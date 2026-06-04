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
    motorway_pct: Optional[float] = None
    nacional_pct: Optional[float] = None
    # Fiscal & charging context (v2)
    profile: str = "particular"           # particular | autonomo | empresa
    scrapping: bool = False
    wallbox_state: str = "installed"      # installed | needs_install | no_home
    home_pct: Optional[int] = None
    work_pct: Optional[int] = None
    public_ac_pct: Optional[int] = None
    public_dc_pct: Optional[int] = None
    subvencion_override_eur: Optional[int] = None
    vehicle_current_price_override_eur: Optional[int] = None
    vehicle_target_price_override_eur: Optional[int] = None



class VehicleSummary(Schema):
    id: int
    make: str
    model: str
    year: int
    propulsion: str
    price_eur: Optional[int] = None
    price_source: Optional[str] = None
    dgt_label: Optional[str] = None
    range_wltp_km: Optional[int] = None
    consumption_kwh_100km: Optional[Decimal] = None
    consumption_l_100km: Optional[Decimal] = None
    # Metadatos de agrupación por (make, model_base). Si el grupo es
    # singleton, variant_count=1 y los rangos coinciden con el valor único.
    variant_count: int = 1
    consumption_min: Optional[Decimal] = None
    consumption_max: Optional[Decimal] = None


class RecommendOut(Schema):
    ice_generic_id: int
    candidates: List[VehicleSummary]


class RouteCommuteIn(Schema):
    start_lng: float
    start_lat: float
    end_lng: float
    end_lat: float


class RouteCommuteOut(Schema):
    distance_km: float
    motorway_pct: float
    nacional_pct: float
    urban_pct: float
    route_geojson: dict



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


class IncentiveOut(Schema):
    code: str
    name: str
    amount_eur: Decimal
    recurring: bool = False
    equivalent_eur: Decimal


class IncentivesBreakdownOut(Schema):
    profile: str
    province: str
    years_horizon: int
    total_eur: Decimal
    items: List[IncentiveOut] = []


class ChargingMixOut(Schema):
    home_pct: int
    work_pct: int
    public_ac_pct: int
    public_dc_pct: int


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
    motorway_pct: Optional[float] = None
    nacional_pct: Optional[float] = None
    urban_pct: Optional[float] = None
    charging_mix: Optional[ChargingMixOut] = None
    weighted_charging_eur_kwh: Optional[Decimal] = None
    incentives: Optional[IncentivesBreakdownOut] = None
    wallbox_capex_eur: Decimal = Decimal("0")
