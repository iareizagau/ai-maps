"""Schemas for `advisor`. PROPUESTA.md §3.1."""

from decimal import Decimal
from typing import List, Optional

from ninja import Schema


class AdvisorQuoteIn(Schema):
    cp: str
    km_year: int
    vehicle_current_id: int
    vehicle_target_id: int
    years_horizon: int = 10
    night_charging: bool = False
    subvencion_eur: int = 0


class VehicleSummary(Schema):
    id: int
    make: str
    model: str
    year: int
    propulsion: str
    price_eur: Optional[int] = None


class CostBreakdownOut(Schema):
    energy: Decimal
    maintenance: Decimal
    insurance: Decimal
    taxes: Decimal
    total: Decimal


class ChargerOut(Schema):
    id: int
    operator: str
    power_kw: Optional[Decimal] = None
    latitude: float
    longitude: float
    address: str
    distance_km: Optional[float] = None


class AdvisorQuoteOut(Schema):
    cp: str
    cp_name: Optional[str] = None
    km_year: int
    years_horizon: int
    vehicle_current: VehicleSummary
    vehicle_target: VehicleSummary
    breakdown_current: CostBreakdownOut
    breakdown_target: CostBreakdownOut
    total_cost_current: Decimal
    total_cost_target: Decimal
    co2_kg_year_current: Decimal
    co2_kg_year_target: Decimal
    co2_saved_kg_year: Decimal
    payback_years: Optional[Decimal] = None
    subvencion_eur: Decimal = Decimal("0")
    nearby_chargers: List[ChargerOut] = []
