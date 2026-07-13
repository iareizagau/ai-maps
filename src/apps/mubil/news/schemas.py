"""Pydantic / Ninja schemas for the `news` API surface."""

from __future__ import annotations

from datetime import datetime

from ninja import Schema


class NewsArticleOut(Schema):
    id: int
    source: str
    source_url: str
    title_es: str
    title_eu: str
    summary_es: str
    summary_eu: str
    image_url: str
    published_at: datetime
    relevance: str
    tags: list[str]
    affects_user_plan: bool


class NewsRefreshOut(Schema):
    dispatched: bool
    reason: str
    latest_age_hours: float | None = None
