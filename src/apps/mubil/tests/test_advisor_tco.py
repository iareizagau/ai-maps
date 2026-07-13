"""Tests for the advisor TCO calculator.

PROPUESTA.md §13: precisión TCO objetivo ±5% vs valor de mercado real.
Aquí validamos la coherencia interna del cálculo y casos límite.
"""

from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.mubil.advisor import services
from apps.mubil.models import ChargingStation, FuelStation, Vehicle


class TCOServiceTests(TestCase):
    """Lógica pura de cálculo TCO."""

    @classmethod
    def setUpTestData(cls):
        # Clean FuelStation to avoid pollution under --keepdb
        FuelStation.objects.all().delete()

        cls.golf = Vehicle.objects.create(
            make="Volkswagen",
            model="Golf 1.6 TDI",
            year=2024,
            propulsion=Vehicle.Propulsion.DIESEL,
            consumption_l_100km=Decimal("4.9"),
            price_eur=28_500,
        )
        cls.ibiza = Vehicle.objects.create(
            make="Seat",
            model="Ibiza 1.0 TSI",
            year=2024,
            propulsion=Vehicle.Propulsion.ICE,
            consumption_l_100km=Decimal("5.6"),
            price_eur=19_900,
        )
        cls.niro = Vehicle.objects.create(
            make="Kia",
            model="Niro EV",
            year=2025,
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
                cp="20018",
                km_year=500,
                vehicle_current_id=self.golf.id,
                vehicle_target_id=self.niro.id,
            )

    def test_horizon_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018",
                km_year=15000,
                years_horizon=25,
                vehicle_current_id=self.golf.id,
                vehicle_target_id=self.niro.id,
            )

    # ---------- subsidy / payback ----------

    def test_subvencion_override_reduces_payback_years(self):
        # Override fuerza un total explícito ignorando el cálculo automático.
        base = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            subvencion_override_eur=0,
        )
        subsidized = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            subvencion_override_eur=7000,
        )
        self.assertIsNotNone(base.payback_years)
        self.assertIsNotNone(subsidized.payback_years)
        self.assertLess(subsidized.payback_years, base.payback_years)
        self.assertEqual(subsidized.subvencion_eur, Decimal("7000"))

    def test_subvencion_larger_than_delta_yields_zero_payback(self):
        cheap_niro = Vehicle.objects.create(
            make="Kia",
            model="Niro EV LE",
            year=2025,
            propulsion=Vehicle.Propulsion.BEV,
            consumption_kwh_100km=Decimal("16.2"),
            price_eur=30_000,
        )
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=cheap_niro.id,
            subvencion_override_eur=12_000,
            purchase_mode="new_vs_new",
        )
        self.assertEqual(q.payback_years, Decimal("0"))

    def test_subvencion_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018",
                km_year=15000,
                vehicle_current_id=self.golf.id,
                vehicle_target_id=self.niro.id,
                subvencion_eur=-100,
            )
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018",
                km_year=15000,
                vehicle_current_id=self.golf.id,
                vehicle_target_id=self.niro.id,
                subvencion_eur=40_000,
            )

    def test_default_profile_particular_computes_auto_incentives(self):
        # Sin override y perfil 'particular' por defecto, debe inyectar
        # Programa Auto+ vehículo (4.500 €) como mínimo.
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
        )
        self.assertIsNotNone(q.incentives)
        self.assertGreaterEqual(q.subvencion_eur, Decimal("4500"))


class NearbyChargersTests(TestCase):
    """Filtro espacial GIST."""

    @classmethod
    def setUpTestData(cls):
        # 3 cargadores: uno a 0.5 km, uno a 4 km, uno a 50 km
        ChargingStation.objects.create(
            external_id="t1",
            source="test",
            operator="A",
            geom=Point(-1.999, 43.296, srid=4326),  # cerca CP 20018
            power_kw=Decimal("22"),
        )
        ChargingStation.objects.create(
            external_id="t2",
            source="test",
            operator="B",
            geom=Point(-1.948, 43.286, srid=4326),  # Astigarraga
            power_kw=Decimal("350"),
        )
        ChargingStation.objects.create(
            external_id="t3",
            source="test",
            operator="C",
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


class IncentivesTests(TestCase):
    """Reglas de `advisor.incentives.compute_incentives`."""

    def test_particular_no_scrap_basics(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b = compute_incentives(
            profile="particular",
            cp="20018",
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=False,
            years_horizon=10,
        )
        codes = {i.code for i in b.items}
        self.assertIn("auto_plus_vehicle", codes)
        self.assertIn("auto_plus_concessionaire", codes)
        self.assertIn("irpf_15", codes)
        self.assertIn("ivtm_bonif", codes)  # CP de Gipuzkoa
        self.assertNotIn("iva_deducible", codes)
        self.assertNotIn("moves3_wallbox", codes)
        # Programa Auto+ particular sin scrap = 4.500 €
        moves = next(i for i in b.items if i.code == "auto_plus_vehicle")
        self.assertEqual(moves.amount_eur, Decimal("4500"))

    def test_particular_with_scrap_jumps_to_7000(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b = compute_incentives(
            profile="particular",
            cp="20018",
            vehicle_price_eur=41500,
            scrapping=True,
            needs_wallbox=False,
            years_horizon=10,
        )
        moves = next(i for i in b.items if i.code == "auto_plus_vehicle")
        self.assertEqual(moves.amount_eur, Decimal("7000"))

    def test_wallbox_no_longer_adds_moves3_line(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b = compute_incentives(
            profile="particular",
            cp="20018",
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=True,
            years_horizon=10,
        )
        self.assertNotIn("moves3_wallbox", {i.code for i in b.items})

    def test_empresa_iva_deducible_100(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b = compute_incentives(
            profile="empresa",
            cp="20018",
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=False,
            years_horizon=10,
        )
        codes = {i.code for i in b.items}
        self.assertIn("iva_deducible", codes)
        self.assertNotIn("irpf_15", codes)  # no aplica a empresas
        iva = next(i for i in b.items if i.code == "iva_deducible")
        # 41500 * 21/121 = 7202 €
        self.assertAlmostEqual(float(iva.amount_eur), 7202.48, delta=1)

    def test_autonomo_iva_deducible_50(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b = compute_incentives(
            profile="autonomo",
            cp="20018",
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=False,
            years_horizon=10,
        )
        iva = next(i for i in b.items if i.code == "iva_deducible")
        self.assertAlmostEqual(float(iva.amount_eur), 3601.24, delta=1)

    def test_ivtm_recurring_capitalises_with_horizon(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b10 = compute_incentives(
            profile="particular",
            cp="48001",
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=False,
            years_horizon=10,
        )
        b5 = compute_incentives(
            profile="particular",
            cp="48001",
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=False,
            years_horizon=5,
        )
        ivtm10 = next(i for i in b10.items if i.code == "ivtm_bonif")
        ivtm5 = next(i for i in b5.items if i.code == "ivtm_bonif")
        # Mismo flujo anual, distinto equivalente lump-sum
        self.assertEqual(ivtm10.amount_eur, ivtm5.amount_eur)
        self.assertEqual(ivtm10.equivalent_lump_sum(10), ivtm5.amount_eur * 10)

    def test_cp_outside_pais_vasco_no_ivtm(self):
        from apps.mubil.advisor.incentives import compute_incentives

        b = compute_incentives(
            profile="particular",
            cp="28001",  # Madrid
            vehicle_price_eur=41500,
            scrapping=False,
            needs_wallbox=False,
            years_horizon=10,
        )
        self.assertNotIn("ivtm_bonif", {i.code for i in b.items})


class ChargingMixTests(TestCase):
    """Mix de carga ponderado."""

    def test_normalize_residual_to_home(self):
        from apps.mubil.advisor.charging_mix import ChargingMix

        m = ChargingMix.normalized(50, 30, 10, 5)  # suma 95
        self.assertEqual(
            m.home_pct + m.work_pct + m.public_ac_pct + m.public_dc_pct, 100
        )
        self.assertEqual(m.home_pct, 55)  # residuo +5 absorbido en casa

    def test_preset_home_always(self):
        from apps.mubil.advisor.charging_mix import ChargingMix

        m = ChargingMix.from_preset("particular", "home_always")
        self.assertEqual(m.home_pct, 100)

    def test_weighted_price_public_only_more_expensive_than_home(self):
        from apps.mubil.advisor.charging_mix import ChargingMix

        home = ChargingMix.from_preset("particular", "home_always")
        public = ChargingMix.from_preset("particular", "public_only")
        self.assertGreater(
            public.weighted_price_eur_kwh(night_charging=False),
            home.weighted_price_eur_kwh(night_charging=True),
        )

    def test_mix_invalid_sum_raises(self):
        from apps.mubil.advisor.charging_mix import ChargingMix

        with self.assertRaises(ValueError):
            ChargingMix(50, 50, 50, 50)


class WallboxCapexAndIntegrationTests(TestCase):
    """Tests del flujo completo cuando entra la nueva información de v2."""

    @classmethod
    def setUpTestData(cls):
        cls.golf = Vehicle.objects.create(
            make="Volkswagen",
            model="Golf 1.6 TDI",
            year=2024,
            propulsion=Vehicle.Propulsion.DIESEL,
            consumption_l_100km=Decimal("4.9"),
            price_eur=28_500,
        )
        cls.niro = Vehicle.objects.create(
            make="Kia",
            model="Niro EV",
            year=2025,
            propulsion=Vehicle.Propulsion.BEV,
            consumption_kwh_100km=Decimal("16.2"),
            price_eur=41_500,
        )

    def test_needs_install_adds_wallbox_capex(self):
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            wallbox_state="needs_install",
        )
        self.assertEqual(q.wallbox_capex_eur, Decimal("1500"))
        # Con Programa Auto+, no hay línea de incentivo adicional de wallbox
        codes = {i.code for i in q.incentives.items}
        self.assertNotIn("moves3_wallbox", codes)

    def test_installed_no_wallbox_capex(self):
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            wallbox_state="installed",
        )
        self.assertEqual(q.wallbox_capex_eur, Decimal("0"))
        self.assertNotIn("moves3_wallbox", {i.code for i in q.incentives.items})

    def test_charging_mix_changes_ev_energy_cost(self):
        # Mismo coche, dos mixes distintos → coste energético distinto
        q_home = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            home_pct=100,
            work_pct=0,
            public_ac_pct=0,
            public_dc_pct=0,
        )
        q_public = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            home_pct=0,
            work_pct=0,
            public_ac_pct=60,
            public_dc_pct=40,
        )
        self.assertGreater(
            q_public.breakdown_target.energy,
            q_home.breakdown_target.energy,
        )

    def test_empresa_profile_yields_higher_total_incentives(self):
        q_part = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            profile="particular",
        )
        q_emp = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            profile="empresa",
        )
        # Empresa tiene IVA deducible (≈7k) > IRPF particular (≈3k), aunque
        # Programa Auto+ sea menor (2.9k vs 4.5k).
        self.assertGreater(q_emp.subvencion_eur, q_part.subvencion_eur)

    def test_invalid_profile_raises(self):
        with self.assertRaises(ValueError):
            services.calculate_tco_quote(
                cp="20018",
                km_year=15000,
                vehicle_current_id=self.golf.id,
                vehicle_target_id=self.niro.id,
                profile="other",
            )

    def test_price_override_does_not_touch_db(self):
        # Override en sesión: el cálculo usa otro precio pero v.price_eur
        # en BBDD queda intacto.
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            vehicle_target_price_override_eur=50_000,  # diferente del 41.500 real
            purchase_mode="new_vs_new",
        )
        self.assertEqual(q.vehicle_target_price_used_eur, 50_000)
        self.assertEqual(q.vehicle_current_price_used_eur, 28_500)
        # BBDD intacta
        from apps.mubil.models import Vehicle as V

        self.assertEqual(V.objects.get(pk=self.niro.id).price_eur, 41_500)

    def test_price_override_changes_payback(self):
        base = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            subvencion_override_eur=0,
        )
        with_higher = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            subvencion_override_eur=0,
            vehicle_target_price_override_eur=60_000,  # más caro → payback peor
        )
        self.assertGreater(with_higher.payback_years, base.payback_years)

    def test_replace_purchase_mode_math(self):
        # En replace, current_price_used es el PVP nuevo (28.500)
        # pero current_residual_value_eur es el valor residual del usado (ej. depreciado a 5 años).
        q = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            purchase_mode="replace",
            current_age_years=5,
        )
        self.assertEqual(q.purchase_mode, "replace")
        self.assertEqual(q.vehicle_current_price_used_eur, 28_500)
        # Valor de reventa con 5 años de depreciación: 28500 * (0.85^5) = 12645.5 → ~12646
        self.assertEqual(q.current_residual_value_eur, 12646)
        # La inversión diferencial (delta) en el payback es PVP target (41500) - PVP current (28500) = 13000
        # menos la subvención por defecto (5500) = 7500.
        # Comparamos que sea igual al payback de new_vs_new con los mismos inputs
        q_new = services.calculate_tco_quote(
            cp="20018",
            km_year=15000,
            vehicle_current_id=self.golf.id,
            vehicle_target_id=self.niro.id,
            purchase_mode="new_vs_new",
        )
        self.assertEqual(q.payback_years, q_new.payback_years)


class PriceHeuristicTests(TestCase):
    """Calibración + estimación del módulo `price_heuristic`."""

    def test_tier_lookup_handles_compound_make(self):
        from apps.mubil.data.price_heuristic import tier_for_make

        self.assertEqual(tier_for_make("Volkswagen Canarias"), "mid")
        self.assertEqual(tier_for_make("BMW Group"), "premium")
        self.assertEqual(tier_for_make("Dacia"), "budget")
        self.assertEqual(tier_for_make("MarcaInventada"), "mid")  # default

    def test_calibrate_with_minimal_anchors(self):
        from decimal import Decimal as D

        from apps.mubil.data.price_heuristic import calibrate

        anchors = [
            Vehicle.objects.create(
                make="Dacia",
                model="Spring",
                year=2025,
                propulsion="BEV",
                battery_kwh=D("26.8"),
                price_eur=18500,
                price_source="manual",
            ),
            Vehicle.objects.create(
                make="Tesla",
                model="Model 3",
                year=2025,
                propulsion="BEV",
                battery_kwh=D("60"),
                price_eur=39990,
                price_source="manual",
            ),
            Vehicle.objects.create(
                make="BMW",
                model="i4",
                year=2025,
                propulsion="BEV",
                battery_kwh=D("83.9"),
                price_eur=60900,
                price_source="manual",
            ),
        ]
        table = calibrate(anchors)
        self.assertEqual(table.n_anchors, 3)
        # premium mediana = (39990 + 60900) / 2 → 50445 (statistics.median)
        self.assertEqual(table.cluster_median_price[("BEV", "premium")], 50445)
        self.assertEqual(table.cluster_median_price[("BEV", "budget")], 18500)

    def test_estimate_uses_cluster_median_and_battery_adjustment(self):
        from decimal import Decimal as D

        from apps.mubil.data.price_heuristic import calibrate

        anchors = [
            Vehicle.objects.create(
                make="Tesla",
                model="M3",
                year=2025,
                propulsion="BEV",
                battery_kwh=D("60"),
                price_eur=40000,
                price_source="manual",
            ),
            Vehicle.objects.create(
                make="BMW",
                model="i4",
                year=2025,
                propulsion="BEV",
                battery_kwh=D("80"),
                price_eur=60000,
                price_source="manual",
            ),
        ]
        table = calibrate(anchors)
        # Predicción para BEV premium con 70 kWh: mediana base 50000,
        # mediana batería 70 kWh → delta 0 → precio 50000.
        pred = table.estimate(propulsion="BEV", make="Audi", battery_kwh=D("70"))
        self.assertEqual(pred, 50000)
        # 100 kWh → +30 kWh × 250 €/kWh = +7500
        pred_big = table.estimate(
            propulsion="BEV", make="Porsche", battery_kwh=D("100")
        )
        self.assertEqual(pred_big, 50000 + 7500)

    def test_estimate_falls_back_to_propulsion_median_when_cluster_empty(self):
        from apps.mubil.data.price_heuristic import calibrate

        anchors = [
            Vehicle.objects.create(
                make="Toyota",
                model="Yaris",
                year=2025,
                propulsion="ICE",
                price_eur=19500,
                price_source="manual",
            ),
        ]
        table = calibrate(anchors)
        # No hay nada en ICE/premium → fallback al fallback de propulsion → 19500
        pred = table.estimate(propulsion="ICE", make="BMW", battery_kwh=None)
        self.assertEqual(pred, 19500)


class GeminiPriceLookupTests(TestCase):
    """Parser de la respuesta Gemini (sin red, sólo unit)."""

    def test_parses_plain_json(self):
        from apps.mubil.data.gemini_price_lookup import _parse_response

        est = _parse_response('{"price_eur": 34500, "confidence": 0.85}')
        self.assertEqual(est.price_eur, 34500)
        self.assertEqual(est.confidence, 0.85)

    def test_parses_json_wrapped_in_markdown_fences(self):
        from apps.mubil.data.gemini_price_lookup import _parse_response

        est = _parse_response('```json\n{"price_eur": 28000, "confidence": 0.7}\n```')
        self.assertEqual(est.price_eur, 28000)

    def test_parses_json_with_leading_chatter(self):
        from apps.mubil.data.gemini_price_lookup import _parse_response

        est = _parse_response('Aquí tienes: {"price_eur": 22000, "confidence": 0.6}')
        self.assertEqual(est.price_eur, 22000)

    def test_returns_none_on_garbage(self):
        from apps.mubil.data.gemini_price_lookup import _parse_response

        est = _parse_response("no tengo ni idea")
        self.assertIsNone(est.price_eur)
        self.assertEqual(est.confidence, 0.0)

    def test_validate_against_heuristic_within_tolerance(self):
        from apps.mubil.data.gemini_price_lookup import validate_against_heuristic

        # Gemini 35k vs heurística 30k → diff 16,7 % → OK
        self.assertTrue(
            validate_against_heuristic(gemini_price=35000, heuristic_price=30000)
        )
        # Gemini 80k vs heurística 30k → diff 166 % → rechazar
        self.assertFalse(
            validate_against_heuristic(gemini_price=80000, heuristic_price=30000)
        )
