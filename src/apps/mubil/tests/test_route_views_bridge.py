"""Tests for the advisor↔route session bridge (Phase 2 of route/PLAN.md)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.mubil.models import Vehicle


def _make_ev(make="Kia", model="Niro EV") -> Vehicle:
    return Vehicle.objects.create(
        make=make,
        model=model,
        year=2024,
        propulsion=Vehicle.Propulsion.BEV,
        battery_kwh=Decimal("64.0"),
        consumption_kwh_100km=Decimal("16.0"),
        range_wltp_km=460,
        co2_g_km_min=0,
        co2_g_km_max=0,
        price_eur=42000,
    )


class RouteBridgeReadTests(TestCase):
    """``route_page`` reads ``session['mubil_route_prefill']`` if present."""

    def setUp(self):
        # Two EVs in the catalog so we can verify the prefill picks the right one
        self.niro = _make_ev(make="Kia", model="Niro EV")
        self.ioniq = _make_ev(make="Hyundai", model="IONIQ 5")

    def _set_session(self, **prefill):
        session = self.client.session
        session["mubil_route_prefill"] = prefill
        session.save()

    def test_prefill_vehicle_picked_when_in_catalog(self):
        self._set_session(vehicle_target_id=self.ioniq.id, cp="20018")
        resp = self.client.get(reverse("mubil:route"), HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["default_vehicle_id"], self.ioniq.id)

    def test_prefill_cp_resolves_to_origin(self):
        # 20018 = Donostia centro (in the cp_centroids seed)
        self._set_session(vehicle_target_id=self.niro.id, cp="20018")
        resp = self.client.get(reverse("mubil:route"), HTTP_HOST="localhost")
        origin = resp.context["default_origin"]
        self.assertIsNotNone(origin)
        self.assertEqual(origin["cp"], "20018")
        self.assertAlmostEqual(origin["lat"], 43.300, places=2)

    def test_unknown_cp_yields_no_origin(self):
        self._set_session(vehicle_target_id=self.niro.id, cp="00000")
        resp = self.client.get(reverse("mubil:route"), HTTP_HOST="localhost")
        self.assertIsNone(resp.context["default_origin"])

    def test_missing_session_falls_back_to_niro_default(self):
        resp = self.client.get(reverse("mubil:route"), HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        # Niro present → default rule picks it
        self.assertEqual(resp.context["default_vehicle_id"], self.niro.id)
        self.assertIsNone(resp.context["default_origin"])

    def test_stale_prefill_vehicle_id_is_ignored(self):
        # Vehicle id that doesn't exist any more (e.g. catalog re-seed)
        self._set_session(vehicle_target_id=999999, cp="20018")
        resp = self.client.get(reverse("mubil:route"), HTTP_HOST="localhost")
        # Falls back to Niro default rather than blowing up
        self.assertEqual(resp.context["default_vehicle_id"], self.niro.id)
        # CP is independent of vehicle — still resolved
        self.assertIsNotNone(resp.context["default_origin"])
