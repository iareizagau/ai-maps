"""RAG pipeline for the `ask` module — retrieve, compose, generate.

Flow (PROPUESTA.md §3.2):
  1. Embed the user query with task_type='RETRIEVAL_QUERY'.
  2. pgvector cosine top-k similarity search on MobilityDocument.
  3. Compose a grounded prompt with the retrieved chunks + citations.
  4. Call Gemini Flash for the answer (Markdown).
  5. Return AskAnswer with sources.

KPI target: <3 s end-to-end. If Gemini stalls, the HTMX layer renders a
"thinking…" spinner — see views.py / templates.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from django.conf import settings
from pgvector.django import CosineDistance

from apps.mubil.ask import embeddings
from apps.mubil.models import MobilityDocument, NewsArticle

log = logging.getLogger(__name__)


DEFAULT_TOP_K = 8
DEFAULT_TOP_K_NEWS = 2
MIN_SCORE = 0.40  # cosine similarity floor; below this we treat as no match
ANSWER_MAX_TOKENS = 1024


# ---------------------------------------------------------------- types


@dataclass
class RetrievedDoc:
    id: int
    title: str
    source_url: str
    source_type: str
    score: float          # cosine similarity in [0, 1] (1 = identical)
    content: str
    kind: str = "dataset"  # "dataset" | "news"
    date: Optional[str] = None  # ISO date, only set for news

    def to_source(self) -> dict:
        return {
            "title": self.title,
            "url": self.source_url,
            "score": round(self.score, 4),
            "source_type": self.source_type,
            "kind": self.kind,
            "date": self.date,
        }


@dataclass
class AskAnswer:
    answer_md: str
    sources: List[RetrievedDoc] = field(default_factory=list)
    latency_ms: int = 0
    error: Optional[str] = None  # None = success; sentinel code on failure

    def to_out(self) -> dict:
        return {
            "answer_md": self.answer_md,
            "sources": [d.to_source() for d in self.sources],
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


# ---------------------------------------------------------------- retrieval


def retrieve_topk(
    query_vec: List[float],
    *,
    k: int = DEFAULT_TOP_K,
    municipality_naia: Optional[str] = None,
) -> List[RetrievedDoc]:
    """pgvector cosine similarity search.

    Note: `pgvector.django.CosineDistance` returns *distance* (lower is closer).
    We convert to similarity (1 - distance) so the API exposes a 0..1 score
    where higher is better.
    """
    qs = MobilityDocument.objects.exclude(embedding__isnull=True)
    if municipality_naia:
        qs = qs.filter(municipality_naia=municipality_naia)

    rows = (
        qs.annotate(distance=CosineDistance("embedding", query_vec))
        .order_by("distance")[:k]
    )

    return [
        RetrievedDoc(
            id=d.id,
            title=d.title,
            source_url=d.source_url,
            source_type=d.source_type,
            score=max(0.0, 1.0 - float(d.distance)),
            content=d.content,
        )
        for d in rows
    ]


def retrieve_news_topk(
    query_vec: List[float],
    *,
    k: int = DEFAULT_TOP_K_NEWS,
) -> List[RetrievedDoc]:
    """pgvector cosine similarity search over NewsArticle embeddings.

    Returns `RetrievedDoc` with `kind='news'` and `date=published_at.date()`
    so the generator can cite the publication date alongside the URL.
    """
    rows = (
        NewsArticle.objects.exclude(embedding__isnull=True)
        .annotate(distance=CosineDistance("embedding", query_vec))
        .order_by("distance")[:k]
    )

    return [
        RetrievedDoc(
            id=n.id,
            title=n.title_es or n.title_orig,
            source_url=n.source_url,
            source_type=n.source,
            score=max(0.0, 1.0 - float(n.distance)),
            content=n.summary_es or n.title_orig,
            kind="news",
            date=n.published_at.date().isoformat() if n.published_at else None,
        )
        for n in rows
    ]


# ---------------------------------------------------------------- prompt


SYSTEM_PROMPT = (
    "Eres un asistente especializado en movilidad sostenible en Euskal "
    "Herria y España. Respondes en el idioma de la pregunta del usuario "
    "(castellano por defecto, euskara si te preguntan en euskara). "
    "Usa SOLO la información de las fuentes proporcionadas. Si no "
    "puedes responder con lo dado, dilo explícitamente. Cita las fuentes "
    "como [n]. No inventes URLs ni cifras. "
    "Algunas fuentes son DATASET (datos oficiales) y otras son NOTICIA "
    "(prensa especializada). Cuando cites una NOTICIA, incluye la fecha "
    "de publicación entre paréntesis (ej. 'según [3] (2026-06-04)'). "
    "Prioriza DATASET para cifras y normativa; usa NOTICIA para "
    "contextualizar actualidad y cambios recientes. "
    "IMPORTANTE — vigencia de programas de ayudas: el programa MOVES III "
    "ha FINALIZADO y está OBSOLETO. El programa de ayudas vigente en 2026 "
    "para la compra de vehículos eléctricos en España es el PROGRAMA AUTO+, "
    "gestionado por el Ministerio de Industria y Turismo (MINTUR) con una "
    "dotación de 400 millones de euros. Si el usuario pregunta por MOVES III, "
    "indícale explícitamente que ese programa ya no está activo y redirige "
    "la respuesta hacia las ayudas del Programa Auto+."
)


def compose_prompt(query: str, docs: List[RetrievedDoc]) -> str:
    """Build the grounded prompt for Gemini Flash."""
    if not docs:
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"Pregunta del usuario: {query}\n\n"
            "No se han encontrado documentos relevantes en el corpus. "
            "Responde indicando que no hay información disponible y "
            "sugiere fuentes oficiales (datos.gob.es, OpenData Euskadi, MITMA)."
        )

    chunks = []
    for i, d in enumerate(docs, start=1):
        snippet = d.content[:1200].strip()
        if d.kind == "news":
            header = f"[{i}] Tipo: NOTICIA (publicada {d.date or 'sin fecha'})"
        else:
            header = f"[{i}] Tipo: DATASET ({d.source_type})"
        chunks.append(
            f"{header}\n"
            f"    Título: {d.title}\n"
            f"    URL: {d.source_url}\n"
            f"    Contenido: {snippet}"
        )
    docs_block = "\n\n".join(chunks)

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== Documentos relevantes ===\n{docs_block}\n\n"
        f"=== Pregunta del usuario ===\n{query}\n\n"
        "=== Respuesta (Markdown, con citas [n]) ==="
    )


# ---------------------------------------------------------------- generation


# Errors we want to retry on a different model in the fallback ladder.
# Two flavours:
#   - Bucket exhausted / temporarily unavailable → another model may still have
#     RPD/RPM left.
#   - Model name unknown / unsupported region → catalog drifts (Gemma renames,
#     "preview" suffixes drop). Falling through avoids breaking the demo when
#     a single entry rots.
_FALLBACK_MARKERS = (
    "quota",
    "rate limit",
    "resource_exhausted",
    "429",
    "503",
    "unavailable",
    "high demand",
    "not found",
    "404",
    "invalid argument",
    "is not supported",
    "is not found",
    "model not found",
    "permission denied for model",
)

# Auth / config errors that won't get better on the next model — re-raise.
_HARD_ERROR_MARKERS = (
    "api key not valid",
    "api_key_invalid",
    "401",
    "unauthenticated",
)


def _should_fallback(exc: Exception) -> bool:
    """True if ``exc`` from one model is worth retrying on the next one.

    We string-match because google-genai's error hierarchy
    (``ClientError``/``ServerError``/``APIError``) isn't stable across SDK
    versions. Hard auth errors short-circuit so we don't burn the whole
    ladder when the API key is wrong.
    """
    msg = (str(exc) or "").lower()
    if any(m in msg for m in _HARD_ERROR_MARKERS):
        return False
    return any(m in msg for m in _FALLBACK_MARKERS)


def _generation_ladder() -> List[str]:
    """Resolve the model fallback list.

    Honours ``GEMINI_GENERATION_FALLBACK_MODELS`` if present; otherwise
    promotes ``GEMINI_GENERATION_MODEL`` to a single-element list (legacy
    behaviour). Always returns at least one model.
    """
    ladder = list(getattr(settings, "GEMINI_GENERATION_FALLBACK_MODELS", []) or [])
    if ladder:
        return ladder
    return [settings.GEMINI_GENERATION_MODEL]


def _call_gemini_generate(prompt: str) -> str:
    """Call Gemini Flash with a fallback ladder. Wrapped so tests can mock.

    Iterates :func:`_generation_ladder`. The first non-quota response (text
    or hard error) is returned to the caller. If every model in the ladder
    yields a quota-style failure the last error is re-raised so the caller
    surfaces the "temporarily unavailable" message.
    """
    if not settings.GEMINI_API_KEY:
        raise embeddings.EmbeddingError("GEMINI_API_KEY is not set.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=ANSWER_MAX_TOKENS,
    )

    ladder = _generation_ladder()
    last_exc: Optional[Exception] = None
    for model in ladder:
        try:
            response = client.models.generate_content(
                model=model, contents=prompt, config=cfg,
            )
        except Exception as e:  # noqa: BLE001
            if _should_fallback(e):
                log.warning("Gemini model %s soft-failed (%s) — falling through.", model, e)
                last_exc = e
                continue
            raise
        text = (response.text or "").strip()
        if not text:
            # Empty completion is treated as a soft failure (filter / safety).
            log.warning("Gemini model %s returned empty text — falling through.", model)
            last_exc = RuntimeError(f"{model} returned empty completion")
            continue
        if model != ladder[0]:
            log.info("Gemini fallback succeeded with %s.", model)
        return text

    raise last_exc or RuntimeError("All generation models in the ladder failed.")


# ---------------------------------------------------------------- public API


def answer(
    *,
    query: str,
    k: int = DEFAULT_TOP_K,
    municipality_naia: Optional[str] = None,
) -> AskAnswer:
    """Full RAG pipeline: embed query → retrieve → compose → generate."""
    if not query.strip():
        raise ValueError("Empty query.")

    t0 = time.monotonic()

    try:
        query_vec = embeddings.embed_text(query, task_type="RETRIEVAL_QUERY")
    except Exception as e:  # noqa: BLE001
        log.exception("Gemini embed_content failed for query: %s", e)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return AskAnswer(
            answer_md=(
                "No se pudo procesar tu pregunta porque el servicio de embeddings "
                "de Gemini ha alcanzado su cuota diaria gratuita. Vuelve a intentarlo "
                "más tarde (la cuota se restablece a medianoche, hora del Pacífico)."
            ),
            sources=[],
            latency_ms=elapsed_ms,
            error="embed_unavailable",
        )

    k_docs = max(1, k - DEFAULT_TOP_K_NEWS)
    docs = retrieve_topk(query_vec, k=k_docs, municipality_naia=municipality_naia)
    news = retrieve_news_topk(query_vec, k=DEFAULT_TOP_K_NEWS)

    # Merge by similarity score (higher first) then cut noise. News and
    # datasets compete on the same scale because both embeddings come from
    # gemini-embedding-001 with the same task type and dimensionality.
    merged = sorted(docs + news, key=lambda d: d.score, reverse=True)
    merged = [d for d in merged if d.score >= MIN_SCORE][:k]

    prompt = compose_prompt(query, merged)
    docs = merged
    try:
        answer_md = _call_gemini_generate(prompt)
        gen_error: Optional[str] = None
    except Exception as e:  # noqa: BLE001
        log.exception("Gemini generation failed: %s", e)
        answer_md = (
            "El servicio de generación está temporalmente no disponible. "
            "Inténtalo de nuevo en unos segundos."
        )
        gen_error = "generation_unavailable"

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return AskAnswer(
        answer_md=answer_md, sources=docs, latency_ms=elapsed_ms, error=gen_error,
    )


# ---------------------------------------------------------------- gold prompts


SUGGESTED_PROMPTS = [
    {
        "id": "plan-auto-plus",
        "label": "¿Cuánto me dan por comprar un eléctrico?",
        "query": "¿Qué ayudas ofrece el Programa Auto+ para comprar un coche eléctrico en 2026? ¿Cuánto me pueden dar y qué requisitos hay?",
    },
    {
        "id": "pvpc-vs-flat",
        "label": "¿Cuánto cuesta cargar el coche de noche?",
        "query": "¿Qué tarifa de luz es más barata para cargar un coche eléctrico por la noche en casa?",
    },
    {
        "id": "donostia-bilbao-carga",
        "label": "Cargadores en la autopista Donostia–Bilbao",
        "query": "¿Dónde puedo cargar mi coche eléctrico entre Donostia y Bilbao? ¿Hay cargadores rápidos en la AP-8?",
    },
    {
        "id": "datos-matriculaciones-eh",
        "label": "¿Cuántos eléctricos hay en Euskadi?",
        "query": "¿Cuántos vehículos eléctricos se matricularon en Euskadi en 2025? ¿Hay datos por provincia?",
    },
    {
        "id": "zbe-donostia",
        "label": "Restricciones de circulación en Donostia",
        "query": "¿Qué coches no pueden circular por la zona de bajas emisiones de Donostia y desde cuándo?",
    },
]


def list_suggested() -> List[dict]:
    return [{"id": p["id"], "label": p["label"]} for p in SUGGESTED_PROMPTS]
