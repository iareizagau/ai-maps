"""Tests for the advisor TCO calculator.

PROPUESTA.md §13: precisión TCO objetivo ±5% vs valor de mercado real.
Aquí validamos la coherencia interna del cálculo y casos límite.
"""

from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.mubil.advisor import services
from apps.mubil.models import ChargingStation, Vehicle


class TCOServiceTests(TestCase):
    """Lógica pura de cálculo TCO."""

    @classmethod
    def setUpTestData(cls):
        cls.golf = Vehicle.objects.create(
            make="Volkswagen", model="Golf 1.6 TDI", year=2024,
            propulsion=Vehicle.Propulsion.DIESEL,
            consumption_l_100km=Decimal("4.9"),
            price_eur=28_500,
        )
        cls.ibiza = Vehicle.objects.create(
            make="Seat", model="Ibiza 1.0 TSI", year=2024,
            propulsion=Vehicle.Propulsion.ICE,
            consumption_l_100km=Decimal("5.6"),
            price_eur=19_900,
        )
        cls.niro = Vehicle.objects.create(
            make="Kia", model="Niro EV", year=2025,
            propulsion=Vehicle.Propulsion.BEV,
            battery_kwh=Decimal("64.8"),
            range_wltp_km=460,
            consumption_kwh_100km=Decimal("16.2"),
            price_eur=41_500,
        )

    # ---------- energy cost ----------

    def test_diesel_energy_cost_matches_hand_calc(self):
        # 4.9 L/100km × 15000 km × 1.495 €/L → 1098.83 €/año
        cost = services._annual_energy_cost(self.golf, 15000, night_charging=False)
        self.assertAlmostEqual(float(cost), 1098.83, delta=1.0)

    def test_gasoline_energy_cost_matches_hand_calc(self):
        # 5.6 L/100km × 15000 km × 1.585 €/L → 1331.40 €/año
        cost = services._annual_energy_cost(self.ibiza, 15000, night_charging=False)
        self.assertAlmostEqual(float(cost), 1331.40, delta=1.0)

    def test_ev_energy_cost_uses_pvpc_when_daylight(self):
        # 16.2 kWh/100km × 15000 km × 0.165 €/kWh → 400.95 €/año
        cost = services._annual_energy_cost(self.niro, 15000, night_charging=False)
        self.assertAlmostEqual(float(cost), 400.95, delta=0.5)

    def test_ev_energy_cost_uses_valley_at_night(self):
        # 16.2 kWh/100km × 15000 km × 0.085 €/kWh → 206.55 €/año
        cost = services._annual_energy_cost(self.niro, 15000, night_charging=True)
        self.assertAlmostEqual(float(cost), 206.55, delta=0.5)
        # Y siempre menor que la diurna
        diurna = services._annual_energy_cost(self.niro, 15000, night_charging=False)
        self.assertLess(cost, diurna)

    # ---------- CO2 ----------

    def test_ev_emits_far_less_co2_than_diesel(self):
        co2_ev = services._annual_co2_kg(self.niro, 15000)
        co2_diesel = services._annual_co2_kg(self.golf, 15000)
        self.assertLess(co2_ev, co2_diesel / 3)  # al menos 3x menos

    # ---------- breakdown ----------

    def test_breakdown_total_equals_sum_of_components(self):
        bd = services._breakdown(self.golf, 15000, 10, night_charging=False)
        self.assertEqual(
            bd.total,
            bd.energy + bd.maintenance + bd.insurance + bd.taxes,
        )

    def test_ev_breakdown_cheaper_in_maintenance_and_taxes(self):
        bd_diesel = services._breakdown(self.golf, 15000, 10, night_charging=False)
        bd_ev = services._breakdown(self.niro, 15000, 10, night_charging=False)
        self.assertLess(bd_ev.maintenance, bd_diesel.maintenance)
        self.assertLess(bd_ev.taxes, bd_diesel.taxes)
        # Energía también más barata
        self.assertLess(bd_ev.energy, bd_diesel.energy)

    # ---------- full quote ----------

    def test_full_quote_returns_valid_structure(self):
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
        )
        self.assertEqual(q.cp_name, "Donostia / San Sebastián (centro)")
        self.assertGreater(q.breakdown_current.total, q.breakdown_target.total)
        self.assertGreater(q.co2_kg_year_current, q.co2_kg_year_target)
        # Payback existe (ambos coches tienen precio)
        self.assertIsNotNone(q.payback_years)

    def test_unknown_cp_returns_quote_without_chargers(self):
        q = services.calculate_tco_quote(
            cp="99999",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
        )
        self.assertIsNone(q.cp_name)
        self.assertEqual(q.nearby_chargers, [])

    # ---------- validation ----------

    def test_km_year_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018", km_year=500,
                vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
            )

    def test_horizon_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018", km_year=15000, years_horizon=25,
                vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
            )

    # ---------- subsidy / payback ----------

    def test_subvencion_reduces_payback_years(self):
        base = services.calculate_tco_quote(
            cp="20018", km_year=15000,
            vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
        )
        subsidized = services.calculate_tco_quote(
            cp="20018", km_year=15000,
            vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
            subvencion_eur=7000,
        )
        self.assertIsNotNone(base.payback_years)
        self.assertIsNotNone(subsidized.payback_years)
        self.assertLess(subsidized.payback_years, base.payback_years)
        self.assertEqual(subsidized.subvencion_eur, Decimal("7000"))

    def test_subvencion_larger_than_delta_yields_zero_payback(self):
        # Golf 28.500€ → Niro 41.500€ → delta 13.000€. Con 12k de ayuda (max),
        # delta queda en 1.000€ y aún hay payback >0.
        # Para forzar payback=0 hace falta delta_price <= subvencion. Modifico
        # el precio del Niro a 30k para que delta=1500 y subvencion=12k → 0.
        cheap_niro = Vehicle.objects.create(
            make="Kia", model="Niro EV LE", year=2025,
            propulsion=Vehicle.Propulsion.BEV,
            consumption_kwh_100km=Decimal("16.2"),
            price_eur=30_000,
        )
        q = services.calculate_tco_quote(
            cp="20018", km_year=15000,
            vehicle_current_id=self.golf.id, vehicle_target_id=cheap_niro.id,
            subvencion_eur=12_000,
        )
        self.assertEqual(q.payback_years, Decimal("0"))

    def test_subvencion_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018", km_year=15000,
                vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
                subvencion_eur=-100,
            )
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018", km_year=15000,
                vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
                subvencion_eur=20_000,
            )

    def test_default_subvencion_is_zero(self):
        q = services.calculate_tco_quote(
            cp="20018", km_year=15000,
            vehicle_current_id=self.golf.id, vehicle_target_id=self.niro.id,
        )
        self.assertEqual(q.subvencion_eur, Decimal("0"))


class NearbyChargersTests(TestCase):
    """Filtro espacial GIST."""

    @classmethod
    def setUpTestData(cls):
        # 3 cargadores: uno a 0.5 km, uno a 4 km, uno a 50 km
        ChargingStation.objects.create(
            external_id="t1", source="test", operator="A",
            geom=Point(-1.999, 43.296, srid=4326),  # cerca CP 20018
            power_kw=Decimal("22"),
        )
        ChargingStation.objects.create(
            external_id="t2", source="test", operator="B",
            geom=Point(-1.948, 43.286, srid=4326),  # Astigarraga
            power_kw=Decimal("350"),
        )
        ChargingStation.objects.create(
            external_id="t3", source="test", operator="C",
            geom=Point(-2.935, 43.262, srid=4326),  # Bilbao — fuera 5km
            power_kw=Decimal("50"),
        )

    def test_chargers_within_5km_of_donostia(self):
        found = services._nearby_chargers("20018", radius_km=5.0)
        ops = {c.operator for c in found}
        self.assertIn("A", ops)
        self.assertIn("B", ops)
        self.assertNotIn("C", ops)

    def test_chargers_ordered_by_distance(self):
        found = services._nearby_chargers("20018", radius_km=10.0)
        distances = [c.distance.km for c in found]
        self.assertEqual(distances, sorted(distances))
