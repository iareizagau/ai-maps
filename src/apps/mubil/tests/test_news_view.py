"""Tests for `news_page` HTMX-free view + nav wiring.

Verifies:
  - Public, no login required.
  - Empty cache → renders, dispatches a Celery refresh.
  - Fresh cache → renders, does NOT dispatch a refresh.
  - relevance / tag filters narrow the queryset.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.mubil.models import NewsArticle


def _make(url, *, title='Titular', relevance='ESPANA', tags=None, days_ago=0):
    pub = datetime(2026, 6, 5, tzinfo=timezone.utc)
    return NewsArticle.objects.create(
        source='newsapi',
        source_url=url,
        title_orig=title,
        title_es=title,
        title_eu=f'{title} EU',
        summary_es='Resumen.',
        summary_eu='Laburpena.',
        published_at=pub,
        relevance=relevance,
        tags=tags or [],
    )


class NewsPageTests(TestCase):

    def test_empty_cache_dispatches_refresh(self):
        with mock.patch('apps.mubil.views.refresh_news.delay') as m:
            resp = self.client.get(reverse('mubil:news'), HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        m.assert_called_once()
        # Empty-state message renders.
        self.assertContains(resp, 'Sin noticias todavía')

    @override_settings(NEWS_CACHE_HOURS=6)
    def test_fresh_cache_does_not_dispatch(self):
        # Article created just now → cache fresh.
        _make('https://example.com/a', title='Subvención ampliada')
        with mock.patch('apps.mubil.views.refresh_news.delay') as m:
            resp = self.client.get(reverse('mubil:news'), HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        m.assert_not_called()
        self.assertContains(resp, 'Subvención ampliada')

    def test_relevance_filter(self):
        _make('https://example.com/eu', title='Solo Euskadi', relevance='EUSKADI')
        _make('https://example.com/es', title='Solo España', relevance='ESPANA')
        with mock.patch('apps.mubil.views.refresh_news.delay'):
            resp = self.client.get(
                reverse('mubil:news') + '?relevance=EUSKADI',
                HTTP_HOST='localhost',
            )
        self.assertContains(resp, 'Solo Euskadi')
        self.assertNotContains(resp, 'Solo España')

    def test_tag_filter(self):
        _make('https://example.com/sub', title='Con tag subvención', tags=['subvencion'])
        _make('https://example.com/luz', title='Con tag precio_luz', tags=['precio_luz'])
        with mock.patch('apps.mubil.views.refresh_news.delay'):
            resp = self.client.get(
                reverse('mubil:news') + '?tag=subvencion',
                HTTP_HOST='localhost',
            )
        self.assertContains(resp, 'Con tag subvención')
        self.assertNotContains(resp, 'Con tag precio_luz')

    def test_celery_down_does_not_500(self):
        """If the broker is down, the page must still render."""
        with mock.patch('apps.mubil.views.refresh_news.delay',
                        side_effect=ConnectionError('broker down')):
            resp = self.client.get(reverse('mubil:news'), HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
