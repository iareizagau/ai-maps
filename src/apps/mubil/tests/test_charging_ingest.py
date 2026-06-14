"""Tests for the charging-station ingest pipeline (MITECO CSV + OCM + DGT NAP).

HTTP (OCM, DGT NAP) is mocked. The MITECO branch reads a tiny CSV written
into a tmp path so the bundled snapshot is not touched. To exercise live:

    python manage.py ingest_charging_stations --source miteco  --dry-run
    python manage.py ingest_charging_stations --source ocm     --dry-run
    python manage.py ingest_charging_stations --source dgt_nap --dry-run
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from apps.mubil.data import charging_ingest, dgt_nap_client, openchargemap_client
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


# ─────────────────────────────────────────────── DGT NAP DATEX II fixture


# Minimal synthetic EnergyInfrastructureTablePublication with three sites:
#   - SITE-EH-1  Bizkaia, two connectors (22 kW + 50 kW) → max power = 50 kW
#   - SITE-EH-2  Gipuzkoa, one connector, missing lastUpdated
#   - SITE-OUT   Barcelona, must be filtered out when eh_only=True
#   - SITE-NOCOORD  Bizkaia but no lat/lon → must be skipped
DGT_NAP_FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<d2:payload xmlns:d2="http://datex2.eu/schema/3/d2Payload"
            xmlns:com="http://datex2.eu/schema/3/common"
            xmlns:loc="http://datex2.eu/schema/3/locationReferencing"
            xmlns:locx="http://datex2.eu/schema/3/locationExtension"
            xmlns:fac="http://datex2.eu/schema/3/facilities"
            xmlns:egi="http://datex2.eu/schema/3/energyInfrastructure">
  <egi:energyInfrastructureTable id="ELECTROLINERAS" version="1">

    <egi:energyInfrastructureSite id="SITE-EH-1" version="">
      <fac:lastUpdated>2026-06-09T10:57:18.000+02:00</fac:lastUpdated>
      <fac:locationReference>
        <loc:_locationReferenceExtension>
          <loc:facilityLocation>
            <locx:address>
              <locx:addressLine order="1">
                <locx:type>generalTextLine</locx:type>
                <locx:text><com:values><com:value lang="es">Dirección: Gran Vía 1</com:value></com:values></locx:text>
              </locx:addressLine>
              <locx:addressLine order="3">
                <locx:type>generalTextLine</locx:type>
                <locx:text><com:values><com:value lang="es">Provincia: Bizkaia</com:value></com:values></locx:text>
              </locx:addressLine>
            </locx:address>
          </loc:facilityLocation>
        </loc:_locationReferenceExtension>
        <loc:coordinatesForDisplay>
          <loc:latitude>43.262</loc:latitude>
          <loc:longitude>-2.935</loc:longitude>
        </loc:coordinatesForDisplay>
      </fac:locationReference>
      <fac:operator><fac:name><com:values><com:value lang="es">IBERDROLA</com:value></com:values></fac:name></fac:operator>
      <egi:energyInfrastructureStation id="SITE-EH-1_1" version="">
        <egi:refillPoint xsi:type="egi:ElectricChargingPoint" id="r1" version=""
                         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <egi:connector>
            <egi:connectorType>iec62196T2</egi:connectorType>
            <egi:chargingMode>mode3AC3p</egi:chargingMode>
            <egi:connectorFormat>socket</egi:connectorFormat>
            <egi:maxPowerAtSocket>22000.0</egi:maxPowerAtSocket>
          </egi:connector>
          <egi:connector>
            <egi:connectorType>iec62196T2COMBO</egi:connectorType>
            <egi:chargingMode>mode4</egi:chargingMode>
            <egi:connectorFormat>cable</egi:connectorFormat>
            <egi:maxPowerAtSocket>50000.0</egi:maxPowerAtSocket>
          </egi:connector>
        </egi:refillPoint>
      </egi:energyInfrastructureStation>
    </egi:energyInfrastructureSite>

    <egi:energyInfrastructureSite id="SITE-EH-2" version="">
      <fac:locationReference>
        <loc:_locationReferenceExtension>
          <loc:facilityLocation>
            <locx:address>
              <locx:addressLine order="3">
                <locx:type>generalTextLine</locx:type>
                <locx:text><com:values><com:value lang="es">Provincia: Gipuzkoa</com:value></com:values></locx:text>
              </locx:addressLine>
            </locx:address>
          </loc:facilityLocation>
        </loc:_locationReferenceExtension>
        <loc:coordinatesForDisplay>
          <loc:latitude>43.319</loc:latitude>
          <loc:longitude>-1.986</loc:longitude>
        </loc:coordinatesForDisplay>
      </fac:locationReference>
      <egi:energyInfrastructureStation id="SITE-EH-2_1" version="">
        <egi:refillPoint xsi:type="egi:ElectricChargingPoint" id="r2" version=""
                         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <egi:connector>
            <egi:connectorType>chademo</egi:connectorType>
            <egi:maxPowerAtSocket>11000.0</egi:maxPowerAtSocket>
          </egi:connector>
        </egi:refillPoint>
      </egi:energyInfrastructureStation>
    </egi:energyInfrastructureSite>

    <egi:energyInfrastructureSite id="SITE-OUT" version="">
      <fac:locationReference>
        <loc:_locationReferenceExtension>
          <loc:facilityLocation>
            <locx:address>
              <locx:addressLine order="3">
                <locx:type>generalTextLine</locx:type>
                <locx:text><com:values><com:value lang="es">Provincia: Barcelona</com:value></com:values></locx:text>
              </locx:addressLine>
            </locx:address>
          </loc:facilityLocation>
        </loc:_locationReferenceExtension>
        <loc:coordinatesForDisplay>
          <loc:latitude>41.385</loc:latitude>
          <loc:longitude>2.173</loc:longitude>
        </loc:coordinatesForDisplay>
      </fac:locationReference>
    </egi:energyInfrastructureSite>

    <egi:energyInfrastructureSite id="SITE-NOCOORD" version="">
      <fac:locationReference>
        <loc:_locationReferenceExtension>
          <loc:facilityLocation>
            <locx:address>
              <locx:addressLine order="3">
                <locx:type>generalTextLine</locx:type>
                <locx:text><com:values><com:value lang="es">Provincia: Bizkaia</com:value></com:values></locx:text>
              </locx:addressLine>
            </locx:address>
          </loc:facilityLocation>
        </loc:_locationReferenceExtension>
      </fac:locationReference>
    </egi:energyInfrastructureSite>

  </egi:energyInfrastructureTable>
</d2:payload>
"""


def _fixture_stream() -> io.BytesIO:
    return io.BytesIO(DGT_NAP_FIXTURE_XML.encode("utf-8"))


# ─────────────────────────────────────────────── DGT NAP parser


class DGTNAPParseTests(TestCase):
    def test_filters_to_eh_provinces(self):
        recs = dgt_nap_client.parse_stream(_fixture_stream(), eh_only=True)
        # SITE-OUT (Barcelona) dropped, SITE-NOCOORD dropped (no lat/lon).
        self.assertEqual({r.external_id for r in recs},
                         {"dgt_nap-SITE-EH-1", "dgt_nap-SITE-EH-2"})

    def test_araba_alava_hyphenated_form_matches(self):
        """DGT publishes Araba as "Araba/Álava" — the only EH province with
        a non-bare label. Regression guard."""
        xml = DGT_NAP_FIXTURE_XML.replace(
            "Provincia: Bizkaia", "Provincia: Araba/Álava"
        )
        recs = dgt_nap_client.parse_stream(io.BytesIO(xml.encode("utf-8")),
                                           eh_only=True)
        self.assertIn("dgt_nap-SITE-EH-1", {r.external_id for r in recs})

    def test_eh_only_false_keeps_non_eh(self):
        recs = dgt_nap_client.parse_stream(_fixture_stream(), eh_only=False)
        # 3 sites have coords (SITE-NOCOORD still dropped regardless of filter).
        self.assertEqual(len(recs), 3)
        self.assertIn("dgt_nap-SITE-OUT", {r.external_id for r in recs})

    def test_watts_converted_to_kw_and_max_taken(self):
        recs = dgt_nap_client.parse_stream(_fixture_stream(), eh_only=True)
        eh1 = next(r for r in recs if r.external_id == "dgt_nap-SITE-EH-1")
        # 22000 W + 50000 W → max 50.00 kW.
        self.assertEqual(eh1.power_kw, Decimal("50.00"))
        self.assertEqual(len(eh1.connectors), 2)
        self.assertEqual(eh1.connectors[0]["kw"], "22.00")
        self.assertEqual(eh1.connectors[1]["kw"], "50.00")
        self.assertEqual(eh1.connectors[1]["type"], "iec62196T2COMBO")

    def test_geom_lonlat_and_operator(self):
        recs = dgt_nap_client.parse_stream(_fixture_stream(), eh_only=True)
        eh1 = next(r for r in recs if r.external_id == "dgt_nap-SITE-EH-1")
        self.assertAlmostEqual(eh1.latitude, 43.262, places=3)
        self.assertAlmostEqual(eh1.longitude, -2.935, places=3)
        self.assertEqual(eh1.operator, "IBERDROLA")
        # Address concatenates the addressLine values in document order.
        self.assertIn("Gran Vía 1", eh1.address)
        self.assertIn("Bizkaia", eh1.address)

    def test_last_updated_parsed_or_none(self):
        recs = dgt_nap_client.parse_stream(_fixture_stream(), eh_only=True)
        eh1 = next(r for r in recs if r.external_id == "dgt_nap-SITE-EH-1")
        eh2 = next(r for r in recs if r.external_id == "dgt_nap-SITE-EH-2")
        self.assertIsNotNone(eh1.last_verified_at)
        self.assertEqual(eh1.last_verified_at.year, 2026)
        # SITE-EH-2 has no fac:lastUpdated → must be None.
        self.assertIsNone(eh2.last_verified_at)


# ─────────────────────────────────────────────── DGT NAP ingest


class IngestDGTNAPTests(TestCase):
    def setUp(self):
        # Force fetch_and_parse to return our fixture-parsed records — keeps
        # the test fully offline.
        self.records = dgt_nap_client.parse_stream(_fixture_stream(), eh_only=True)
        patcher = mock.patch(
            "apps.mubil.data.dgt_nap_client.fetch_and_parse",
            return_value=self.records,
        )
        self.fetch_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_creates_stations(self):
        stats = charging_ingest.ingest_dgt_nap()
        self.assertEqual(stats.fetched, 2)
        self.assertEqual(stats.created, 2)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(ChargingStation.objects.filter(source="dgt_nap").count(), 2)
        s = ChargingStation.objects.get(external_id="dgt_nap-SITE-EH-1")
        self.assertEqual(s.power_kw, Decimal("50.00"))
        self.assertEqual(s.operator, "IBERDROLA")
        self.assertIsNotNone(s.last_seen_at)

    def test_idempotent_rerun(self):
        charging_ingest.ingest_dgt_nap()
        stats = charging_ingest.ingest_dgt_nap()
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 2)
        self.assertEqual(ChargingStation.objects.filter(source="dgt_nap").count(), 2)

    def test_dry_run_makes_no_writes(self):
        stats = charging_ingest.ingest_dgt_nap(dry_run=True)
        self.assertEqual(stats.fetched, 2)
        self.assertEqual(ChargingStation.objects.count(), 0)

    def test_fetch_error_increments_errors_counter(self):
        self.fetch_mock.side_effect = dgt_nap_client.DGTNAPError("boom")
        stats = charging_ingest.ingest_dgt_nap()
        self.assertEqual(stats.errors, 1)
        self.assertEqual(stats.fetched, 0)
        self.assertEqual(ChargingStation.objects.count(), 0)
