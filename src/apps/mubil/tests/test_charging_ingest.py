"""Tests for the charging-station ingest pipeline (MITECO CSV + OCM).

HTTP (OCM) is mocked. The MITECO branch reads a tiny CSV written into a tmp
path so the bundled snapshot is not touched. To exercise either branch live:

    python manage.py ingest_charging_stations --source miteco --dry-run
    python manage.py ingest_charging_stations --source ocm    --dry-run
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from apps.mubil.data import charging_ingest, openchargemap_client
from apps.mubil.models import ChargingStation


# ─────────────────────────────────────────────── MITECO CSV fixture


MITECO_CSV_HEADER = (
    "IdPuntoRecarga|Operador|Direccion|CodPostal|Provincia|Municipio|"
    "Localizacion|CoordenadaXDec|CoordenadaYDec|PotenciaMaxima"
)

# Mix of EH (Bizkaia, Gipuzkoa, Araba/Alava, Navarra), one non-EH (Madrid)
# and one malformed row (missing coords) to exercise the skip branches.
MITECO_CSV_ROWS = [
    "ES*IBD*E001|IBERDROLA|Retuerto,68|48903|BIZKAIA|BARAKALDO|EN LA CALLE|-3.0046|43.2871|50.00",
    "ES*IBD*E002|IBERDROLA|Av Tolosa 1|20018|GIPUZKOA|DONOSTIA|EN LA CALLE|-1.985|43.318|22.00",
    "ES*IBD*E003|IBERDROLA|Calle Foru 1|01001|ARABA|VITORIA|EN LA CALLE|-2.672|42.846|11.00",
    "ES*IBD*E004|IBERDROLA|Pamplona Centro|31001|NAVARRA|PAMPLONA|EN LA CALLE|-1.643|42.815|22.00",
    # Accented Álava → must normalise to ARABA.
    "ES*IBD*E005|IBERDROLA|Llodio Centro|01400|ÁLAVA|LLODIO|EN LA CALLE|-2.962|43.144|150.00",
    # Non-EH — must be skipped when eh_only=True.
    "ES*IBD*E006|IBERDROLA|San Pablo,51|28823|MADRID|COSLADA|EN LA CALLE|-3.532|40.431|22.00",
    # Missing coordinates → must be skipped silently.
    "ES*IBD*E007|IBERDROLA|||48903|BIZKAIA|BARAKALDO|EN LA CALLE|||",
    # Missing IdPuntoRecarga → must be skipped silently.
    "|IBERDROLA|x|48903|BIZKAIA|BARAKALDO|EN LA CALLE|-3.0|43.3|22.00",
]


def _write_csv(tmp_path: Path) -> Path:
    """Materialise the MITECO fixture in a tmp dir, return its path."""
    p = tmp_path / "PuntosCarga.csv"
    p.write_text(
        "\r\n".join([MITECO_CSV_HEADER, *MITECO_CSV_ROWS]),
        encoding="latin-1",
    )
    return p


# ─────────────────────────────────────────────── OCM payload fixture


OCM_SAMPLE_PAYLOAD = [
    {
        "ID": 12345,
        "AddressInfo": {
            "Title": "Donostia Parking",
            "AddressLine1": "Av Ejemplo 1",
            "Town": "DONOSTIA",
            "Postcode": "20018",
            "Latitude": 43.319,
            "Longitude": -1.986,
        },
        "OperatorInfo": {"Title": "Iberdrola"},
        "Connections": [
            {"PowerKW": 22, "ConnectionType": {"Title": "Type 2"}},
            {"PowerKW": 50, "ConnectionType": {"Title": "CCS2"}},
        ],
        "DateLastVerified": "2026-05-10T08:00:00Z",
        "DateLastStatusUpdate": "2026-05-12T08:00:00Z",
    },
    {
        "ID": 99999,
        "AddressInfo": {
            "Title": "Bilbao Centro",
            "AddressLine1": "Plaza X",
            "Town": "BILBAO",
            "Postcode": "48001",
            "Latitude": 43.262,
            "Longitude": -2.935,
        },
        "OperatorInfo": {"Title": "EVERA"},
        "Connections": [],
        "DateLastVerified": None,
        "DateLastStatusUpdate": None,
    },
    # Malformed — no AddressInfo. Must be dropped silently.
    {"ID": 1, "Connections": []},
    # Malformed — no ID. Must be dropped silently.
    {"AddressInfo": {"Latitude": 43, "Longitude": -2}},
]


def _mock_response(payload=None, status=200):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else OCM_SAMPLE_PAYLOAD
    r.text = "" if status < 400 else "boom"
    return r


# ─────────────────────────────────────────────── helpers


class HelperTests(TestCase):
    def test_strip_accents_upper(self):
        self.assertEqual(charging_ingest._strip_accents_upper("Álava"), "ALAVA")
        self.assertEqual(charging_ingest._strip_accents_upper("Gipuzkoa"), "GIPUZKOA")
        self.assertEqual(charging_ingest._strip_accents_upper(""), "")

    def test_to_decimal_kw_handles_comma(self):
        self.assertEqual(charging_ingest._to_decimal_kw("50,00"), Decimal("50.00"))
        self.assertEqual(charging_ingest._to_decimal_kw("22.5"), Decimal("22.50"))
        self.assertIsNone(charging_ingest._to_decimal_kw(""))
        self.assertIsNone(charging_ingest._to_decimal_kw("bad"))


# ─────────────────────────────────────────────── MITECO ingest


class IngestMitecoCsvTests(TestCase):
    def setUp(self):
        # Each test writes its own tmp CSV — keeps the bundled file untouched.
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.csv_path = _write_csv(Path(self._tmpdir.name))

    def test_filters_to_eh_provinces(self):
        stats = charging_ingest.ingest_miteco_csv(csv_path=self.csv_path, eh_only=True)
        # 5 EH rows (Bizkaia, Gipuzkoa, Araba, Navarra, Álava).
        self.assertEqual(stats.fetched, 5)
        self.assertEqual(stats.created, 5)
        # Madrid + the two malformed rows count as skipped.
        self.assertEqual(stats.skipped, 3)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(ChargingStation.objects.filter(source="miteco").count(), 5)

    def test_all_spain_loads_madrid_too(self):
        stats = charging_ingest.ingest_miteco_csv(csv_path=self.csv_path, eh_only=False)
        # Madrid joins the 5 EH rows; the 2 malformed rows still skip.
        self.assertEqual(stats.fetched, 6)
        self.assertEqual(stats.skipped, 2)

    def test_dry_run_makes_no_writes(self):
        stats = charging_ingest.ingest_miteco_csv(csv_path=self.csv_path, dry_run=True)
        self.assertEqual(stats.fetched, 5)
        self.assertEqual(stats.created, 0)
        self.assertEqual(ChargingStation.objects.count(), 0)

    def test_idempotent_rerun(self):
        charging_ingest.ingest_miteco_csv(csv_path=self.csv_path)
        stats = charging_ingest.ingest_miteco_csv(csv_path=self.csv_path)
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 5)
        self.assertEqual(ChargingStation.objects.filter(source="miteco").count(), 5)

    def test_missing_file_marks_error(self):
        stats = charging_ingest.ingest_miteco_csv(csv_path=Path("/tmp/does-not-exist.csv"))
        self.assertEqual(stats.errors, 1)
        self.assertEqual(stats.fetched, 0)

    def test_geom_lonlat_order_and_power_parsed(self):
        charging_ingest.ingest_miteco_csv(csv_path=self.csv_path)
        s = ChargingStation.objects.get(source="miteco", external_id="ES*IBD*E001")
        # Point(x=lon, y=lat) with SRID 4326.
        self.assertAlmostEqual(s.geom.x, -3.0046, places=3)
        self.assertAlmostEqual(s.geom.y, 43.2871, places=3)
        self.assertEqual(s.power_kw, Decimal("50.00"))
        self.assertEqual(s.operator, "IBERDROLA")
        self.assertIsNotNone(s.last_seen_at)


# ─────────────────────────────────────────────── OCM client (parsing)


class OCMParseTests(TestCase):
    def test_parse_payload_drops_malformed(self):
        recs = openchargemap_client.parse_payload(OCM_SAMPLE_PAYLOAD)
        self.assertEqual(len(recs), 2)
        self.assertEqual({r.external_id for r in recs}, {"ocm-12345", "ocm-99999"})

    def test_max_power_taken_from_connections(self):
        recs = openchargemap_client.parse_payload(OCM_SAMPLE_PAYLOAD)
        donostia = next(r for r in recs if r.external_id == "ocm-12345")
        self.assertEqual(donostia.power_kw, Decimal("50.00"))
        self.assertEqual(len(donostia.connectors), 2)

    def test_no_connections_returns_none_power(self):
        recs = openchargemap_client.parse_payload(OCM_SAMPLE_PAYLOAD)
        bilbao = next(r for r in recs if r.external_id == "ocm-99999")
        self.assertIsNone(bilbao.power_kw)
        self.assertEqual(bilbao.connectors, [])

    def test_iso8601_zulu_parsed(self):
        recs = openchargemap_client.parse_payload(OCM_SAMPLE_PAYLOAD)
        donostia = next(r for r in recs if r.external_id == "ocm-12345")
        self.assertIsNotNone(donostia.last_verified_at)
        # Most recent of DateLastVerified vs DateLastStatusUpdate.
        self.assertEqual(donostia.last_verified_at.year, 2026)
        self.assertEqual(donostia.last_verified_at.day, 12)


# ─────────────────────────────────────────────── OCM ingest (HTTP mocked)


class IngestOpenChargeMapTests(TestCase):
    @mock.patch("apps.mubil.data.openchargemap_client.requests.get")
    def test_creates_stations(self, get_mock):
        get_mock.return_value = _mock_response()

        stats = charging_ingest.ingest_openchargemap(api_key="test-key")

        self.assertEqual(stats.fetched, 2)
        self.assertEqual(stats.created, 2)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(ChargingStation.objects.filter(source="ocm").count(), 2)
        s = ChargingStation.objects.get(external_id="ocm-12345")
        self.assertEqual(s.operator, "Iberdrola")
        self.assertEqual(s.power_kw, Decimal("50.00"))

    @mock.patch("apps.mubil.data.openchargemap_client.requests.get")
    def test_idempotent_rerun_updates(self, get_mock):
        get_mock.return_value = _mock_response()
        charging_ingest.ingest_openchargemap(api_key="test-key")

        stats = charging_ingest.ingest_openchargemap(api_key="test-key")
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 2)

    @mock.patch("apps.mubil.data.openchargemap_client.requests.get")
    def test_dry_run_makes_no_writes(self, get_mock):
        get_mock.return_value = _mock_response()
        stats = charging_ingest.ingest_openchargemap(api_key="test-key", dry_run=True)
        self.assertEqual(stats.fetched, 2)
        self.assertEqual(ChargingStation.objects.count(), 0)

    @mock.patch("apps.mubil.data.openchargemap_client.requests.get")
    def test_http_error_increments_errors_counter(self, get_mock):
        get_mock.return_value = _mock_response(status=500)
        stats = charging_ingest.ingest_openchargemap(api_key="test-key")
        self.assertEqual(stats.errors, 1)
        self.assertEqual(ChargingStation.objects.count(), 0)

    @override_settings(OPENCHARGEMAP_API_KEY="")
    def test_missing_key_noops_gracefully(self):
        stats = charging_ingest.ingest_openchargemap()
        # No HTTP call, no error counter — the cron is allowed to run dry.
        self.assertEqual(stats.fetched, 0)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(ChargingStation.objects.count(), 0)

    @override_settings(OPENCHARGEMAP_API_KEY="from-settings")
    @mock.patch("apps.mubil.data.openchargemap_client.requests.get")
    def test_picks_key_from_settings(self, get_mock):
        get_mock.return_value = _mock_response(payload=[])
        charging_ingest.ingest_openchargemap()
        # The header must carry the key from settings, not None.
        _args, kwargs = get_mock.call_args
        self.assertEqual(kwargs["headers"]["X-API-Key"], "from-settings")
