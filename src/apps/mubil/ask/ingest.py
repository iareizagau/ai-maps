"""CKAN + OpenData Euskadi ingestion for the `ask` RAG corpus.

Populates `MobilityDocument` with text content + metadata. Embeddings are
generated in a separate step (see `embeddings.py`) so the corpus can be
inspected before paying Gemini quota.

Idempotent: looks up by (source_type, source_url). Content changes trigger
re-embedding by nulling the embedding field. Re-runs are safe.

PROPUESTA.md §3.2, §5.4.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

from apps.mubil.models import MobilityDocument

log = logging.getLogger(__name__)


CKAN_BASE = "https://datos.gob.es/apidata"
# datos.gob.es exposes theme-specific endpoints; the slug matches the tail of
# the dcat:theme URI `http://datos.gob.es/kos/sector-publico/sector/{slug}`.
CKAN_THEME_SLUG = "transporte"
HTTP_TIMEOUT = 30
USER_AGENT = "mubil/0.1 (iareizagau@gmail.com)"


# ---------------------------------------------------------------- helpers


def _content_hash(text: str) -> str:
    """Stable hash of canonical text used to detect content change."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _pick_lang(values, lang: str = "es") -> str:
    """Extract a `{_value, _lang}` multilingual field, prefer `lang`."""
    if not values:
        return ""
    if isinstance(values, str):
        return values
    if not isinstance(values, list):
        return str(values)
    for v in values:
        if isinstance(v, dict) and v.get("_lang") == lang:
            return v.get("_value", "")
    head = values[0]
    if isinstance(head, dict):
        return head.get("_value", "")
    return str(head)


@dataclass
class IngestStats:
    source: str
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    pages: int = 0

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "pages": self.pages,
        }


# ---------------------------------------------------------------- upsert


def _upsert(
    *,
    source_type: str,
    source_url: str,
    title: str,
    content: str,
    municipality_naia: str = "",
    stats: IngestStats,
) -> None:
    """Insert or update a MobilityDocument. Nulls embedding if content changed."""
    new_hash = _content_hash(content)
    # MobilityDocument.source_url is a URLField (default max_length=200).
    source_url = source_url[:200] if source_url else ""

    existing = (
        MobilityDocument.objects
        .filter(source_type=source_type, source_url=source_url)
        .first()
        if source_url
        else MobilityDocument.objects.filter(content_hash=new_hash).first()
    )

    if existing is None:
        MobilityDocument.objects.create(
            source_type=source_type,
            source_url=source_url,
            title=title[:300],
            content=content,
            content_hash=new_hash,
            municipality_naia=municipality_naia,
        )
        stats.created += 1
        return

    if existing.content_hash == new_hash:
        stats.skipped += 1
        return

    existing.title = title[:300]
    existing.content = content
    existing.content_hash = new_hash
    existing.municipality_naia = municipality_naia or existing.municipality_naia
    existing.embedding = None  # force re-embedding on next embed run
    existing.save(update_fields=[
        "title", "content", "content_hash", "municipality_naia",
        "embedding", "updated_at",
    ])
    stats.updated += 1


# ---------------------------------------------------------------- CKAN datos.gob.es


def _fetch_ckan_page(page: int, page_size: int, theme_slug: str) -> dict:
    url = f"{CKAN_BASE}/catalog/dataset/theme/{theme_slug}"
    params = {"_pageSize": page_size, "_page": page}
    r = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def _ckan_to_doc_payload(item: dict) -> Optional[dict]:
    """Map a CKAN dataset record to a MobilityDocument payload (or None)."""
    title = _pick_lang(item.get("title"), "es")
    desc = _pick_lang(item.get("description"), "es")
    if not title or not desc:
        return None

    keywords = item.get("keyword") or []
    if isinstance(keywords, list):
        kw_text = ", ".join(str(k) for k in keywords if k)
    else:
        kw_text = str(keywords)

    content = f"{title}\n\n{desc}"
    if kw_text:
        content += f"\n\nKeywords: {kw_text}"

    source_url = item.get("_about") or item.get("identifier") or ""
    if isinstance(source_url, list):
        source_url = source_url[0] if source_url else ""

    return {
        "title": title,
        "source_url": source_url,
        "content": content,
    }


def ingest_ckan(
    *,
    max_pages: int = 20,
    page_size: int = 50,
    theme_slug: str = CKAN_THEME_SLUG,
    dry_run: bool = False,
) -> IngestStats:
    """Ingest CKAN datos.gob.es datasets filtered by theme slug.

    Args:
        max_pages: hard cap (default 20 × 50 = 1.000 docs).
        page_size: CKAN allows up to ~100.
        theme_slug: dcat:theme tail slug (default: 'transporte').
        dry_run: parse + count, don't write.

    Returns:
        IngestStats with counts.
    """
    stats = IngestStats(source=f"ckan_datos_gob:{theme_slug}")

    for page in range(max_pages):
        try:
            payload = _fetch_ckan_page(page, page_size, theme_slug)
        except requests.exceptions.JSONDecodeError as e:
            # CKAN occasionally returns truncated JSON for a single page —
            # skip it instead of aborting the whole crawl.
            log.warning("CKAN page %d JSON malformed, skipping: %s", page, e)
            stats.errors += 1
            continue
        except requests.RequestException as e:
            log.error("CKAN page %d HTTP failed, aborting crawl: %s", page, e)
            stats.errors += 1
            break

        items = (
            payload.get("result", {}).get("items")
            or payload.get("items")
            or []
        )
        if not items:
            log.info("CKAN page %d empty — stopping", page)
            break

        stats.pages += 1

        for item in items:
            stats.fetched += 1
            doc = _ckan_to_doc_payload(item)
            if doc is None:
                stats.skipped += 1
                continue
            if dry_run:
                continue
            try:
                _upsert(
                    source_type=MobilityDocument.SourceType.DATASET,
                    source_url=doc["source_url"],
                    title=doc["title"],
                    content=doc["content"],
                    stats=stats,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("CKAN upsert failed for %r: %s", doc["title"][:60], e)
                stats.errors += 1

        log.info(
            "CKAN page %d → fetched=%d created=%d updated=%d skipped=%d errors=%d",
            page, stats.fetched, stats.created, stats.updated, stats.skipped, stats.errors,
        )

    return stats
