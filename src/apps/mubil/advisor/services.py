"""TCO calculation services for the `advisor` module.

PROPUESTA.md §3.1: jurado teclea CP + vehículo actual/objetivo + km/año →
recibe coste total, payback, CO₂ evitado, breakdown de costes y mapa de
cargadores a 5 km del centroide.

La función `calculate_tco_quote` es pura — entrada Python, salida dict
(o pydantic via schemas). Fácil de testear, fácil de cambiar fuentes.

Tests objetivo: precisión ±5% vs valor de mercado real (ver tests/).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from apps.mubil.data import cp_centroids
from apps.mubil.data.price_defaults import (
    CO2_KG_PER_KWH_MIX_ES,
    CO2_KG_PER_LITRE_DIESEL,
    CO2_KG_PER_LITRE_GASOLINA,
    DEFAULT_GASOLEO_A_EUR_L,
    DEFAULT_GASOLINA_95_EUR_L,
    DEFAULT_INSURANCE_EUR_YEAR_EV,
    DEFAULT_INSURANCE_EUR_YEAR_ICE,
    DEFAULT_MAINTENANCE_EUR_YEAR_EV,
    DEFAULT_MAINTENANCE_EUR_YEAR_ICE,
    DEFAULT_PVPC_EUR_KWH,
    DEFAULT_PVPC_VALLE_EUR_KWH,
    DEFAULT_TAX_EUR_YEAR_EV,
    DEFAULT_TAX_EUR_YEAR_ICE,
)
from apps.mubil.models import ChargingStation, Vehicle


@dataclass(frozen=True)
class CostBreakdown:
    energy: Decimal
    maintenance: Decimal
    insurance: Decimal
    taxes: Decimal

    @property
    def total(self) -> Decimal:
        return self.energy + self.maintenance + self.insurance + self.taxes


@dataclass(frozen=True)
class TCOQuote:
    cp: str
    cp_name: Optional[str]
    km_year: int
    years_horizon: int
    vehicle_current: Vehicle
    vehicle_target: Vehicle
    breakdown_current: CostBreakdown
    breakdown_target: CostBreakdown
    co2_kg_year_current: Decimal
    co2_kg_year_target: Decimal
    payback_years: Optional[Decimal]
    nearby_chargers: list[ChargingStation]
    subvencion_eur: Decimal = Decimal("0")


# ------------------------------------------------------------------ helpers


def _is_electric(v: Vehicle) -> bool:
    return v.propulsion == Vehicle.Propulsion.BEV


def _is_diesel(v: Vehicle) -> bool:
    return v.propulsion == Vehicle.Propulsion.DIESEL


def _annual_energy_cost(
    vehicle: Vehicle,
    km_year: int,
    night_charging: bool,
) -> Decimal:
    """Coste anual de energía (€) en función del vehículo, km y régimen tarifario."""
    km = Decimal(km_year)
    if _is_electric(vehicle):
        kwh_100 = vehicle.consumption_kwh_100km or Decimal("17.0")
        kwh = (kwh_100 * km) / Decimal("100")
        price = DEFAULT_PVPC_VALLE_EUR_KWH if night_charging else DEFAULT_PVPC_EUR_KWH
        return (kwh * price).quantize(Decimal("0.01"))
    # combustión / híbrido — usar consumption_l_100km
    l_100 = vehicle.consumption_l_100km or Decimal("6.0")
    litres = (l_100 * km) / Decimal("100")
    price = DEFAULT_GASOLEO_A_EUR_L if _is_diesel(vehicle) else DEFAULT_GASOLINA_95_EUR_L
    return (litres * price).quantize(Decimal("0.01"))


def _annual_co2_kg(vehicle: Vehicle, km_year: int) -> Decimal:
    """Emisiones tank-to-wheel + well-to-tank simplificado (kg CO₂e / año)."""
    km = Decimal(km_year)
    if _is_electric(vehicle):
        kwh_100 = vehicle.consumption_kwh_100km or Decimal("17.0")
        kwh = (kwh_100 * km) / Decimal("100")
        return (kwh * CO2_KG_PER_KWH_MIX_ES).quantize(Decimal("0.1"))
    l_100 = vehicle.consumption_l_100km or Decimal("6.0")
    litres = (l_100 * km) / Decimal("100")
    factor = CO2_KG_PER_LITRE_DIESEL if _is_diesel(vehicle) else CO2_KG_PER_LITRE_GASOLINA
    return (litres * factor).quantize(Decimal("0.1"))


def _breakdown(
    vehicle: Vehicle,
    km_year: int,
    years_horizon: int,
    night_charging: bool,
) -> CostBreakdown:
    horizon = Decimal(years_horizon)
    energy = _annual_energy_cost(vehicle, km_year, night_charging) * horizon
    if _is_electric(vehicle):
        maint = DEFAULT_MAINTENANCE_EUR_YEAR_EV * horizon
        insur = DEFAULT_INSURANCE_EUR_YEAR_EV * horizon
        taxes = DEFAULT_TAX_EUR_YEAR_EV * horizon
    else:
        maint = DEFAULT_MAINTENANCE_EUR_YEAR_ICE * horizon
        insur = DEFAULT_INSURANCE_EUR_YEAR_ICE * horizon
        taxes = DEFAULT_TAX_EUR_YEAR_ICE * horizon
    return CostBreakdown(
        energy=energy.quantize(Decimal("0.01")),
        maintenance=maint.quantize(Decimal("0.01")),
        insurance=insur.quantize(Decimal("0.01")),
        taxes=taxes.quantize(Decimal("0.01")),
    )


def _payback_years(
    current: Vehicle,
    target: Vehicle,
    annual_savings: Decimal,
    subvencion_eur: Decimal = Decimal("0"),
) -> Optional[Decimal]:
    """Payback simple: (delta precio − subvención) / ahorro anual.

    `subvencion_eur` representa ayudas públicas/privadas que se restan del
    sobrecoste de compra del target (típicamente MOVES III + Plan Renove EH).

    Devuelve None si no hay datos de precio o no hay ahorro positivo.
    """
    if not current.price_eur or not target.price_eur or annual_savings <= 0:
        return None
    delta_price = Decimal(target.price_eur - current.price_eur) - subvencion_eur
    if delta_price <= 0:
        # el target neto sale más barato → payback inmediato
        return Decimal("0")
    return (delta_price / annual_savings).quantize(Decimal("0.1"))


def _nearby_chargers(cp: str, radius_km: float = 5.0, limit: int = 25) -> list[ChargingStation]:
    centroid = cp_centroids.lookup(cp)
    if centroid is None:
        return []
    lat, lon, _name = centroid
    qs = ChargingStation.objects.nearby(longitude=lon, latitude=lat, radius_km=radius_km)
    return list(qs[:limit])


# ------------------------------------------------------------------ public API


def calculate_tco_quote(
    *,
    cp: str,
    km_year: int,
    vehicle_current_id: int,
    vehicle_target_id: int,
    years_horizon: int = 10,
    night_charging: bool = False,
    subvencion_eur: int = 0,
) -> TCOQuote:
    """Calcula la comparativa TCO para el `advisor`.

    `subvencion_eur` es la ayuda total a la compra del target (MOVES III + Plan
    Renove EH + descuento marca). Se resta del sobrecoste de compra para el
    payback. Rango admitido: 0-12.000€.

    Lanza Vehicle.DoesNotExist si los IDs no existen y ValueError si los
    parámetros son inválidos.
    """
    if not (1_000 <= km_year <= 60_000):
        raise ValueError(f"km_year fuera de rango (1.000-60.000): {km_year}")
    if not (1 <= years_horizon <= 20):
        raise ValueError(f"years_horizon fuera de rango (1-20): {years_horizon}")
    if not (0 <= subvencion_eur <= 12_000):
        raise ValueError(f"subvencion_eur fuera de rango (0-12.000): {subvencion_eur}")

    current = Vehicle.objects.get(pk=vehicle_current_id)
    target = Vehicle.objects.get(pk=vehicle_target_id)

    bd_current = _breakdown(current, km_year, years_horizon, night_charging)
    bd_target = _breakdown(target, km_year, years_horizon, night_charging)

    annual_savings = (
        _annual_energy_cost(current, km_year, night_charging)
        + (DEFAULT_MAINTENANCE_EUR_YEAR_ICE if not _is_electric(current) else DEFAULT_MAINTENANCE_EUR_YEAR_EV)
        + (DEFAULT_INSURANCE_EUR_YEAR_ICE if not _is_electric(current) else DEFAULT_INSURANCE_EUR_YEAR_EV)
        + (DEFAULT_TAX_EUR_YEAR_ICE if not _is_electric(current) else DEFAULT_TAX_EUR_YEAR_EV)
    ) - (
        _annual_energy_cost(target, km_year, night_charging)
        + (DEFAULT_MAINTENANCE_EUR_YEAR_ICE if not _is_electric(target) else DEFAULT_MAINTENANCE_EUR_YEAR_EV)
        + (DEFAULT_INSURANCE_EUR_YEAR_ICE if not _is_electric(target) else DEFAULT_INSURANCE_EUR_YEAR_EV)
        + (DEFAULT_TAX_EUR_YEAR_ICE if not _is_electric(target) else DEFAULT_TAX_EUR_YEAR_EV)
    )

    centroid = cp_centroids.lookup(cp)
    cp_name = centroid[2] if centroid else None

    return TCOQuote(
        cp=cp,
        cp_name=cp_name,
        km_year=km_year,
        years_horizon=years_horizon,
        vehicle_current=current,
        vehicle_target=target,
        breakdown_current=bd_current,
        breakdown_target=bd_target,
        co2_kg_year_current=_annual_co2_kg(current, km_year),
        co2_kg_year_target=_annual_co2_kg(target, km_year),
        payback_years=_payback_years(
            current, target, annual_savings, Decimal(subvencion_eur)
        ),
        nearby_chargers=_nearby_chargers(cp),
        subvencion_eur=Decimal(subvencion_eur),
    )
