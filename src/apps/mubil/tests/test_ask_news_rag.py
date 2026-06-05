"""Tests for Fase 3 — news embeddings mixed into the `ask` RAG.

Covers:
  - retrieve_news_topk returns RetrievedDoc with kind='news' + ISO date.
  - News without embedding are excluded.
  - answer() merges docs + news by score and keeps the top-k.
  - compose_prompt distinguishes DATASET vs NOTICIA in chunk headers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from django.test import TestCase, override_settings

from apps.mubil.ask import services
from apps.mubil.models import MobilityDocument, NewsArticle


def _news(url, *, title='Subv MOVES III', embedding=None,
          published=datetime(2026, 6, 4, tzinfo=timezone.utc)):
    return NewsArticle.objects.create(
        source='newsapi',
        source_url=url,
        title_orig=title,
        title_es=title,
        title_eu=f'{title} EU',
        summary_es='Resumen de la noticia.',
        summary_eu='Berriaren laburpena.',
        published_at=published,
        relevance=NewsArticle.Relevance.ESPANA,
        tags=['subvencion'],
        affects_user_plan=True,
        embedding=embedding,
    )


def _doc(i, *, content='Contenido oficial.', embedding=None):
    return MobilityDocument.objects.create(
        title=f'Doc {i}',
        source_url=f'https://example.com/doc/{i}',
        source_type=MobilityDocument.SourceType.DATASET,
        content=content,
        content_hash=f'hash-{i}',
        embedding=embedding,
    )


class RetrieveNewsTopkTests(TestCase):

    def test_kind_and_date_populated(self):
        vec = [1.0] + [0.0] * 767
        _news('https://x/n1', embedding=vec)
        result = services.retrieve_news_topk(vec, k=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].kind, 'news')
        self.assertEqual(result[0].date, '2026-06-04')
        self.assertEqual(result[0].title, 'Subv MOVES III')

    def test_excludes_unembedded(self):
        vec = [1.0] + [0.0] * 767
        _news('https://x/n1', embedding=vec)
        _news('https://x/n2', embedding=None)
        result = services.retrieve_news_topk(vec, k=5)
        self.assertEqual(len(result), 1)


class ComposePromptKindLabelTests(TestCase):

    def test_dataset_and_news_carry_distinct_headers(self):
        docs = [
            services.RetrievedDoc(
                id=1, title='MOVES III', source_url='https://x/d',
                source_type='dataset', score=0.9, content='ayudas hasta 7000€',
                kind='dataset',
            ),
            services.RetrievedDoc(
                id=2, title='Subvención ampliada', source_url='https://x/n',
                source_type='newsapi', score=0.85, content='Resumen.',
                kind='news', date='2026-06-04',
            ),
        ]
        prompt = services.compose_prompt('¿Cuánto da MOVES III?', docs)
        self.assertIn('[1] Tipo: DATASET (dataset)', prompt)
        self.assertIn('[2] Tipo: NOTICIA (publicada 2026-06-04)', prompt)


@override_settings(GEMINI_API_KEY='fake')
class AnswerMergeTests(TestCase):

    @mock.patch('apps.mubil.ask.services._call_gemini_generate')
    @mock.patch('apps.mubil.ask.services.embeddings.embed_text')
    def test_news_and_docs_merged_and_sorted_by_score(self, embed_mock, gen_mock):
        embed_mock.return_value = [0.0] * 768
        gen_mock.return_value = 'OK'

        doc_lo = services.RetrievedDoc(
            id=10, title='Doc-lo', source_url='https://x/d-lo',
            source_type='dataset', score=0.50, content='c',
        )
        doc_hi = services.RetrievedDoc(
            id=11, title='Doc-hi', source_url='https://x/d-hi',
            source_type='dataset', score=0.90, content='c',
        )
        news_mid = services.RetrievedDoc(
            id=12, title='News-mid', source_url='https://x/n-mid',
            source_type='newsapi', score=0.80, content='c',
            kind='news', date='2026-06-04',
        )

        with mock.patch.object(services, 'retrieve_topk', return_value=[doc_hi, doc_lo]), \
             mock.patch.object(services, 'retrieve_news_topk', return_value=[news_mid]):
            result = services.answer(query='¿algo?', k=3)

        order = [s.id for s in result.sources]
        self.assertEqual(order, [11, 12, 10])

    @mock.patch('apps.mubil.ask.services._call_gemini_generate')
    @mock.patch('apps.mubil.ask.services.embeddings.embed_text')
    def test_low_score_news_filtered_with_min_score(self, embed_mock, gen_mock):
        embed_mock.return_value = [0.0] * 768
        gen_mock.return_value = 'OK'

        noise_news = services.RetrievedDoc(
            id=20, title='Irrelevant', source_url='https://x/n',
            source_type='newsapi', score=0.10, content='c',
            kind='news', date='2026-06-04',
        )
        good_doc = services.RetrievedDoc(
            id=21, title='Doc', source_url='https://x/d',
            source_type='dataset', score=0.70, content='c',
        )

        with mock.patch.object(services, 'retrieve_topk', return_value=[good_doc]), \
             mock.patch.object(services, 'retrieve_news_topk', return_value=[noise_news]):
            result = services.answer(query='¿algo?', k=3)

        self.assertEqual([s.id for s in result.sources], [21])
