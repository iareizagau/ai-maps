"""Ninja sub-router for `news`. Mounted at /mubil/api/v1/news/."""

from __future__ import annotations

from ninja import Router

from apps.mubil.news import services
from apps.mubil.news.schemas import NewsArticleOut, NewsRefreshOut
from apps.mubil.news.tasks import refresh_news

router = Router()


@router.get("/health")
def health(request):
    return {"status": "ok", "module": "news"}


@router.get("/", response=list[NewsArticleOut])
def list_news(
    request, relevance: str | None = None, tag: str | None = None, limit: int = 60
):
    return list(services.list_articles(limit=limit, relevance=relevance, tag=tag))


@router.post("/refresh", response=NewsRefreshOut)
def trigger_refresh(request):
    stale, age = services.is_cache_stale()
    if not stale:
        return {"dispatched": False, "reason": "cache_fresh", "latest_age_hours": age}
    refresh_news.delay()
    return {
        "dispatched": True,
        "reason": "cache_stale_or_empty",
        "latest_age_hours": age,
    }
