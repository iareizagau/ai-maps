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
from typing import Literal, Optional

from apps.mubil.data.price_defaults import (
    IRPF_BEV_BASE_MAX_EUR,
    IRPF_BEV_DEDUCCION_PCT,
    IVA_DEDUCIBLE_AUTONOMO_PCT,
    IVA_DEDUCIBLE_EMPRESA_PCT,
    IVA_RATE,
    IVTM_BEV_BASE_EUR_YEAR,
    IVTM_BONIF_PCT_BY_PROVINCE,
    MOVES3_BEV_EMPRESA_EUR,
    MOVES3_BEV_EMPRESA_SCRAP_EUR,
    MOVES3_BEV_PARTICULAR_EUR,
    MOVES3_BEV_PARTICULAR_SCRAP_EUR,
    MOVES3_WALLBOX_EMPRESA_EUR,
    MOVES3_WALLBOX_PARTICULAR_EUR,
    cp_to_province,
)

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


def _auto_plus_vehicle(profile: Profile, scrapping: bool) -> Optional[Incentive]:
    if profile == "particular":
        amount = MOVES3_BEV_PARTICULAR_SCRAP_EUR if scrapping else MOVES3_BEV_PARTICULAR_EUR
    else:
        amount = MOVES3_BEV_EMPRESA_SCRAP_EUR if scrapping else MOVES3_BEV_EMPRESA_EUR
    label = "Programa Auto+ vehículo" + (" + achatarramiento" if scrapping else "")
    return Incentive(code="auto_plus_vehicle", name=label, amount_eur=amount)


def _auto_plus_concessionaire(profile: Profile) -> Optional[Incentive]:
    # Descuento obligatorio concesionario (1.000 €)
    return Incentive(code="auto_plus_concessionaire", name="Programa Auto+ descuento concesionario", amount_eur=Decimal("1000"))


def _irpf_deduction(profile: Profile, vehicle_price_eur: Optional[int]) -> Optional[Incentive]:
    """RD-ley 5/2023: 15 % sobre base máxima 20.000 €, sólo personas físicas."""
    if profile != "particular" or not vehicle_price_eur:
        return None
    base = min(Decimal(vehicle_price_eur), IRPF_BEV_BASE_MAX_EUR)
    amount = (base * IRPF_BEV_DEDUCCION_PCT).quantize(Decimal("0.01"))
    return Incentive(code="irpf_15", name="Deducción IRPF 15 % (RD-ley 5/2023)", amount_eur=amount)


def _ivtm_exemption(cp: str) -> Optional[Incentive]:
    province = cp_to_province(cp)
    bonif = IVTM_BONIF_PCT_BY_PROVINCE.get(province, Decimal("0"))
    if bonif <= 0:
        return None
    annual = (IVTM_BEV_BASE_EUR_YEAR * bonif).quantize(Decimal("0.01"))
    label = f"Bonificación IVTM ({province} ~{int(bonif * 100)} %)"
    return Incentive(code="ivtm_bonif", name=label, amount_eur=annual, recurring=True)


def _iva_deducible(profile: Profile, vehicle_price_eur: Optional[int]) -> Optional[Incentive]:
    """IVA deducible para autónomos/empresas. Precio asumido CON IVA."""
    if profile not in ("autonomo", "empresa") or not vehicle_price_eur:
        return None
    price = Decimal(vehicle_price_eur)
    iva_total = price * (IVA_RATE / (Decimal("1") + IVA_RATE))
    pct = IVA_DEDUCIBLE_EMPRESA_PCT if profile == "empresa" else IVA_DEDUCIBLE_AUTONOMO_PCT
    amount = (iva_total * pct).quantize(Decimal("0.01"))
    pct_label = "100 %" if profile == "empresa" else "50 %"
    return Incentive(code="iva_deducible", name=f"IVA deducible ({pct_label})", amount_eur=amount)


# ---------------------------------------------------------------- public API


def compute_incentives(
    *,
    profile: Profile,
    cp: str,
    vehicle_price_eur: Optional[int],
    scrapping: bool,
    needs_wallbox: bool,
    years_horizon: int,
) -> IncentivesBreakdown:
    """Devuelve el desglose completo de incentivos aplicables."""
    rules = [
        _auto_plus_vehicle(profile, scrapping),
        _auto_plus_concessionaire(profile),
        _irpf_deduction(profile, vehicle_price_eur),
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
