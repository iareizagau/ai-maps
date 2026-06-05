"""Celery task for on-demand news refresh.

Dispatched by `views.news_page` when the cache is stale. Not registered
in any beat schedule — on-demand only to control Gemini cost.
"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.mubil.news import services

log = logging.getLogger(__name__)


@shared_task(name="mubil.news.refresh")
def refresh_news(embed: bool = True) -> dict:
    stats = services.refresh(embed=embed)
    return stats.as_dict()
