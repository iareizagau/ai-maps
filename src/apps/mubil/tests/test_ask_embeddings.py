"""Tests for the embedding pipeline.

Gemini SDK is mocked — these tests do not hit Google's API.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from apps.mubil.ask import embeddings
from apps.mubil.models import MobilityDocument


def _fake_client(values):
    """Build a mock that mimics `google.genai.Client.models.embed_content`."""
    client = mock.Mock()
    embedding_obj = mock.Mock()
    embedding_obj.values = list(values)
    result = mock.Mock()
    result.embeddings = [embedding_obj]
    client.models.embed_content.return_value = result
    return client


def _fake_embed_for_text(text):
    """Deterministic-by-length 768-dim fake embedding."""
    seed = (len(text) % 7) / 10.0
    return [seed] * embeddings.EMBEDDING_DIM


@override_settings(GEMINI_API_KEY="fake-key-for-tests")
class EmbedTextTests(TestCase):
    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_text_returns_768_dim(self, conf_mock):
        client = _fake_client([0.42] * 768)
        conf_mock.return_value = client

        vec = embeddings.embed_text("hola", task_type="RETRIEVAL_DOCUMENT")

        self.assertEqual(len(vec), 768)
        # values were uniform → normalization makes every entry equal to 1/sqrt(768).
        expected = 1.0 / (768**0.5)
        self.assertAlmostEqual(vec[0], expected, places=6)
        client.models.embed_content.assert_called_once()
        _, kwargs = client.models.embed_content.call_args
        self.assertEqual(kwargs["contents"], "hola")
        self.assertEqual(kwargs["config"].task_type, "RETRIEVAL_DOCUMENT")
        self.assertEqual(kwargs["config"].output_dimensionality, 768)

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_text_truncates_long_content(self, conf_mock):
        client = _fake_client([0.1] * 768)
        conf_mock.return_value = client

        long_text = "x" * 20000
        embeddings.embed_text(long_text)

        _, kwargs = client.models.embed_content.call_args
        self.assertEqual(len(kwargs["contents"]), embeddings.MAX_INPUT_CHARS)

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_text_rejects_bad_dimension(self, conf_mock):
        client = _fake_client([0.0] * 100)  # wrong dim
        conf_mock.return_value = client

        with self.assertRaises(embeddings.EmbeddingError):
            embeddings.embed_text("anything")


@override_settings(GEMINI_API_KEY="")
class EmbedTextNoKeyTests(TestCase):
    def test_raises_when_key_missing(self):
        with self.assertRaises(embeddings.EmbeddingError) as ctx:
            embeddings.embed_text("any")
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))


@override_settings(GEMINI_API_KEY="fake-key-for-tests")
class EmbedCorpusTests(TestCase):
    def _make_docs(self, n, *, embedded=False):
        for i in range(n):
            MobilityDocument.objects.create(
                title=f"Doc {i}",
                source_url=f"https://example.com/{i}",
                source_type=MobilityDocument.SourceType.DATASET,
                content=f"Contenido del documento {i} sobre movilidad sostenible.",
                content_hash=f"hash-{i}",
                embedding=([0.1] * 768) if embedded else None,
            )

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_corpus_only_processes_pending(self, conf_mock):
        client = mock.Mock()

        def fake_embed(**kwargs):
            values = _fake_embed_for_text(kwargs["contents"])
            emb = mock.Mock()
            emb.values = values
            r = mock.Mock()
            r.embeddings = [emb]
            return r

        client.models.embed_content.side_effect = fake_embed
        conf_mock.return_value = client

        self._make_docs(3, embedded=False)
        self._make_docs(2, embedded=True)  # should be skipped

        stats = embeddings.embed_corpus(throttle_s=0.0)

        self.assertEqual(stats.total_pending, 3)
        self.assertEqual(stats.embedded, 3)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(client.models.embed_content.call_count, 3)

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_corpus_writes_embedding(self, conf_mock):
        client = _fake_client([0.7] * 768)
        conf_mock.return_value = client

        self._make_docs(1, embedded=False)
        embeddings.embed_corpus(throttle_s=0.0)

        doc = MobilityDocument.objects.first()
        self.assertIsNotNone(doc.embedding)
        # Normalized uniform vector → each component = 1/sqrt(768).
        expected = 1.0 / (768**0.5)
        self.assertAlmostEqual(float(doc.embedding[0]), expected, places=5)

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_corpus_skips_empty_content(self, conf_mock):
        conf_mock.return_value = mock.Mock()

        MobilityDocument.objects.create(
            title="empty",
            source_url="https://example.com/empty",
            source_type=MobilityDocument.SourceType.DATASET,
            content="   ",
            content_hash="empty-hash",
        )

        stats = embeddings.embed_corpus(throttle_s=0.0)

        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.embedded, 0)

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_corpus_counts_errors(self, conf_mock):
        client = mock.Mock()
        client.models.embed_content.side_effect = RuntimeError("boom")
        conf_mock.return_value = client

        self._make_docs(2, embedded=False)
        stats = embeddings.embed_corpus(throttle_s=0.0)

        self.assertEqual(stats.errors, 2)
        self.assertEqual(stats.embedded, 0)
        self.assertEqual(
            MobilityDocument.objects.filter(embedding__isnull=True).count(), 2
        )

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_corpus_respects_limit(self, conf_mock):
        client = _fake_client([0.0] * 768)
        conf_mock.return_value = client

        self._make_docs(5, embedded=False)
        stats = embeddings.embed_corpus(throttle_s=0.0, limit=2)

        self.assertEqual(stats.embedded, 2)
        self.assertEqual(client.models.embed_content.call_count, 2)

    @mock.patch("apps.mubil.ask.embeddings._configure_genai")
    def test_embed_corpus_dry_run_makes_no_calls(self, conf_mock):
        client = mock.Mock()
        conf_mock.return_value = client

        self._make_docs(3, embedded=False)
        stats = embeddings.embed_corpus(throttle_s=0.0, dry_run=True)

        self.assertEqual(stats.embedded, 3)
        client.models.embed_content.assert_not_called()
        self.assertEqual(
            MobilityDocument.objects.filter(embedding__isnull=True).count(), 3
        )
