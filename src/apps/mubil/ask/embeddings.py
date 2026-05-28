"""Gemini embedding wrapper for the `ask` RAG module.

Uses `google-genai` (the supported SDK; `google-generativeai` is EOL) with
`gemini-embedding-001` truncated to 768d via Matryoshka so the existing
`VectorField(dimensions=768)` schema is preserved.

Embeds rows in `MobilityDocument` whose `embedding` field is null. Idempotent
— callers (e.g. `ingest.py`) null the embedding when content changes, so the
next embed run picks them up.

Free-tier limits (as of 2026):
  - gemini-embedding-001: 100 RPM on free tier. Throttle accordingly.

PROPUESTA.md §3.2, §5.2.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings

from apps.mubil.models import MobilityDocument

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- config

EMBEDDING_DIM = 768
DEFAULT_THROTTLE_S = 0.6   # ~100 RPM free-tier ceiling on gemini-embedding-001
DEFAULT_BATCH_SIZE = 50
MAX_INPUT_CHARS = 8000


# ---------------------------------------------------------------- stats


@dataclass
class EmbedStats:
    total_pending: int = 0
    embedded: int = 0
    errors: int = 0
    skipped: int = 0
    elapsed_s: float = 0.0

    def as_dict(self) -> dict:
        return {
            "total_pending": self.total_pending,
            "embedded": self.embedded,
            "errors": self.errors,
            "skipped": self.skipped,
            "elapsed_s": round(self.elapsed_s, 2),
        }


# ---------------------------------------------------------------- Gemini call


class EmbeddingError(RuntimeError):
    """Raised when the Gemini embed call fails permanently for a text."""


def _configure_genai():
    """Build a google-genai client lazily so unit tests can mock it without
    the SDK being installed at import time.
    """
    if not settings.GEMINI_API_KEY:
        raise EmbeddingError(
            "GEMINI_API_KEY is not set — embedding cannot proceed. "
            "Get one at https://aistudio.google.com/app/apikey."
        )

    from google import genai

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _normalize(vec: List[float]) -> List[float]:
    """Unit-normalize. gemini-embedding-001 only normalizes the full 3072d
    output; truncated MRL vectors must be normalized by the caller for cosine
    similarity to behave as expected.
    """
    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return list(vec)
    return [v / norm for v in vec]


def embed_text(text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
    """Call Gemini embedding model for a single text.

    Args:
        text: input text (truncated to MAX_INPUT_CHARS).
        task_type: 'RETRIEVAL_DOCUMENT' for corpus docs, 'RETRIEVAL_QUERY' for
                   user queries. Asymmetric task types yield better retrieval
                   than 'SEMANTIC_SIMILARITY'.

    Returns:
        768-dim unit-norm list of floats.
    """
    from google.genai import types

    client = _configure_genai()
    payload = text[:MAX_INPUT_CHARS]
    response = client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=payload,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    vec = list(response.embeddings[0].values)
    if len(vec) != EMBEDDING_DIM:
        raise EmbeddingError(
            f"Unexpected embedding dim {len(vec)} (want {EMBEDDING_DIM})."
        )
    return _normalize(vec)


# ---------------------------------------------------------------- corpus walker


def embed_corpus(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    throttle_s: float = DEFAULT_THROTTLE_S,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> EmbedStats:
    """Embed every MobilityDocument whose `embedding` is null.

    Args:
        batch_size: rows fetched per DB iteration (small to keep memory low).
        throttle_s: sleep between Gemini calls (rate-limit safety).
        limit: hard cap on rows processed (None = all).
        dry_run: walk the queryset and count, don't call Gemini, don't write.
    """
    stats = EmbedStats()
    started = time.monotonic()

    pending_qs = MobilityDocument.objects.filter(embedding__isnull=True).order_by("id")
    stats.total_pending = pending_qs.count()

    if limit is not None:
        pending_qs = pending_qs[:limit]

    processed = 0
    for doc in pending_qs.iterator(chunk_size=batch_size):
        if not doc.content.strip():
            stats.skipped += 1
            continue

        if dry_run:
            stats.embedded += 1
            processed += 1
            continue

        try:
            vec = embed_text(doc.content, task_type="RETRIEVAL_DOCUMENT")
        except Exception as e:  # noqa: BLE001
            log.warning("embed failed for doc id=%d (%s): %s", doc.id, doc.title[:60], e)
            stats.errors += 1
            continue

        doc.embedding = vec
        doc.save(update_fields=["embedding", "updated_at"])
        stats.embedded += 1
        processed += 1

        if throttle_s > 0:
            time.sleep(throttle_s)

    stats.elapsed_s = time.monotonic() - started
    return stats
