"""Tests for the plan MOCK pipeline (PROPUESTA.md §3.4)."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.mubil.models import ChargingStation, DemandHex
from apps.mubil.plan import services


def _make_charger(lon, lat, power_kw=Decimal("50.00")) -> ChargingStation:
    return ChargingStation.objects.create(
        source="test",
        external_id=f"t-{lon:.4f}-{lat:.4f}",
        operator="DEMO",
        address="addr",
        geom=Point(lon, lat, srid=4326),
        power_kw=power_kw,
    )


class GridTests(TestCase):
    def test_iter_grid_covers_bbox(self):
        cells = list(services.iter_grid())
        # 0.5° lat / 0.025° step = 20 rows. 0.9° lon / 0.030° step = 30 cols.
        self.assertEqual(len(cells), 20 * 30)

    def test_slug_fits_pk_constraint(self):
        for cell in services.iter_grid():
            self.assertLessEqual(len(cell.slug), 15)

    def test_slug_unique_per_cell(self):
        slugs = [c.slug for c in services.iter_grid()]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_cell_polygon_is_4326(self):
        cell = next(iter(services.iter_grid()))
        poly = services.cell_polygon(cell)
        self.assertEqual(poly.srid, 4326)
        self.assertEqual(poly.geom_type, "Polygon")


class ScoringTests(TestCase):
    def test_population_peak_at_donostia_centre(self):
        donostia = (43.318, -1.985)
        far_away = (43.000, -2.500)
        self.assertGreater(
            services._population_component(donostia),
            services._population_component(far_away),
        )

    def test_corridor_proxy_drops_off_axis(self):
        on_ap8 = (43.290, -2.500)        # near the AP-8 segment
        off_axis = (42.500, -2.500)      # well south of any corridor
        self.assertGreater(
            services._corridor_component(on_ap8),
            services._corridor_component(off_axis),
        )

    def test_supply_component_counts_chargers(self):
        centre = (43.318, -1.985)
        self.assertEqual(services._supply_component(centre), 0)
        _make_charger(-1.985, 43.318)
        _make_charger(-1.987, 43.320)
        self.assertEqual(services._supply_component(centre), 2)

    def test_score_cell_returns_breakdown(self):
        out = services.score_cell((43.318, -1.985))
        for key in ("score_now", "components"):
            self.assertIn(key, out)
        self.assertTrue(0.0 <= out["score_now"] <= 1.0)

    def test_score_clamped_to_0_1(self):
        # Stack chargers around Donostia to push the negative supply term high.
        for i in range(20):
            _make_charger(-1.985 + 0.001 * i, 43.318)
        out = services.score_cell((43.318, -1.985))
        self.assertGreaterEqual(out["score_now"], 0.0)
        self.assertLessEqual(out["score_now"], 1.0)


class ComputeDemandScoresTests(TestCase):
    def test_dry_run_makes_no_writes(self):
        stats = services.compute_demand_scores(dry_run=True)
        self.assertEqual(stats.cells_scored, 20 * 30)
        self.assertEqual(stats.created, 0)
        self.assertEqual(DemandHex.objects.count(), 0)

    def test_writes_one_row_per_cell(self):
        stats = services.compute_demand_scores()
        self.assertEqual(stats.created, 20 * 30)
        self.assertEqual(DemandHex.objects.count(), 20 * 30)
        sample = DemandHex.objects.first()
        # Components carry the per-axis breakdown we use in the popup.
        self.assertIn("pop", sample.components)
        self.assertIn("od", sample.components)
        self.assertIn("chargers_nearby", sample.components)

    def test_growth_factors_applied(self):
        services.compute_demand_scores()
        sample = DemandHex.objects.filter(score_now__gt=Decimal("0.05")).first()
        self.assertIsNotNone(sample)
        self.assertGreater(sample.score_y3, sample.score_now)
        self.assertGreater(sample.score_y5, sample.score_y3)

    def test_idempotent_rerun_updates(self):
        services.compute_demand_scores()
        stats = services.compute_demand_scores()
        self.assertEqual(stats.created, 0)
        self.assertEqual(stats.updated, 20 * 30)
        self.assertEqual(DemandHex.objects.count(), 20 * 30)

    def test_prune_removes_stale_rows(self):
        # Pre-seed a row whose slug will never be produced by iter_grid().
        DemandHex.objects.create(
            h3_index="stale_pk",
            geom=services.cell_polygon(next(iter(services.iter_grid()))),
            score_now=Decimal("0.5"),
            score_y3=Decimal("0.5"),
            score_y5=Decimal("0.5"),
            components={"stale": True},
        )
        stats = services.compute_demand_scores()
        self.assertEqual(stats.deleted, 1)
        self.assertFalse(DemandHex.objects.filter(h3_index="stale_pk").exists())


class ReadAPITests(TestCase):
    def setUp(self):
        services.compute_demand_scores()

    def test_heatmap_geojson_shape(self):
        fc = services.heatmap_geojson(horizon=3, min_score=0.05)
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertGreater(len(fc["features"]), 0)
        feat = fc["features"][0]
        self.assertEqual(feat["type"], "Feature")
        self.assertEqual(feat["geometry"]["type"], "Polygon")
        self.assertIn("score", feat["properties"])
        self.assertIn("components", feat["properties"])

    def test_heatmap_min_score_filters(self):
        all_features = services.heatmap_geojson(horizon=3, min_score=0.0)["features"]
        high_only = services.heatmap_geojson(horizon=3, min_score=0.5)["features"]
        self.assertGreater(len(all_features), len(high_only))

    def test_top_locations_sorted_desc(self):
        rows = services.top_locations(horizon=3, limit=5)
        self.assertEqual(len(rows), 5)
        scores = [r["score"] for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("centroid_lat", rows[0])
        self.assertIn("centroid_lon", rows[0])
