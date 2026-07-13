"""Tests for the IDAE catalog ingest pipeline.

HTTP is mocked — these tests do not hit coches.idae.es. To exercise live:
  `python manage.py ingest_idae_catalog --marca <id> --dry-run`.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.mubil.data import idae_client, idae_ingest
from apps.mubil.models import Vehicle

# Sample rows in the same shape that POST /ajax returns.
SAMPLE_ELEC_PAYLOAD = {
    "draw": 1,
    "recordsTotal": 3,
    "recordsFiltered": 3,
    "data": [
        # BEV — Tesla Model Y
        [
            "TESLA  Model Y Gran Autonomía",
            '<img src="https://coches.idae.es/img/clasificacion/A.gif" title="Clasificación: A">',
            "Eléctricos puros",
            "M1",
            2100,
            "16.9",
            "378.0",
            "533.0",
            "75.0",
            548400,
        ],
        # PHEV
        [
            "VOLKSWAGEN  Tiguan eHybrid",
            '<img src="https://coches.idae.es/img/clasificacion/B.gif" title="Clasificación: B">',
            "Híbrido enchufable",
            "M1",
            2050,
            "19.7",
            "150.0",
            "100.0",
            "19.7",
            612345,
        ],
        # ICE — appears in elec table with empty kWh cells, motorización=Gasolina
        [
            "SEAT  Ibiza 1.0 TSI",
            '<img src="https://coches.idae.es/img/clasificacion/C.gif" title="Clasificación: C">',
            "Gasolina",
            "M1",
            1180,
            "",
            "",
            "",
            "",
            709123,
        ],
    ],
}

SAMPLE_WLTP_PAYLOAD = {
    "draw": 1,
    "recordsTotal": 3,
    "recordsFiltered": 3,
    "data": [
        # ICE — has consumption + CO₂ filled
        [
            "SEAT  Ibiza 1.0 TSI",
            '<img src="https://coches.idae.es/img/clasificacion/C.gif" title="Clasificación: C">',
            "5,3",
            "5,8",
            "120",
            "131",
            709123,
        ],
        # PHEV — partial WLTP figures (combustion fallback mode)
        [
            "VOLKSWAGEN  Tiguan eHybrid",
            '<img src="https://coches.idae.es/img/clasificacion/B.gif" title="Clasificación: B">',
            "1,4",
            "1,8",
            "32",
            "41",
            612345,
        ],
        # BEV — Tesla → empty WLTP combustion cells
        [
            "TESLA  Model Y Gran Autonomía",
            '<img src="https://coches.idae.es/img/clasificacion/A.gif" title="Clasificación: A">',
            "",
            "",
            "",
            "",
            548400,
        ],
    ],
}


# ─────────────────────────────────────────────── parser unit tests


class ParserTests(TestCase):
    def test_decimal_comma(self):
        self.assertEqual(idae_client._to_decimal("13,2"), Decimal("13.2"))
        self.assertEqual(idae_client._to_decimal("13.2"), Decimal("13.2"))
        self.assertEqual(idae_client._to_decimal(13.2), Decimal("13.2"))

    def test_decimal_empty(self):
        self.assertIsNone(idae_client._to_decimal(""))
        self.assertIsNone(idae_client._to_decimal(None))
        self.assertIsNone(idae_client._to_decimal("nope"))

    def test_normalize_make_model_double_space(self):
        make, model = idae_client._normalize_make_model("TESLA  Model X Gran autonomía")
        self.assertEqual(make, "TESLA")
        self.assertEqual(model, "Model X Gran autonomía")

    def test_normalize_make_model_multiword_marca(self):
        make, model = idae_client._normalize_make_model("ZERO MOTORCYCLES  LS1")
        self.assertEqual(make, "ZERO MOTORCYCLES")
        self.assertEqual(model, "LS1")

    def test_normalize_make_model_no_double_space(self):
        # Defensive fallback — pre-2024 IDAE rows had only a single space.
        make, model = idae_client._normalize_make_model("FIAT 500")
        self.assertEqual(make, "FIAT")
        self.assertEqual(model, "500")

    def test_make_hint_overrides_heuristic(self):
        # Real-life VW row where the marca/model separator is a single space
        # and the model contains its own multi-space chunks.
        raw = "Volkswagen Turismos T-Roc Cabrio MY22 …  6 vel."
        make, model = idae_client._normalize_make_model(
            raw,
            make_hint="Volkswagen Turismos",
        )
        self.assertEqual(make, "Volkswagen Turismos")
        self.assertTrue(model.startswith("T-Roc Cabrio"))

    def test_extract_energy_class_from_img(self):
        s = '<img src="https://coches.idae.es/img/clasificacion/A.gif" title="A">'
        self.assertEqual(idae_client._extract_energy_class(s), "A")

    def test_extract_energy_class_missing(self):
        self.assertEqual(idae_client._extract_energy_class(""), "")
        self.assertEqual(idae_client._extract_energy_class("<img>"), "")


class PropulsionMappingTests(TestCase):
    def test_bev(self):
        self.assertEqual(idae_client.map_propulsion("Eléctricos puros"), "BEV")
        self.assertEqual(idae_client.map_propulsion("ELECTRICOS PUROS"), "BEV")

    def test_phev_before_hev(self):
        # The needle order matters — both "Híbrido enchufable" (singular)
        # and "Híbridos enchufables" (plural, IDAE's actual label) must
        # match PHEV before the generic Híbrido rule.
        self.assertEqual(idae_client.map_propulsion("Híbrido enchufable"), "PHEV")
        self.assertEqual(idae_client.map_propulsion("Híbridos enchufables"), "PHEV")
        self.assertEqual(idae_client.map_propulsion("Híbrido"), "HEV")
        self.assertEqual(idae_client.map_propulsion("Híbridos"), "HEV")

    def test_diesel_variants(self):
        self.assertEqual(idae_client.map_propulsion("Diésel"), "DIESEL")
        self.assertEqual(idae_client.map_propulsion("Gasóleo"), "DIESEL")

    def test_gas_variants(self):
        self.assertEqual(idae_client.map_propulsion("Gas Natural Comprimido"), "CNG")
        self.assertEqual(idae_client.map_propulsion("GLP"), "LPG")
        self.assertEqual(idae_client.map_propulsion("Autogás"), "LPG")

    def test_unknown_returns_none(self):
        self.assertIsNone(idae_client.map_propulsion(""))
        self.assertIsNone(idae_client.map_propulsion("Pegasus"))


class ElecRowParsingTests(TestCase):
    def test_parses_bev_row(self):
        row = idae_client._parse_elec_row(SAMPLE_ELEC_PAYLOAD["data"][0])
        self.assertIsNotNone(row)
        self.assertEqual(row.idae_id, 548400)
        self.assertEqual(row.make, "TESLA")
        self.assertEqual(row.model, "Model Y Gran Autonomía")
        self.assertEqual(row.propulsion, "BEV")
        self.assertEqual(row.category, "M1")
        self.assertEqual(row.mtma_kg, 2100)
        self.assertEqual(row.consumption_kwh_100km, Decimal("16.9"))
        self.assertEqual(row.range_wltp_km, 533)
        self.assertEqual(row.battery_kwh, Decimal("75.0"))
        self.assertEqual(row.energy_class, "A")

    def test_parses_ice_row_with_empty_elec_cells(self):
        row = idae_client._parse_elec_row(SAMPLE_ELEC_PAYLOAD["data"][2])
        self.assertEqual(row.propulsion, "ICE")
        self.assertIsNone(row.consumption_kwh_100km)
        self.assertIsNone(row.battery_kwh)
        self.assertIsNone(row.range_wltp_km)

    def test_drops_malformed_rows(self):
        self.assertIsNone(idae_client._parse_elec_row([]))
        self.assertIsNone(idae_client._parse_elec_row([1, 2, 3]))  # too short


class WLTPRowParsingTests(TestCase):
    def test_parses_combustion_row(self):
        row = idae_client._parse_wltp_row(SAMPLE_WLTP_PAYLOAD["data"][0])
        self.assertIsNotNone(row)
        self.assertEqual(row.idae_id, 709123)
        self.assertEqual(row.consumption_l_100km_min, Decimal("5.3"))
        self.assertEqual(row.consumption_l_100km_max, Decimal("5.8"))
        self.assertEqual(row.co2_g_km_min, 120)
        self.assertEqual(row.co2_g_km_max, 131)

    def test_parses_bev_row_blank_combustion(self):
        row = idae_client._parse_wltp_row(SAMPLE_WLTP_PAYLOAD["data"][2])
        self.assertIsNone(row.consumption_l_100km_min)
        self.assertIsNone(row.co2_g_km_min)


# ─────────────────────────────────────────────── ingest orchestration


def _envelope_responder(payloads_by_ciclo):
    """Build a ``fetch_listing`` side_effect that returns one page per ciclo
    and an empty page on the second call (ends pagination)."""
    state = dict.fromkeys(payloads_by_ciclo, False)

    def _side_effect(*, ciclo, marca_id=None, categoria_id=None, start=0, length=1000):
        if state[ciclo]:
            return {"data": []}
        state[ciclo] = True
        return payloads_by_ciclo[ciclo]

    return _side_effect


class IngestMarcaTests(TestCase):
    def setUp(self):
        super().setUp()
        Vehicle.objects.all().delete()

    @mock.patch.object(idae_client.IDAESession, "fetch_listing")
    def test_merges_elec_and_wltp_by_idae_id(self, fetch_mock):
        fetch_mock.side_effect = _envelope_responder(
            {
                "elec": SAMPLE_ELEC_PAYLOAD,
                "wltp": SAMPLE_WLTP_PAYLOAD,
            }
        )
        session = idae_client.IDAESession()

        stats = idae_ingest.ingest_marca(marca_id=134, session=session)

        self.assertEqual(stats.fetched_elec, 3)
        self.assertEqual(stats.fetched_wltp, 3)
        self.assertEqual(stats.merged, 3)
        self.assertEqual(stats.created, 3)
        self.assertEqual(Vehicle.objects.count(), 3)

        tesla = Vehicle.objects.get(idae_id=548400)
        self.assertEqual(tesla.make, "TESLA")
        self.assertEqual(tesla.propulsion, "BEV")
        self.assertEqual(tesla.dgt_label, "0")  # Cero
        self.assertEqual(tesla.energy_class, "A")
        # BEV gets 0 CO₂ even though the WLTP cell was empty.
        self.assertEqual(tesla.co2_g_km_min, 0)

        ice = Vehicle.objects.get(idae_id=709123)
        self.assertEqual(ice.propulsion, "ICE")
        # Consumption collapsed to midpoint of (5.3, 5.8).
        self.assertEqual(ice.consumption_l_100km, Decimal("5.55"))
        self.assertEqual(ice.co2_g_km_max, 131)

        phev = Vehicle.objects.get(idae_id=612345)
        self.assertEqual(phev.propulsion, "PHEV")
        self.assertEqual(phev.dgt_label, "ECO")

    @mock.patch.object(idae_client.IDAESession, "fetch_listing")
    def test_idempotent_rerun_updates(self, fetch_mock):
        fetch_mock.side_effect = _envelope_responder(
            {
                "elec": SAMPLE_ELEC_PAYLOAD,
                "wltp": SAMPLE_WLTP_PAYLOAD,
            }
        )
        session = idae_client.IDAESession()
        idae_ingest.ingest_marca(marca_id=134, session=session)

        # Second run — same payloads → updates, not creates.
        fetch_mock.side_effect = _envelope_responder(
            {
                "elec": SAMPLE_ELEC_PAYLOAD,
                "wltp": SAMPLE_WLTP_PAYLOAD,
            }
        )
        stats = idae_ingest.ingest_marca(marca_id=134, session=session)
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 3)
        self.assertEqual(Vehicle.objects.count(), 3)

    @mock.patch.object(idae_client.IDAESession, "fetch_listing")
    def test_dry_run_makes_no_writes(self, fetch_mock):
        fetch_mock.side_effect = _envelope_responder(
            {
                "elec": SAMPLE_ELEC_PAYLOAD,
                "wltp": SAMPLE_WLTP_PAYLOAD,
            }
        )
        session = idae_client.IDAESession()
        stats = idae_ingest.ingest_marca(marca_id=134, session=session, dry_run=True)
        self.assertEqual(stats.merged, 3)
        self.assertEqual(stats.created, 0)
        self.assertEqual(Vehicle.objects.count(), 0)
