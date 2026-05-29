"""Tests for the MINCOTUR fuel-station ingest pipeline.

HTTP is mocked — these tests do not hit sedeaplicaciones.minetur.gob.es. To
exercise the live endpoint:  `python manage.py ingest_fuel --dry-run`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import mock

from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.mubil.data import fuel_ingest, mincotur_client
from apps.mubil.models import FuelStation


# Two well-formed stations + one malformed row to exercise the parser's skip
# branches (missing IDEESS, missing coordinates, empty fuel cells).
SAMPLE_PAYLOAD = {
    "Fecha": "27/05/2026 18:42:11",
    "ListaEESSPrecio": [
        {
            "C.P.": "20018",
            "Dirección": "AV EJEMPLO 1",
            "Horario": "L-D: 24H",
            "IDEESS": "1234",
            "IDProvincia": "20",
            "Latitud": "43,318",
            "Longitud (WGS84)": "-1,985",
            "Municipio": "DONOSTIA / SAN SEBASTIAN",
            "Precio Gasolina 95 E5": "1,569",
            "Precio Gasoleo A": "1,489",
            "Precio Gasolina 98 E5": "",       # empty → dropped
            "Provincia": "GIPUZKOA",
            "Rótulo": "REPSOL",
            "Tipo Venta": "P",
        },
        {
            "C.P.": "20018",
            "Dirección": "C. EJEMPLO 2",
            "IDEESS": "5678",
            "Latitud": "43,320",
            "Longitud (WGS84)": "-1,990",
            "Municipio": "DONOSTIA / SAN SEBASTIAN",
            "Precio Gasolina 95 E5": "1,609",
            "Precio Gasoleo A": "1,529",
            "Rótulo": "CEPSA",
            "Tipo Venta": "P",
        },
        # Malformed — missing IDEESS, should be dropped silently.
        {"Latitud": "43,0", "Longitud (WGS84)": "-2,0", "Rótulo": "X"},
        # Malformed — non-numeric coords, should be dropped.
        {"IDEESS": "9999", "Latitud": "??", "Longitud (WGS84)": ""},
    ],
}


def _mock_response(payload=None, status=200):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else SAMPLE_PAYLOAD
    r.text = "" if status < 400 else "boom"
    return r


def _make_session_mock(payload=None, status=200):
    """Build a mock ``_session()`` whose ``.get()`` returns the desired response."""
    session = mock.Mock()
    session.get.return_value = _mock_response(payload=payload, status=status)
    return session


# ─────────────────────────────────────────────── parser


class ParserTests(TestCase):
    def test_decimal_comma_normalized(self):
        self.assertEqual(mincotur_client._to_decimal_eur("1,659"), Decimal("1.659"))
        self.assertEqual(mincotur_client._to_decimal_eur("1.659"), Decimal("1.659"))

    def test_empty_and_invalid_return_none(self):
        self.assertIsNone(mincotur_client._to_decimal_eur(""))
        self.assertIsNone(mincotur_client._to_decimal_eur(None))
        self.assertIsNone(mincotur_client._to_decimal_eur("nope"))

    def test_coord_comma_normalized(self):
        self.assertEqual(mincotur_client._to_float_coord("43,318"), 43.318)
        self.assertIsNone(mincotur_client._to_float_coord(""))
        self.assertIsNone(mincotur_client._to_float_coord("xx"))

    def test_parse_record_drops_rows_without_id_or_coords(self):
        # Missing IDEESS
        self.assertIsNone(mincotur_client._parse_record({"Latitud": "1,0", "Longitud (WGS84)": "1,0"}))
        # Missing coords
        self.assertIsNone(mincotur_client._parse_record({"IDEESS": "1"}))

    def test_parse_record_keeps_only_reported_fuels(self):
        rec = mincotur_client._parse_record(SAMPLE_PAYLOAD["ListaEESSPrecio"][0])
        self.assertIsNotNone(rec)
        self.assertEqual(set(rec.prices), {"gasolina_95_e5", "gasoleo_a"})
        self.assertEqual(rec.prices["gasolina_95_e5"], Decimal("1.569"))


# ─────────────────────────────────────────────── HTTP client


class FetchProvinceTests(TestCase):
    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_parses_valid_rows_and_drops_bad_ones(self, get_mock):
        get_mock.return_value = _make_session_mock()

        recs = mincotur_client.fetch_province("20")

        self.assertEqual(len(recs), 2)
        self.assertEqual({r.ideess for r in recs}, {1234, 5678})
        self.assertEqual(recs[0].municipality_name, "DONOSTIA / SAN SEBASTIAN")
        self.assertEqual(recs[0].postal_code, "20018")
        self.assertEqual(recs[0].prices["gasolina_95_e5"], Decimal("1.569"))

    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_pads_province_code(self, get_mock):
        get_mock.return_value = _make_session_mock()
        mincotur_client.fetch_province(20)  # int, no zero padding
        args, _ = get_mock.return_value.get.call_args
        # No trailing slash — IIS rejects it with 404.
        self.assertTrue(args[0].endswith("FiltroProvincia/20"))

    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_http_error_raises(self, get_mock):
        get_mock.return_value = _make_session_mock(status=500)
        with self.assertRaises(mincotur_client.MincoturError):
            mincotur_client.fetch_province("20")

    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_missing_list_raises(self, get_mock):
        get_mock.return_value = _make_session_mock(payload={"Fecha": "x"})
        with self.assertRaises(mincotur_client.MincoturError):
            mincotur_client.fetch_province("20")


# ─────────────────────────────────────────────── ingest orchestration


class IngestProvincesTests(TestCase):
    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_creates_stations(self, get_mock):
        get_mock.return_value = _make_session_mock()

        stats = fuel_ingest.ingest_provinces(prov_codes=("20",))

        self.assertEqual(stats.provinces, 1)
        self.assertEqual(stats.fetched, 2)
        self.assertEqual(stats.created, 2)
        self.assertEqual(stats.errors, 0)
        self.assertEqual(FuelStation.objects.count(), 2)

        s = FuelStation.objects.get(ideess=1234)
        self.assertEqual(s.brand, "REPSOL")
        # JSON values stored as strings to keep Decimal round-trip stable.
        self.assertEqual(s.prices["gasolina_95_e5"], "1.569")
        # geom is a Point with SRID 4326, lon/lat order is x/y.
        self.assertAlmostEqual(s.geom.x, -1.985, places=3)
        self.assertAlmostEqual(s.geom.y, 43.318, places=3)
        self.assertIsNotNone(s.last_seen_at)

    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_idempotent_rerun_updates(self, get_mock):
        get_mock.return_value = _make_session_mock()
        fuel_ingest.ingest_provinces(prov_codes=("20",))

        # Second run — same payload → 2 updates, 0 creates.
        stats = fuel_ingest.ingest_provinces(prov_codes=("20",))
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 2)
        self.assertEqual(FuelStation.objects.count(), 2)

    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_dry_run_makes_no_writes(self, get_mock):
        get_mock.return_value = _make_session_mock()
        stats = fuel_ingest.ingest_provinces(prov_codes=("20",), dry_run=True)
        self.assertEqual(stats.fetched, 2)
        self.assertEqual(stats.created, 0)
        self.assertEqual(FuelStation.objects.count(), 0)

    @mock.patch("apps.mubil.data.mincotur_client._session")
    def test_http_error_increments_errors_counter(self, get_mock):
        get_mock.return_value = _make_session_mock(status=500)
        stats = fuel_ingest.ingest_provinces(prov_codes=("20",))
        self.assertEqual(stats.errors, 1)
        self.assertEqual(FuelStation.objects.count(), 0)


# ─────────────────────────────────────────────── queries (advisor wiring)


def _make_station(
    *,
    ideess: int,
    cp: str,
    municipality: str,
    prices: dict,
    last_seen_hours_ago: int = 1,
    lon: float = -1.985,
    lat: float = 43.318,
) -> FuelStation:
    return FuelStation.objects.create(
        ideess=ideess,
        brand="DEMO",
        address="addr",
        municipality_name=municipality,
        postal_code=cp,
        geom=Point(lon, lat, srid=4326),
        prices=prices,
        last_seen_at=datetime.now(tz=timezone.utc) - timedelta(hours=last_seen_hours_ago),
    )


class FuelQueryTests(TestCase):
    def test_recent_avg_returns_none_when_table_empty(self):
        self.assertIsNone(fuel_ingest.recent_avg_eur_l(fuel_key="gasolina_95_e5"))

    def test_recent_avg_averages_across_stations(self):
        _make_station(ideess=1, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.500"})
        _make_station(ideess=2, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.600"})
        avg = fuel_ingest.recent_avg_eur_l(fuel_key="gasolina_95_e5")
        self.assertEqual(avg, Decimal("1.550"))

    def test_recent_avg_skips_stations_without_the_fuel(self):
        _make_station(ideess=1, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.500"})
        _make_station(ideess=2, cp="20018", municipality="Donostia",
                      prices={"gasoleo_a": "1.400"})  # no gasolina
        avg = fuel_ingest.recent_avg_eur_l(fuel_key="gasolina_95_e5")
        self.assertEqual(avg, Decimal("1.500"))

    def test_recent_avg_filters_by_postal_code(self):
        _make_station(ideess=1, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.500"})
        _make_station(ideess=2, cp="48001", municipality="Bilbao",
                      prices={"gasolina_95_e5": "1.700"})
        avg = fuel_ingest.recent_avg_eur_l(
            fuel_key="gasolina_95_e5", postal_code="48001",
        )
        self.assertEqual(avg, Decimal("1.700"))

    def test_recent_avg_excludes_stale_stations(self):
        _make_station(ideess=1, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.500"},
                      last_seen_hours_ago=24 * 30)  # 30 days old
        self.assertIsNone(fuel_ingest.recent_avg_eur_l(fuel_key="gasolina_95_e5"))

    def test_current_price_prefers_postal_code(self):
        _make_station(ideess=1, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.500"})
        _make_station(ideess=2, cp="48001", municipality="Bilbao",
                      prices={"gasolina_95_e5": "1.700"})
        # CP match wins over province-wide average.
        self.assertEqual(
            fuel_ingest.current_price_eur_l(
                fuel_key="gasolina_95_e5", postal_code="20018",
            ),
            Decimal("1.500"),
        )

    def test_current_price_falls_back_to_province_avg(self):
        _make_station(ideess=1, cp="20018", municipality="Donostia",
                      prices={"gasolina_95_e5": "1.500"})
        _make_station(ideess=2, cp="20300", municipality="Irun",
                      prices={"gasolina_95_e5": "1.700"})
        # CP 48001 has no rows → falls back to global avg = 1.6
        self.assertEqual(
            fuel_ingest.current_price_eur_l(
                fuel_key="gasolina_95_e5", postal_code="48001",
            ),
            Decimal("1.600"),
        )

    def test_current_price_falls_back_to_default_when_empty(self):
        from apps.mubil.data.price_defaults import (
            DEFAULT_GASOLEO_A_EUR_L,
            DEFAULT_GASOLINA_95_EUR_L,
        )
        self.assertEqual(
            fuel_ingest.current_price_eur_l(fuel_key="gasolina_95_e5"),
            DEFAULT_GASOLINA_95_EUR_L,
        )
        self.assertEqual(
            fuel_ingest.current_price_eur_l(fuel_key="gasoleo_a"),
            DEFAULT_GASOLEO_A_EUR_L,
        )
