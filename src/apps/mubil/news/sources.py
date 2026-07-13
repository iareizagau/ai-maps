"""Sources for the `news` aggregator: NewsAPI + Spanish EV RSS feeds.

Pure I/O — no DB, no Gemini. Returns lists of `RawArticle` dataclasses
that `services.py` then dedupes, classifies, and persists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser
import requests
from django.conf import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- types


@dataclass
class RawArticle:
    source: str
    source_url: str
    title: str
    published_at: datetime
    snippet: str = ""
    image_url: str = ""


# ---------------------------------------------------------------- RSS feeds

RSS_FEEDS = [
    ("forocoches_ev", "https://forococheselectricos.com/feed"),
    ("hibridos_electricos", "https://www.hibridosyelectricos.com/rss/portada"),
    ("movilidad_electrica", "https://movilidadelectrica.com/feed/"),
    (
        "motorpasion_ev",
        "https://www.motorpasion.com/categoria/coches-electricos/rss2.xml",
    ),
]


def _parse_rss_date(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _extract_image(entry) -> str:
    media = entry.get("media_content") or entry.get("media_thumbnail") or []
    if media and isinstance(media, list):
        url = media[0].get("url", "")
        if url:
            return url
    for enc in entry.get("enclosures", []) or []:
        if enc.get("type", "").startswith("image/"):
            return enc.get("href", "") or enc.get("url", "")
    return ""


def fetch_rss(source: str, url: str, *, limit: int = 20) -> list[RawArticle]:
    parsed = feedparser.parse(url)
    if parsed.bozo and not parsed.entries:
        log.warning("RSS %s parse failed: %s", source, parsed.bozo_exception)
        return []

    out: list[RawArticle] = []
    for entry in parsed.entries[:limit]:
        link = entry.get("link") or ""
        title = (entry.get("title") or "").strip()
        if not link or not title:
            continue
        published = _parse_rss_date(entry)
        if not published:
            continue
        snippet = (entry.get("summary") or entry.get("description") or "").strip()
        out.append(
            RawArticle(
                source=source,
                source_url=link,
                title=title[:300],
                published_at=published,
                snippet=snippet[:2000],
                image_url=_extract_image(entry),
            )
        )
    return out


def fetch_rss_all(*, limit_per_feed: int = 20) -> list[RawArticle]:
    all_items: list[RawArticle] = []
    for source, url in RSS_FEEDS:
        try:
            items = fetch_rss(source, url, limit=limit_per_feed)
        except Exception as e:
            log.warning("RSS %s fetch crashed: %s", source, e)
            continue
        log.info("RSS %s → %d items", source, len(items))
        all_items.extend(items)
    return all_items


# ---------------------------------------------------------------- NewsAPI

NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_QUERY = '"coche eléctrico" OR "vehículo eléctrico" OR "movilidad eléctrica"'


def fetch_newsapi(*, page_size: int = 40, language: str = "es") -> list[RawArticle]:
    """Query NewsAPI `everything`. Empty list if no key configured.

    Free dev tier: 100 req/day, articles up to ~1 month old.
    """
    key = (settings.NEWS_API_KEY or "").strip()
    if not key:
        log.info("NEWS_API_KEY not set — skipping NewsAPI source.")
        return []

    params = {
        "q": NEWSAPI_QUERY,
        "language": language,
        "sortBy": "publishedAt",
        "pageSize": page_size,
    }
    headers = {"X-Api-Key": key}
    try:
        resp = requests.get(NEWSAPI_URL, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("NewsAPI fetch failed: %s", e)
        return []

    payload = resp.json()
    if payload.get("status") != "ok":
        log.warning("NewsAPI error response: %s", payload.get("message"))
        return []

    out: list[RawArticle] = []
    for art in payload.get("articles", []):
        url = art.get("url") or ""
        title = (art.get("title") or "").strip()
        if not url or not title:
            continue
        try:
            published = datetime.fromisoformat(
                art["publishedAt"].replace("Z", "+00:00")
            )
        except (KeyError, ValueError):
            continue
        snippet = " ".join(
            filter(
                None,
                [
                    art.get("description") or "",
                    art.get("content") or "",
                ],
            )
        )[:2000]
        out.append(
            RawArticle(
                source="newsapi",
                source_url=url,
                title=title[:300],
                published_at=published,
                snippet=snippet,
                image_url=art.get("urlToImage") or "",
            )
        )
    log.info("NewsAPI → %d items", len(out))
    return out


def fetch_all() -> list[RawArticle]:
    return fetch_newsapi() + fetch_rss_all()
