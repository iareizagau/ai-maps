"""Cálculo automático de incentivos para la compra de un BEV.

Sustituye al campo único `subvencion_eur` por un desglose auditable. El
usuario elige un perfil fiscal y declara si achatarra / instala wallbox;
el servicio resuelve qué reglas aplican y devuelve un breakdown que la UI
pinta línea a línea. El total agregado sigue alimentando el cálculo de
payback en `services.calculate_tco_quote`.

Reglas modeladas (vigentes 2026):
- Moves III vehículo (particular / empresa, con/sin achatarramiento).
- Moves III infraestructura (wallbox).
- Deducción IRPF 15% (sólo particulares, base máx. 20k €).
- Bonificación IVTM por provincia (flujo anual capitalizado al horizonte).
- IVA deducible (autónomos 50%, empresas 100%).

Ámbito v1: importes Moves de partícipes individuales y micro-empresas. No
distingue subcategorías regionales de Plan Renove (que reabren cada año
con criterios distintos) — esa capa se añade cuando tengamos catálogo.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from apps.mubil.data.price_defaults import (
    AUTO_PLUS_CONCESSIONAIRE_DISCOUNT,
    AUTO_PLUS_LIMIT_SIN_IVA,
    AUTO_PLUS_MAX_HELP,
    IRPF_BEV_BASE_MAX_EUR,
    IRPF_BEV_DEDUCCION_PCT,
    IVA_DEDUCIBLE_AUTONOMO_PCT,
    IVA_DEDUCIBLE_EMPRESA_PCT,
    IVA_RATE,
    IVTM_BEV_BASE_EUR_YEAR,
    IVTM_BONIF_PCT_BY_PROVINCE,
    cp_to_province,
)
from apps.mubil.models import Vehicle

Profile = Literal["particular", "autonomo", "empresa"]


@dataclass(frozen=True)
class Incentive:
    """Una línea de incentivo. `recurring=True` significa flujo anual."""

    code: str
    name: str
    amount_eur: Decimal
    recurring: bool = False  # True → ahorro €/año; False → lump-sum año 0

    def equivalent_lump_sum(self, years_horizon: int) -> Decimal:
        """Convierte un flujo anual al equivalente al año 0 (sin descuento)."""
        if self.recurring:
            return (self.amount_eur * Decimal(years_horizon)).quantize(Decimal("0.01"))
        return self.amount_eur


@dataclass(frozen=True)
class IncentivesBreakdown:
    items: list[Incentive]
    profile: Profile
    province: str
    years_horizon: int

    @property
    def total_lump_sum_eur(self) -> Decimal:
        """Suma todos los incentivos llevados al año 0 (para payback)."""
        return sum(
            (i.equivalent_lump_sum(self.years_horizon) for i in self.items),
            Decimal("0"),
        ).quantize(Decimal("0.01"))

    def to_out(self) -> dict:
        return {
            "profile": self.profile,
            "province": self.province,
            "years_horizon": self.years_horizon,
            "total_eur": self.total_lump_sum_eur,
            "items": [
                {
                    "code": i.code,
                    "name": i.name,
                    "amount_eur": i.amount_eur,
                    "recurring": i.recurring,
                    "equivalent_eur": i.equivalent_lump_sum(self.years_horizon),
                }
                for i in self.items
            ],
        }


# ---------------------------------------------------------------- rules


def _auto_plus_vehicle(
    vehicle_price_eur: int | None,
    propulsion: str,
    category: str,
    assembled_in_eu: bool,
    battery_made_in_eu: bool,
    profile: Profile = "particular",
    scrapping: bool = False,
) -> Incentive | None:
    if not vehicle_price_eur:
        return None

    price_sin_iva = Decimal(vehicle_price_eur) / (Decimal("1") + IVA_RATE)
    if price_sin_iva > AUTO_PLUS_LIMIT_SIN_IVA:
        return Incentive(
            code="auto_plus_vehicle",
            name="Programa Auto+ vehículo (Excluido por precio > 45k€ sin IVA)",
            amount_eur=Decimal("0"),
        )

    # 1. Factor Eléctrico (50% BEV / 25% PHEV)
    if propulsion == "BEV":
        factor_electric = Decimal("0.50")
    elif propulsion == "PHEV":
        factor_electric = Decimal("0.25")
    else:
        return None

    # Base Max Help based on profile and scrapping
    if profile == "particular":
        max_aid = AUTO_PLUS_MAX_HELP.get(category, Decimal("4500"))
        if scrapping:
            max_aid += Decimal("2500")
    else:
        max_aid = Decimal("2900")
        if scrapping:
            max_aid += Decimal("1100")

    # 2. Factor Económico (25% si <= 35k / 15% si <= 45k)
    if price_sin_iva <= Decimal("35000"):
        factor_economic = Decimal("0.25")
    else:
        factor_economic = Decimal("0.15")

    # 3. Factor Europeo (15% montaje + 10% batería)
    factor_eu_assembly = Decimal("0.15") if assembled_in_eu else Decimal("0")
    factor_eu_battery = Decimal("0.10") if battery_made_in_eu else Decimal("0")

    total_pct = (
        factor_electric + factor_economic + factor_eu_assembly + factor_eu_battery
    )
    amount = (max_aid * total_pct).quantize(Decimal("0.01"))

    factors_label = []
    if factor_electric > 0:
        factors_label.append(f"Eléctrico {int(factor_electric * 100)}%")
    if factor_economic > 0:
        factors_label.append(f"Económico {int(factor_economic * 100)}%")
    if factor_eu_assembly > 0:
        factors_label.append("Montaje UE")
    if factor_eu_battery > 0:
        factors_label.append("Batería UE")
    if scrapping:
        factors_label.append("Achatarramiento")

    label = "Programa Auto+ vehículo (" + ", ".join(factors_label) + ")"
    return Incentive(code="auto_plus_vehicle", name=label, amount_eur=amount)


def _auto_plus_concessionaire(profile: Profile) -> Incentive | None:
    # Descuento obligatorio concesionario (1.000 €)
    return Incentive(
        code="auto_plus_concessionaire",
        name="Programa Auto+ descuento concesionario",
        amount_eur=AUTO_PLUS_CONCESSIONAIRE_DISCOUNT,
    )


def _irpf_deduction(
    profile: Profile,
    vehicle_price_eur: int | None,
    auto_plus_aid: Decimal = Decimal("0"),
) -> Incentive | None:
    """RD-ley 5/2023: 15 % sobre base máxima 20.000 €, sólo personas físicas.
    Aplicado sobre el coste de compra neto de ayudas estatales."""
    if profile != "particular" or not vehicle_price_eur:
        return None
    price_after_aid = Decimal(vehicle_price_eur) - auto_plus_aid
    if price_after_aid <= 0:
        return None
    base = min(price_after_aid, IRPF_BEV_BASE_MAX_EUR)
    amount = (base * IRPF_BEV_DEDUCCION_PCT).quantize(Decimal("0.01"))
    return Incentive(
        code="irpf_15",
        name="Deducción IRPF 15 % (RD-ley 5/2023)",
        amount_eur=amount,
    )


def _ivtm_exemption(cp: str) -> Incentive | None:
    province = cp_to_province(cp)
    bonif = IVTM_BONIF_PCT_BY_PROVINCE.get(province, Decimal("0"))
    if bonif <= 0:
        return None
    annual = (IVTM_BEV_BASE_EUR_YEAR * bonif).quantize(Decimal("0.01"))
    label = f"Bonificación IVTM ({province} ~{int(bonif * 100)} %)"
    return Incentive(code="ivtm_bonif", name=label, amount_eur=annual, recurring=True)


def _iva_deducible(profile: Profile, vehicle_price_eur: int | None) -> Incentive | None:
    """IVA deducible para autónomos/empresas. Precio asumido CON IVA."""
    if profile not in ("autonomo", "empresa") or not vehicle_price_eur:
        return None
    price = Decimal(vehicle_price_eur)
    iva_total = price * (IVA_RATE / (Decimal("1") + IVA_RATE))
    pct = (
        IVA_DEDUCIBLE_EMPRESA_PCT
        if profile == "empresa"
        else IVA_DEDUCIBLE_AUTONOMO_PCT
    )
    amount = (iva_total * pct).quantize(Decimal("0.01"))
    pct_label = "100 %" if profile == "empresa" else "50 %"
    return Incentive(
        code="iva_deducible", name=f"IVA deducible ({pct_label})", amount_eur=amount
    )


# ---------------------------------------------------------------- public API


def compute_incentives(
    *,
    profile: Profile,
    cp: str,
    vehicle_price_eur: int | None,
    scrapping: bool,
    needs_wallbox: bool,
    years_horizon: int,
    vehicle: Vehicle | None = None,
    assembled_in_eu: bool | None = None,
    battery_made_in_eu: bool | None = None,
) -> IncentivesBreakdown:
    """Devuelve el desglose completo de incentivos aplicables."""
    # Resolve EEE inputs, with defaults if vehicle is missing
    target_assembled = True
    target_battery = True
    target_propulsion = "BEV"
    target_category = "M1"

    if vehicle is not None:
        target_assembled = vehicle.assembled_in_eu
        target_battery = vehicle.battery_made_in_eu
        target_propulsion = vehicle.propulsion
        target_category = vehicle.category or "M1"

    # Manual overrides from form
    final_assembled = (
        assembled_in_eu if assembled_in_eu is not None else target_assembled
    )
    final_battery = (
        battery_made_in_eu if battery_made_in_eu is not None else target_battery
    )

    auto_plus_veh = _auto_plus_vehicle(
        vehicle_price_eur=vehicle_price_eur,
        propulsion=target_propulsion,
        category=target_category,
        assembled_in_eu=final_assembled,
        battery_made_in_eu=final_battery,
        profile=profile,
        scrapping=scrapping,
    )
    auto_plus_aid = auto_plus_veh.amount_eur if auto_plus_veh else Decimal("0")

    rules = [
        auto_plus_veh,
        _auto_plus_concessionaire(profile),
        _irpf_deduction(profile, vehicle_price_eur, auto_plus_aid),
        _ivtm_exemption(cp),
        _iva_deducible(profile, vehicle_price_eur),
    ]
    items = [r for r in rules if r is not None]
    return IncentivesBreakdown(
        items=items,
        profile=profile,
        province=cp_to_province(cp),
        years_horizon=years_horizon,
    )
