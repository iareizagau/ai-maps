"""Pipeline for the `news` aggregator: fetch → dedupe → classify (Gemini) → embed → persist.

On-demand only — no celery beat. `views.news_page` dispatches
`tasks.refresh_news` when `is_cache_stale()`. Per-article Gemini call
reuses `apps.mubil.ask.services._call_gemini_generate` (fallback ladder
covers quota/safety-filter failures). Embedding errors are tolerated:
the article is saved without the vector.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.mubil.ask import embeddings, services as ask_services
from apps.mubil.models import NewsArticle
from apps.mubil.news import sources
from apps.mubil.news.sources import RawArticle

log = logging.getLogger(__name__)


CLASSIFY_PROMPT_TEMPLATE = """Eres un editor especializado en movilidad eléctrica para una audiencia de Euskal Herria.

Recibes el título y descripción de una noticia. Devuelve EXCLUSIVAMENTE un objeto JSON válido (sin texto antes/después, sin bloque markdown ```json) con esta forma exacta:

{{
  "title_es": "string, máx 200 chars, en castellano",
  "title_eu": "string, máx 200 chars, en euskera",
  "summary_es": "string, 2-3 frases, neutral, sin opinión, castellano",
  "summary_eu": "string, 2-3 frases, neutral, sin opinión, euskera",
  "tags": ["subvencion"|"precio_luz"|"modelo_nuevo"|"normativa"|"infraestructura"|"industria"|"opinion"|"otro", ...],
  "relevance": "EUSKADI" | "ESPANA" | "GLOBAL",
  "affects_user_plan": true | false
}}

Reglas:
- `relevance`: EUSKADI si menciona Euskadi/País Vasco/Bizkaia/Gipuzkoa/Araba; ESPANA si menciona España o regiones españolas; GLOBAL en otro caso.
- `affects_user_plan`: true SOLO si la noticia cambia subvenciones, fiscalidad, PVPC, o normativa que afecte al coste de poseer un EV en España. false para lanzamientos, opinión, industria global.
- `tags`: 1-3 etiquetas de la lista cerrada anterior.
- Si el contenido es irrelevante a la movilidad eléctrica, devuelve igualmente JSON válido pero pon `tags=["otro"]` y `affects_user_plan=false`.

=== Titular ===
{title}

=== Descripción ===
{snippet}
"""


# ---------------------------------------------------------------- types


@dataclass
class RefreshStats:
    fetched: int = 0
    new: int = 0
    classified: int = 0
    embedded: int = 0
    classify_errors: int = 0
    embed_errors: int = 0
    elapsed_s: float = 0.0

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "new": self.new,
            "classified": self.classified,
            "embedded": self.embedded,
            "classify_errors": self.classify_errors,
            "embed_errors": self.embed_errors,
            "elapsed_s": round(self.elapsed_s, 2),
        }


# ---------------------------------------------------------------- staleness


def latest_fetched_at():
    row = NewsArticle.objects.order_by("-created_at").values("created_at").first()
    return row["created_at"] if row else None


def is_cache_stale() -> tuple[bool, float | None]:
    """Returns (stale, age_hours). `age_hours` is None when the cache is empty."""
    latest = latest_fetched_at()
    if latest is None:
        return True, None
    age = timezone.now() - latest
    age_hours = age.total_seconds() / 3600
    return age_hours > settings.NEWS_CACHE_HOURS, age_hours


# ---------------------------------------------------------------- classify


def _parse_gemini_json(raw: str) -> dict:
    """Strip optional ```json fences and parse. Raises ValueError on malformed."""
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1] if "\n" in txt else txt
        if txt.endswith("```"):
            txt = txt[:-3]
        txt = txt.strip()
    return json.loads(txt)


def classify_article(raw: RawArticle) -> dict | None:
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(
        title=raw.title,
        snippet=raw.snippet or "(sin descripción)",
    )
    try:
        text = ask_services._call_gemini_generate(prompt)
    except Exception as e:
        log.warning("Gemini classify failed for %s: %s", raw.source_url, e)
        return None
    try:
        data = _parse_gemini_json(text)
    except (ValueError, KeyError) as e:
        log.warning(
            "Gemini returned non-JSON for %s: %s | raw=%r",
            raw.source_url,
            e,
            text[:200],
        )
        return None

    valid_relevance = {c[0] for c in NewsArticle.Relevance.choices}
    if data.get("relevance") not in valid_relevance:
        data["relevance"] = NewsArticle.Relevance.GLOBAL
    if not isinstance(data.get("tags"), list):
        data["tags"] = ["otro"]
    return data


# ---------------------------------------------------------------- embed


def _embed_for_search(article: NewsArticle) -> list | None:
    text = f"{article.title_es}\n\n{article.summary_es}".strip()
    if not text:
        return None
    try:
        return embeddings.embed_text(text, task_type="RETRIEVAL_DOCUMENT")
    except Exception as e:
        log.warning("embed failed for news id=%s: %s", article.id, e)
        return None


# ---------------------------------------------------------------- orchestrator


def refresh(*, embed: bool = True, throttle_s: float = 0.6) -> RefreshStats:
    """Full pipeline: fetch all sources, classify new ones, embed, persist.

    Idempotent via `source_url` uniqueness.
    """
    stats = RefreshStats()
    started = time.monotonic()

    raw_items = sources.fetch_all()
    stats.fetched = len(raw_items)

    seen_in_batch: set[str] = set()
    deduped: list[RawArticle] = []
    for r in raw_items:
        if r.source_url in seen_in_batch:
            continue
        seen_in_batch.add(r.source_url)
        deduped.append(r)

    existing = set(
        NewsArticle.objects.filter(source_url__in=list(seen_in_batch)).values_list(
            "source_url", flat=True
        )
    )
    new_raws = [r for r in deduped if r.source_url not in existing]
    stats.new = len(new_raws)

    for raw in new_raws:
        cls = classify_article(raw)
        if cls is None:
            stats.classify_errors += 1
            continue
        stats.classified += 1

        article = NewsArticle.objects.create(
            source=raw.source,
            source_url=raw.source_url,
            title_orig=raw.title,
            title_es=(cls.get("title_es") or raw.title)[:300],
            title_eu=(cls.get("title_eu") or "")[:300],
            summary_es=cls.get("summary_es") or "",
            summary_eu=cls.get("summary_eu") or "",
            image_url=raw.image_url or "",
            published_at=raw.published_at,
            relevance=cls["relevance"],
            tags=cls.get("tags", []),
            affects_user_plan=bool(cls.get("affects_user_plan", False)),
        )

        if embed:
            vec = _embed_for_search(article)
            if vec is None:
                stats.embed_errors += 1
            else:
                article.embedding = vec
                article.save(update_fields=["embedding", "updated_at"])
                stats.embedded += 1

        if throttle_s > 0:
            time.sleep(throttle_s)

    stats.elapsed_s = time.monotonic() - started
    log.info("news.refresh stats=%s", stats.as_dict())
    return stats


# ---------------------------------------------------------------- read API


def list_articles(
    *, limit: int = 60, relevance: str | None = None, tag: str | None = None
):
    qs = NewsArticle.objects.all()
    if relevance:
        qs = qs.filter(relevance=relevance)
    if tag:
        qs = qs.filter(tags__contains=[tag])
    return qs.order_by("-published_at")[:limit]


# ---------------------------------------------------------------- alerts (Fase 2)

ALERT_WINDOW_DAYS = 30


def recent_affecting_plan(*, days: int = ALERT_WINDOW_DAYS, limit: int = 3):
    """Chronological feed of `affects_user_plan=True` news within the window."""
    cutoff = timezone.now() - timedelta(days=days)
    return list(
        NewsArticle.objects.filter(
            affects_user_plan=True, published_at__gte=cutoff
        ).order_by("-published_at")[:limit]
    )


def ranked_for_user(
    *, query_text: str, days: int = ALERT_WINDOW_DAYS, limit: int = 3
) -> list:
    """Top affects_user_plan news within the window, ranked by embedding
    similarity to `query_text`. Falls back to chronological order if the
    embedding call fails (quota, network, missing key).
    """
    cutoff = timezone.now() - timedelta(days=days)
    base = NewsArticle.objects.filter(
        affects_user_plan=True, published_at__gte=cutoff
    ).exclude(embedding__isnull=True)
    if not base.exists():
        return []

    try:
        qvec = embeddings.embed_text(query_text, task_type="RETRIEVAL_QUERY")
    except Exception as e:
        log.warning("news ranking embedding failed (%s) — chronological fallback.", e)
        return recent_affecting_plan(days=days, limit=limit)

    from pgvector.django import CosineDistance

    return list(
        base.annotate(_distance=CosineDistance("embedding", qvec)).order_by(
            "_distance"
        )[:limit]
    )
