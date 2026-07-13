"""Tests for the `ask` corpus ingest (CKAN parsing + upsert idempotency).

Network is mocked — these tests do not hit datos.gob.es. To exercise the live
endpoint, run `manage.py ingest_ask_corpus --max-pages=1 --dry-run`.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.mubil.ask import ingest
from apps.mubil.models import MobilityDocument

# A realistic-ish CKAN datos.gob.es payload shape (JSON-LD `_value/_lang`).
SAMPLE_PAYLOAD = {
    "result": {
        "items": [
            {
                "_about": "https://datos.gob.es/catalogo/a-coruna-trafico-1",
                "title": [
                    {"_value": "Datos de tráfico A Coruña", "_lang": "es"},
                    {"_value": "A Coruña traffic data", "_lang": "en"},
                ],
                "description": [
                    {
                        "_value": "Aforos por viario. Actualización diaria.",
                        "_lang": "es",
                    },
                ],
                "keyword": ["tráfico", "aforos", "movilidad"],
            },
            # Missing description → must be skipped
            {
                "_about": "https://datos.gob.es/catalogo/sin-desc",
                "title": [{"_value": "Sin descripción", "_lang": "es"}],
                "keyword": [],
            },
            # Plain-string title (older CKAN entries)
            {
                "_about": "https://datos.gob.es/catalogo/plain-string",
                "title": "Aparcamientos disuasorios Bilbao",
                "description": "Listado de aparcamientos disuasorios del BMB.",
                "keyword": "aparcamiento, bilbao",
            },
        ]
    }
}


class CKANParsingTests(TestCase):
    def test_pick_lang_prefers_requested_language(self):
        values = [
            {"_value": "english", "_lang": "en"},
            {"_value": "español", "_lang": "es"},
        ]
        self.assertEqual(ingest._pick_lang(values, "es"), "español")
        self.assertEqual(ingest._pick_lang(values, "en"), "english")

    def test_pick_lang_falls_back_to_first(self):
        self.assertEqual(
            ingest._pick_lang([{"_value": "x", "_lang": "fr"}], "es"),
            "x",
        )

    def test_pick_lang_handles_plain_string(self):
        self.assertEqual(ingest._pick_lang("plain"), "plain")

    def test_pick_lang_empty(self):
        self.assertEqual(ingest._pick_lang(None), "")
        self.assertEqual(ingest._pick_lang([]), "")

    def test_ckan_to_doc_payload_full_record(self):
        item = SAMPLE_PAYLOAD["result"]["items"][0]
        doc = ingest._ckan_to_doc_payload(item)
        self.assertEqual(doc["title"], "Datos de tráfico A Coruña")
        self.assertIn("Aforos por viario", doc["content"])
        self.assertIn("Keywords: tráfico, aforos, movilidad", doc["content"])
        self.assertEqual(
            doc["source_url"], "https://datos.gob.es/catalogo/a-coruna-trafico-1"
        )

    def test_ckan_to_doc_payload_skips_missing_description(self):
        item = SAMPLE_PAYLOAD["result"]["items"][1]
        self.assertIsNone(ingest._ckan_to_doc_payload(item))

    def test_ckan_to_doc_payload_handles_plain_string_fields(self):
        item = SAMPLE_PAYLOAD["result"]["items"][2]
        doc = ingest._ckan_to_doc_payload(item)
        self.assertEqual(doc["title"], "Aparcamientos disuasorios Bilbao")
        self.assertIn("aparcamiento, bilbao", doc["content"])


class CKANIngestTests(TestCase):
    def _mock_pages(self, *pages):
        """Build a side_effect that returns one page per call, then empty."""
        responses = list(pages) + [{"result": {"items": []}}]
        return mock.Mock(side_effect=responses)

    @mock.patch("apps.mubil.ask.ingest._fetch_ckan_page")
    def test_ingest_creates_documents(self, fetch_mock):
        fetch_mock.side_effect = [SAMPLE_PAYLOAD, {"result": {"items": []}}]

        stats = ingest.ingest_ckan(max_pages=5, page_size=50)

        self.assertEqual(stats.created, 2)  # one skipped (no description)
        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(MobilityDocument.objects.count(), 2)

    @mock.patch("apps.mubil.ask.ingest._fetch_ckan_page")
    def test_ingest_is_idempotent(self, fetch_mock):
        fetch_mock.side_effect = [SAMPLE_PAYLOAD, {"result": {"items": []}}] * 2

        ingest.ingest_ckan(max_pages=5)
        stats2 = ingest.ingest_ckan(max_pages=5)

        self.assertEqual(MobilityDocument.objects.count(), 2)
        self.assertEqual(stats2.created, 0)
        self.assertEqual(stats2.skipped, 3)  # 2 unchanged + 1 still missing desc

    @mock.patch("apps.mubil.ask.ingest._fetch_ckan_page")
    def test_ingest_updates_on_content_change(self, fetch_mock):
        # First run: original content.
        fetch_mock.side_effect = [SAMPLE_PAYLOAD, {"result": {"items": []}}]
        ingest.ingest_ckan(max_pages=5)
        doc = MobilityDocument.objects.get(
            source_url="https://datos.gob.es/catalogo/a-coruna-trafico-1"
        )
        # Simulate an embedding having been generated.
        from pgvector.django import VectorField  # noqa: F401

        doc.embedding = [0.1] * 768
        doc.save(update_fields=["embedding"])

        # Second run: same URL, different description.
        modified = {
            "result": {
                "items": [
                    {
                        "_about": "https://datos.gob.es/catalogo/a-coruna-trafico-1",
                        "title": [
                            {"_value": "Datos de tráfico A Coruña", "_lang": "es"}
                        ],
                        "description": [
                            {
                                "_value": "Aforos por viario. ACTUALIZADO 2026.",
                                "_lang": "es",
                            }
                        ],
                        "keyword": ["tráfico"],
                    }
                ]
            }
        }
        fetch_mock.side_effect = [modified, {"result": {"items": []}}]
        stats = ingest.ingest_ckan(max_pages=5)

        doc.refresh_from_db()
        self.assertEqual(stats.updated, 1)
        self.assertIn("ACTUALIZADO 2026", doc.content)
        self.assertIsNone(doc.embedding)  # cleared for re-embedding

    @mock.patch("apps.mubil.ask.ingest._fetch_ckan_page")
    def test_ingest_dry_run_does_not_write(self, fetch_mock):
        fetch_mock.side_effect = [SAMPLE_PAYLOAD, {"result": {"items": []}}]

        stats = ingest.ingest_ckan(max_pages=5, dry_run=True)

        self.assertEqual(MobilityDocument.objects.count(), 0)
        self.assertEqual(stats.fetched, 3)

    @mock.patch("apps.mubil.ask.ingest._fetch_ckan_page")
    def test_ingest_stops_on_empty_page(self, fetch_mock):
        fetch_mock.side_effect = [SAMPLE_PAYLOAD, {"result": {"items": []}}]

        stats = ingest.ingest_ckan(max_pages=10)

        self.assertEqual(stats.pages, 1)
        self.assertEqual(fetch_mock.call_count, 2)
