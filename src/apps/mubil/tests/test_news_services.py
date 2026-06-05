"""Tests for the `news` pipeline: dedupe, classify (Gemini mocked), persist.

Gemini and the embedding SDK are mocked end-to-end. No live network calls
(mandate: feedback_gemini_smoke_tests.md — don't burn quota on tests).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest import mock

from django.test import TestCase, override_settings

from apps.mubil.models import NewsArticle
from apps.mubil.news import services
from apps.mubil.news.sources import RawArticle


def _raw(url: str, *, source: str = 'newsapi', title: str = 'Subvención MOVES III ampliada',
         published_at=None) -> RawArticle:
    return RawArticle(
        source=source,
        source_url=url,
        title=title,
        published_at=published_at or datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        snippet='El gobierno amplía las ayudas MOVES III hasta diciembre.',
        image_url='',
    )


def _gemini_payload(**overrides) -> str:
    data = {
        'title_es': 'Subvención MOVES III ampliada',
        'title_eu': 'MOVES III diru-laguntza luzatu egin da',
        'summary_es': 'El gobierno amplía MOVES III hasta diciembre. Mantiene los importes actuales.',
        'summary_eu': 'Gobernuak MOVES III abendura arte luzatu du. Egungo zenbatekoak mantentzen ditu.',
        'tags': ['subvencion'],
        'relevance': 'ESPANA',
        'affects_user_plan': True,
    }
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------- dedupe


class DedupeTests(TestCase):
    """Idempotency: re-running refresh on the same URLs must not duplicate."""

    @override_settings(GEMINI_API_KEY='fake')
    def test_existing_url_is_skipped(self):
        NewsArticle.objects.create(
            source='newsapi', source_url='https://example.com/a',
            title_orig='preexisting', published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            relevance=NewsArticle.Relevance.ESPANA,
        )
        raws = [_raw('https://example.com/a'), _raw('https://example.com/b')]

        with mock.patch('apps.mubil.news.services.sources.fetch_all', return_value=raws), \
             mock.patch('apps.mubil.news.services.ask_services._call_gemini_generate',
                        return_value=_gemini_payload()):
            stats = services.refresh(embed=False)

        # Only the new URL gets classified + saved.
        self.assertEqual(stats.fetched, 2)
        self.assertEqual(stats.new, 1)
        self.assertEqual(stats.classified, 1)
        self.assertEqual(NewsArticle.objects.count(), 2)

    @override_settings(GEMINI_API_KEY='fake')
    def test_intra_batch_duplicate_is_collapsed(self):
        """Same URL appearing twice in one fetch (NewsAPI + RSS) → one row."""
        raws = [_raw('https://example.com/x'), _raw('https://example.com/x', source='forocoches_ev')]

        with mock.patch('apps.mubil.news.services.sources.fetch_all', return_value=raws), \
             mock.patch('apps.mubil.news.services.ask_services._call_gemini_generate',
                        return_value=_gemini_payload()):
            stats = services.refresh(embed=False)

        self.assertEqual(stats.new, 1)
        self.assertEqual(NewsArticle.objects.count(), 1)


# ---------------------------------------------------------------- classify


class ClassifyTests(TestCase):
    @override_settings(GEMINI_API_KEY='fake')
    def test_fenced_json_is_parsed(self):
        """Gemini sometimes wraps JSON in ```json blocks despite the prompt."""
        fenced = "```json\n" + _gemini_payload() + "\n```"
        with mock.patch('apps.mubil.news.services.ask_services._call_gemini_generate',
                        return_value=fenced):
            data = services.classify_article(_raw('https://example.com/c'))
        self.assertIsNotNone(data)
        self.assertEqual(data['relevance'], 'ESPANA')

    @override_settings(GEMINI_API_KEY='fake')
    def test_invalid_relevance_falls_back_to_global(self):
        with mock.patch('apps.mubil.news.services.ask_services._call_gemini_generate',
                        return_value=_gemini_payload(relevance='MARTE')):
            data = services.classify_article(_raw('https://example.com/d'))
        self.assertEqual(data['relevance'], 'GLOBAL')

    @override_settings(GEMINI_API_KEY='fake')
    def test_non_json_returns_none(self):
        with mock.patch('apps.mubil.news.services.ask_services._call_gemini_generate',
                        return_value='Lo siento, no puedo responder.'):
            data = services.classify_article(_raw('https://example.com/e'))
        self.assertIsNone(data)


# ---------------------------------------------------------------- staleness


class StalenessTests(TestCase):
    def test_empty_cache_is_stale(self):
        stale, age = services.is_cache_stale()
        self.assertTrue(stale)
        self.assertIsNone(age)

    @override_settings(NEWS_CACHE_HOURS=6)
    def test_fresh_row_is_not_stale(self):
        NewsArticle.objects.create(
            source='newsapi', source_url='https://example.com/fresh',
            title_orig='x', published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            relevance=NewsArticle.Relevance.GLOBAL,
        )
        stale, age = services.is_cache_stale()
        self.assertFalse(stale)
        self.assertIsNotNone(age)
