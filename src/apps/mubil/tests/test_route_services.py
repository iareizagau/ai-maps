"""Tests for the route MOCK pipeline (PROPUESTA.md §3.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.mubil.models import ChargingStation, EnergyPricePVPC, EVRoutePlan, Vehicle
from apps.mubil.route import services


def _make_vehicle(
    *,
    make="Kia",
    model="Niro EV",
    battery_kwh=Decimal("64.0"),
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
        for key in (
            "slug",
            "label",
            "origin_name",
            "dest_name",
            "via",
            "distance_km",
            "duration_min",
        ):
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
            slug="donostia-bilbao",
            vehicle_id=v.id,
            soc_start_pct=30.0,
        )
        kinds = [s.kind for s in result.segments]
        self.assertIn("charge_stop", kinds)
        # Drive segments still split into two halves.
        self.assertEqual(kinds.count("drive"), 2)

    def test_high_soc_no_stop_needed(self):
        v = _make_vehicle()  # 64 kWh, full
        result = services.plan(
            slug="donostia-tolosa",
            vehicle_id=v.id,
            soc_start_pct=95.0,
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
        self.assertEqual(
            len(data["polyline"]), len(services.ROUTE_DEMOS[0]["polyline"])
        )


class Phase1FieldsTests(TestCase):
    """Phase 1: free-O/D, ICE baseline, 24h cost curve, chargers-along-route."""

    def test_demo_plan_carries_phase1_fields(self):
        v = _make_vehicle()
        result = services.plan(slug="donostia-bilbao", vehicle_id=v.id)
        # Mode and ICE baseline
        self.assertEqual(result.mode, "demo")
        self.assertIsNotNone(result.ice_baseline)
        self.assertIn("cost_eur", result.ice_baseline)
        self.assertIn("vs_ev_eur", result.ice_baseline)
        # 24h cost curve
        self.assertEqual(len(result.cost_by_hour), 24)
        for h, c in result.cost_by_hour:
            self.assertGreaterEqual(c, 0)
        # SOC curve sampled at polyline vertices (battery known)
        self.assertGreater(len(result.soc_curve), 0)
        self.assertEqual(result.soc_curve[0][0], 0.0)
        # nearby_chargers is a list (may be empty without seed)
        self.assertIsInstance(result.nearby_chargers, list)

    def test_to_dict_includes_phase1_fields(self):
        import json

        v = _make_vehicle()
        result = services.plan(
            slug="donostia-bilbao", vehicle_id=v.id, departure_hour=3
        )
        data = result.to_dict()
        for key in (
            "mode",
            "departure_hour",
            "soc_curve",
            "cost_by_hour",
            "nearby_chargers",
            "selected_charger",
            "ice_baseline",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["departure_hour"], 3)
        # JSON-serialisable end-to-end (no Decimal leakage)
        json.dumps(data)

    def test_invalid_departure_hour_raises(self):
        with self.assertRaises(ValueError):
            services.plan(slug="donostia-bilbao", departure_hour=24)
        with self.assertRaises(ValueError):
            services.plan(slug="donostia-bilbao", departure_hour=-1)

    def test_plan_requires_slug_or_full_od(self):
        with self.assertRaises(ValueError):
            services.plan()
        # Partial O/D is rejected too
        with self.assertRaises(ValueError):
            services.plan(origin_lng=-1.98, origin_lat=43.31)

    def test_pvpc_curve_fallback_when_empty(self):
        curve = services._pvpc_24h_curve()
        self.assertEqual(len(curve), 24)
        # Flat curve at the fallback price → all values equal
        self.assertEqual(len(set(curve)), 1)

    def test_pvpc_curve_buckets_by_hour(self):
        # Insert two days of synthetic data: hour 3 cheap, hour 12 expensive.
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        # Build at Madrid-local hours by going through tz conversion. We just
        # need the bucket to be deterministically different.
        for day in (1, 2):
            EnergyPricePVPC.objects.create(
                timestamp=(now - timedelta(days=day)).replace(hour=3),
                tariff=EnergyPricePVPC.Tariff.P3,
                price_eur_mwh=Decimal("50"),
            )
            EnergyPricePVPC.objects.create(
                timestamp=(now - timedelta(days=day)).replace(hour=12),
                tariff=EnergyPricePVPC.Tariff.P2,
                price_eur_mwh=Decimal("250"),
            )
        curve = services._pvpc_24h_curve(window_days=7)
        self.assertEqual(len(curve), 24)
        # The two inserted hours should differ; the others get filled with
        # the average so set-size must be at least 2.
        self.assertGreaterEqual(len(set(curve)), 2)

    def test_cost_by_hour_tracks_pvpc(self):
        curve = [Decimal("0.10")] * 24
        curve[3] = Decimal("0.05")
        curve[20] = Decimal("0.30")
        costs = services._cost_by_hour(
            energy_kwh=Decimal("20"),
            kwh_fast_charge=Decimal("0"),
            pvpc_curve=curve,
        )
        self.assertEqual(len(costs), 24)
        # Cheapest hour matches the cheapest PVPC bucket
        cheapest = min(costs, key=lambda x: x[1])
        self.assertEqual(cheapest[0], 3)
        priciest = max(costs, key=lambda x: x[1])
        self.assertEqual(priciest[0], 20)

    def test_ice_trip_cost_uses_gasoline(self):
        # 100 km × 6.5 L/100km = 6.5 L. Fallback price → cost > 0.
        ice = services._ice_trip_cost(Decimal("100"))
        self.assertAlmostEqual(ice["fuel_l"], 6.5, places=2)
        self.assertGreater(ice["cost_eur"], 0)


class ChargersAlongRouteTests(TestCase):
    def test_along_route_filters_by_corridor(self):
        # Charger sitting roughly on the Donostia-Bilbao polyline
        on_route = ChargingStation.objects.create(
            source="test",
            external_id="on",
            geom=Point(-2.4970, 43.3576, srid=4326),
            power_kw=Decimal("150"),
        )
        # Charger far away (Madrid)
        ChargingStation.objects.create(
            source="test",
            external_id="off",
            geom=Point(-3.7000, 40.4000, srid=4326),
            power_kw=Decimal("150"),
        )
        polyline_lonlat = [
            (lon, lat) for lat, lon in services.ROUTE_DEMOS[0]["polyline"]
        ]
        qs = list(ChargingStation.objects.along_route(polyline_lonlat, radius_km=5))
        ids = [c.id for c in qs]
        self.assertIn(on_route.id, ids)
        self.assertEqual(len(qs), 1)

    def test_along_route_short_polyline_returns_none(self):
        qs = ChargingStation.objects.along_route([(-2.0, 43.3)], radius_km=5)
        self.assertEqual(list(qs), [])


class FreeODTests(TestCase):
    """Free-mode dispatch using a stubbed ``advisor.get_commute_route``."""

    def _stub_route(self, distance_km=120.0):
        return {
            "distance_km": distance_km,
            "motorway_pct": 80.0,
            "nacional_pct": 15.0,
            "urban_pct": 5.0,
            "route_geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-1.9812, 43.3183],
                                [-2.4970, 43.3576],
                                [-2.9253, 43.2627],
                            ],
                        },
                        "properties": {},
                    }
                ],
                "metadata": {},
            },
        }

    def test_free_mode_uses_advisor_route(self):
        v = _make_vehicle()
        with mock.patch(
            "apps.mubil.advisor.services.get_commute_route",
            return_value=self._stub_route(distance_km=120.0),
        ) as patched:
            result = services.plan(
                origin_lng=-1.9812,
                origin_lat=43.3183,
                dest_lng=-2.9253,
                dest_lat=43.2627,
                vehicle_id=v.id,
                soc_start_pct=80.0,
            )
        patched.assert_called_once()
        self.assertEqual(result.mode, "free")
        self.assertEqual(result.slug, "free")
        self.assertAlmostEqual(float(result.distance_km), 120.0, places=2)
        # Polyline preserves (lat, lon) ordering and at least the 3 vertices
        self.assertEqual(result.polyline[0], (43.3183, -1.9812))
        self.assertGreaterEqual(len(result.polyline), 3)
        # All Phase 1 fields populated
        self.assertEqual(len(result.cost_by_hour), 24)
        self.assertIsNotNone(result.ice_baseline)

    def test_free_mode_zero_distance_raises(self):
        with mock.patch(
            "apps.mubil.advisor.services.get_commute_route",
            return_value={"distance_km": 0, "route_geojson": {}},
        ), self.assertRaises(ValueError):
            services.plan(
                origin_lng=-1.9812,
                origin_lat=43.3183,
                dest_lng=-1.9812,
                dest_lat=43.3183,
            )


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
