"""Normativa corpus expansion for the `ask` module.

Why this exists: the original CKAN ingest covers dataset *metadata* — fine
for "what data is there?" queries, useless for regulatory questions like
MOVES III or DGT labelling. This module ingests the curated URL list in
:mod:`normativa_sources`, extracting main text from HTML (trafilatura) or
PDFs (pypdf), chunking it into ~2 KB pieces, and upserting as
``MobilityDocument`` rows with ``source_type='norma'``.

Embedding is intentionally deferred to ``manage.py embed_ask_corpus`` —
new chunks land with ``embedding IS NULL`` and the existing batch command
picks them up idempotently.

PROPUESTA.md §3.2.
"""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass

import requests

from apps.mubil.ask.ingest import IngestStats, _upsert
from apps.mubil.data import normativa_sources
from apps.mubil.models import MobilityDocument

log = logging.getLogger(__name__)


HTTP_TIMEOUT = 45
USER_AGENT = (
    "mubil/0.1 (iareizagau@gmail.com) academic research corpus, "
    "MUBIL Mobility Awards 2026"
)
DEFAULT_CHUNK_CHARS = 2000
MIN_BODY_CHARS = 200  # below this we skip the source (likely empty/JS page).
DEFAULT_THROTTLE_S = 1.0  # be polite to gov.es / Wikipedia.

# Reuse the existing source_type. 'norma' is the closest semantic match
# already in MobilityDocument.SourceType.choices.
SOURCE_TYPE = MobilityDocument.SourceType.NORMA


# ─────────────────────────────────────────────── fetch + extract


def _fetch(url: str) -> tuple[bytes, str]:
    """Return ``(raw_bytes, content_type)``. Raises on HTTP errors."""
    r = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9",
        },
        timeout=HTTP_TIMEOUT,
        allow_redirects=True,
    )
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "")


def _is_pdf(url: str, content_type: str) -> bool:
    return "pdf" in content_type.lower() or url.lower().split("?")[0].endswith(".pdf")


def _extract_pdf(raw: bytes) -> str:
    """Extract concatenated text from a PDF byte string."""
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(raw))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception as e:
            log.debug("PDF page extract failed: %s", e)
    return "\n\n".join(t for t in pages if t.strip())


def _extract_html(raw: bytes, url: str) -> tuple[str, str]:
    """Return ``(main_text, title)`` from an HTML byte string."""
    import trafilatura

    # trafilatura.extract handles encoding detection internally when given bytes.
    body = (
        trafilatura.extract(
            raw,
            url=url,
            favor_recall=False,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        or ""
    )

    # Title via metadata extractor — falls back gracefully if missing.
    title = ""
    try:
        meta = trafilatura.metadata.extract_metadata(raw)
        if meta and meta.title:
            title = meta.title.strip()
    except Exception:
        pass

    return body, title


# ─────────────────────────────────────────────── chunking


# Boundary preferences when greedy-cutting a long blob, in priority order.
# Trafilatura strips paragraph breaks on Wikipedia tables (single ``\n`` only),
# so a chunker that relies purely on ``\n\n`` will fall back to "1 giant chunk"
# — verified live on Bizkaibus (17 KB body, 0 ``\n\n`` separators).
_BOUNDARIES = ("\n\n", "\n", ". ", " ")


def chunk_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    """Split ``text`` into ≤ ``max_chars`` chunks at the best boundary found.

    Strategy per chunk: scan back from ``max_chars`` for the latest paragraph
    break, then newline, sentence, then any space — whichever is at least
    halfway through the window. Falls back to a hard char cut only if none of
    those exists (extremely rare).
    """
    if not text:
        return []
    text = text.strip()
    chunks: list[str] = []
    while len(text) > max_chars:
        cut = max_chars
        for sep in _BOUNDARIES:
            idx = text.rfind(sep, 0, max_chars)
            if idx > max_chars // 2:
                cut = idx + len(sep)
                break
        chunk = text[:cut].strip()
        if chunk:
            chunks.append(chunk)
        text = text[cut:].lstrip()
    tail = text.strip()
    if tail:
        chunks.append(tail)
    return chunks


# ─────────────────────────────────────────────── ingest orchestration


@dataclass
class NormativaIngestStats(IngestStats):
    """Adds source-level counters on top of the CKAN ``IngestStats``."""

    sources_fetched: int = 0
    sources_skipped: int = 0
    chunks_total: int = 0

    def __post_init__(self):
        # Inherit `source` semantics from parent; default to "normativa".
        if not getattr(self, "source", None):
            self.source = "normativa"

    def as_dict(self) -> dict:
        d = super().as_dict()
        d.update(
            {
                "sources_fetched": self.sources_fetched,
                "sources_skipped": self.sources_skipped,
                "chunks_total": self.chunks_total,
            }
        )
        return d


def _ingest_one(
    src: normativa_sources.NormativaSource,
    *,
    stats: NormativaIngestStats,
    dry_run: bool,
) -> None:
    try:
        raw, content_type = _fetch(src.url)
    except Exception as e:
        log.warning("Fetch failed for %s: %s", src.url, e)
        stats.errors += 1
        stats.sources_skipped += 1
        return

    if _is_pdf(src.url, content_type):
        body = _extract_pdf(raw)
        title = src.title_override or src.note or src.url
    else:
        body, page_title = _extract_html(raw, src.url)
        title = src.title_override or page_title or src.note or src.url

    if not body or len(body) < MIN_BODY_CHARS:
        log.info("Empty/short body for %s (%d chars) — skipped.", src.url, len(body))
        stats.sources_skipped += 1
        return

    chunks = chunk_text(body)
    if not chunks:
        stats.sources_skipped += 1
        return

    stats.sources_fetched += 1
    stats.chunks_total += len(chunks)
    n = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk_title = title[:280] + (f" (parte {i + 1}/{n})" if n > 1 else "")
        # Each chunk needs a unique source_url so _upsert can match it back.
        # MobilityDocument.source_url is max_length=200 — keep room for the
        # fragment.
        base_url = src.url[:180]
        chunk_url = base_url if n == 1 else f"{base_url}#c{i}"
        if dry_run:
            stats.fetched += 1
            continue
        _upsert(
            source_type=SOURCE_TYPE,
            source_url=chunk_url,
            title=chunk_title,
            content=chunk,
            municipality_naia=src.region_naia,
            stats=stats,
        )


def ingest_normativa(
    *,
    only: Iterable[str] | None = None,
    throttle_s: float = DEFAULT_THROTTLE_S,
    dry_run: bool = False,
) -> NormativaIngestStats:
    """Ingest the curated normativa URL list into ``MobilityDocument``.

    Args:
        only: optional substring filter on URLs — handy to re-ingest one
            source after fixing its parser.
        throttle_s: sleep between sources (be polite to BOE / Wikipedia).
        dry_run: fetch + parse + chunk, no DB writes.
    """
    stats = NormativaIngestStats(source="normativa")
    sources = list(normativa_sources.ALL_SOURCES)
    if only:
        needles = [n.lower() for n in only]
        sources = [s for s in sources if any(n in s.url.lower() for n in needles)]

    for src in sources:
        _ingest_one(src, stats=stats, dry_run=dry_run)
        if throttle_s > 0:
            time.sleep(throttle_s)

    return stats
