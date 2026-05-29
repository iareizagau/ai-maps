"""Tests for the route MOCK pipeline (PROPUESTA.md §3.3)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.mubil.models import EVRoutePlan, Vehicle
from apps.mubil.route import services


def _make_vehicle(
    *, make="Kia", model="Niro EV", battery_kwh=Decimal("64.0"),
    consumption_kwh_100km=Decimal("16.0"),
) -> Vehicle:
    return Vehicle.objects.create(
        make=make,
        model=model,
        year=2024,
        propulsion=Vehicle.Propulsion.BEV,
        battery_kwh=battery_kwh,
        consumption_kwh_100km=consumption_kwh_100km,
        range_wltp_km=460,
        co2_g_km_min=0,
        co2_g_km_max=0,
        price_eur=42000,
    )


class DemoCatalogTests(TestCase):
    def test_five_demos_with_unique_slugs(self):
        slugs = [d["slug"] for d in services.ROUTE_DEMOS]
        self.assertEqual(len(slugs), 5)
        self.assertEqual(len(set(slugs)), 5)

    def test_polylines_start_and_end_at_endpoints(self):
        for d in services.ROUTE_DEMOS:
            self.assertEqual(d["polyline"][0], d["origin"])
            self.assertEqual(d["polyline"][-1], d["dest"])

    def test_list_demos_carries_metadata(self):
        demos = services.list_demos()
        self.assertEqual(len(demos), 5)
        first = demos[0]
        for key in ("slug", "label", "origin_name", "dest_name", "via",
                    "distance_km", "duration_min"):
            self.assertIn(key, first)


class PlanTests(TestCase):
    def test_plan_unknown_slug_raises(self):
        with self.assertRaises(ValueError):
            services.plan(slug="does-not-exist")

    def test_plan_default_no_vehicle(self):
        result = services.plan(slug="donostia-bilbao")
        self.assertEqual(result.slug, "donostia-bilbao")
        self.assertIsNone(result.vehicle_id)
        # No battery → no stop is forced even on the long demo.
        self.assertTrue(all(s.kind == "drive" for s in result.segments))
        # 18 kWh/100km × 102 km = 18.36 kWh.
        self.assertAlmostEqual(float(result.energy_kwh), 18.36, places=1)

    def test_plan_with_vehicle_uses_its_consumption(self):
        v = _make_vehicle()  # 16 kWh/100km Niro EV
        result = services.plan(slug="donostia-bilbao", vehicle_id=v.id)
        # 16 × 102 / 100 = 16.32 kWh.
        self.assertAlmostEqual(float(result.energy_kwh), 16.32, places=1)
        self.assertEqual(result.vehicle_label, "Kia Niro EV")

    def test_long_trip_low_soc_inserts_charge_stop(self):
        v = _make_vehicle(battery_kwh=Decimal("30.0"))  # small battery
        result = services.plan(
            slug="donostia-bilbao", vehicle_id=v.id, soc_start_pct=30.0,
        )
        kinds = [s.kind for s in result.segments]
        self.assertIn("charge_stop", kinds)
        # Drive segments still split into two halves.
        self.assertEqual(kinds.count("drive"), 2)

    def test_high_soc_no_stop_needed(self):
        v = _make_vehicle()  # 64 kWh, full
        result = services.plan(
            slug="donostia-tolosa", vehicle_id=v.id, soc_start_pct=95.0,
        )
        self.assertTrue(all(s.kind == "drive" for s in result.segments))

    def test_invalid_soc_raises(self):
        with self.assertRaises(ValueError):
            services.plan(slug="donostia-bilbao", soc_start_pct=120)
        with self.assertRaises(ValueError):
            services.plan(slug="donostia-bilbao", soc_start_pct=-10)

    def test_to_dict_is_json_safe(self):
        import json
        result = services.plan(slug="donostia-bilbao")
        data = result.to_dict()
        # Round-trips through json without TypeError.
        json.dumps(data)
        self.assertEqual(data["slug"], "donostia-bilbao")
        self.assertEqual(len(data["polyline"]), len(services.ROUTE_DEMOS[0]["polyline"]))


class UpsertDemoPlansTests(TestCase):
    def test_creates_five_rows_first_run(self):
        v = _make_vehicle()
        n = services.upsert_demo_plans(default_vehicle=v)
        self.assertEqual(n, 5)
        self.assertEqual(EVRoutePlan.objects.count(), 5)

    def test_idempotent_rerun_does_not_duplicate(self):
        v = _make_vehicle()
        services.upsert_demo_plans(default_vehicle=v)
        services.upsert_demo_plans(default_vehicle=v)
        self.assertEqual(EVRoutePlan.objects.count(), 5)

    def test_geojson_blob_persisted(self):
        v = _make_vehicle()
        services.upsert_demo_plans(default_vehicle=v)
        row = EVRoutePlan.objects.first()
        self.assertIn("polyline", row.geojson)
        self.assertIn("segments", row.geojson)
