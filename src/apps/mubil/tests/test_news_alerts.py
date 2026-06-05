"""Tests for Fase 2 — news alerts surfaced in the advisor.

Covers:
  - `recent_affecting_plan` filters by both `affects_user_plan=True` and
    the 30-day window.
  - `ranked_for_user` falls back to chronological order when the embedding
    call raises (offline / no key / quota).
  - `advisor_page` context exposes `recent_alerts` (empty list is fine).
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.mubil.models import NewsArticle
from apps.mubil.news import services


def _make(url, *, affects=True, days_ago=1, tags=None, title='X'):
    return NewsArticle.objects.create(
        source='newsapi',
        source_url=url,
        title_orig=title,
        title_es=title,
        title_eu=f'{title} EU',
        summary_es='Resumen.',
        summary_eu='Laburpena.',
        published_at=timezone.now() - timedelta(days=days_ago),
        relevance=NewsArticle.Relevance.ESPANA,
        tags=tags or ['subvencion'],
        affects_user_plan=affects,
    )


class RecentAffectingPlanTests(TestCase):

    def test_only_flagged_within_window_are_returned(self):
        _make('https://x/inside-flagged', affects=True, days_ago=5, title='Dentro y flag')
        _make('https://x/inside-unflagged', affects=False, days_ago=5, title='Dentro sin flag')
        _make('https://x/outside-flagged', affects=True, days_ago=45, title='Fuera ventana')

        result = services.recent_affecting_plan(days=30, limit=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title_orig, 'Dentro y flag')

    def test_limit_caps_results(self):
        for i in range(5):
            _make(f'https://x/{i}', affects=True, days_ago=i)

        self.assertEqual(len(services.recent_affecting_plan(limit=3)), 3)


class RankedForUserTests(TestCase):

    def test_no_articles_returns_empty(self):
        self.assertEqual(services.ranked_for_user(query_text='x'), [])

    def test_articles_without_embedding_are_excluded(self):
        _make('https://x/no-embed', affects=True, days_ago=2)
        self.assertEqual(services.ranked_for_user(query_text='x'), [])

    def test_embedding_failure_falls_back_to_chronological(self):
        a = _make('https://x/a', affects=True, days_ago=10, title='Antigua')
        b = _make('https://x/b', affects=True, days_ago=1, title='Reciente')
        # Give them embeddings so the QS isn't filtered out.
        a.embedding = [0.0] * 768
        a.save(update_fields=['embedding'])
        b.embedding = [0.0] * 768
        b.save(update_fields=['embedding'])

        with mock.patch(
            'apps.mubil.news.services.embeddings.embed_text',
            side_effect=RuntimeError('quota'),
        ):
            result = services.ranked_for_user(query_text='cualquier cosa', limit=2)

        self.assertEqual([r.title_orig for r in result], ['Reciente', 'Antigua'])


class AdvisorPageContextTests(TestCase):

    def test_recent_alerts_in_context_even_when_empty(self):
        resp = self.client.get(reverse('mubil:advisor'), HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('recent_alerts', resp.context)
        self.assertEqual(list(resp.context['recent_alerts']), [])

    def test_alert_strip_renders_when_news_flagged(self):
        _make('https://x/flagged', affects=True, days_ago=2, title='Subvención ampliada')
        resp = self.client.get(reverse('mubil:advisor'), HTTP_HOST='localhost')
        self.assertContains(resp, 'Subvención ampliada')
        self.assertContains(resp, 'que afecta')
