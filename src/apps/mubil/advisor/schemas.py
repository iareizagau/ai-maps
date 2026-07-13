"""Schemas for `advisor`. PROPUESTA.md §3.1."""

from decimal import Decimal

from ninja import Schema


class AdvisorQuoteIn(Schema):
    cp: str
    km_year: int
    vehicle_current_id: int
    vehicle_target_id: int
    years_horizon: int = 10
    night_charging: bool = False
    subvencion_eur: int = 0
    motorway_pct: float | None = None
    nacional_pct: float | None = None
    # Fiscal & charging context (v2)
    profile: str = "particular"  # particular | autonomo | empresa
    scrapping: bool = False
    wallbox_state: str = "installed"  # installed | needs_install | no_home
    home_pct: int | None = None
    work_pct: int | None = None
    public_ac_pct: int | None = None
    public_dc_pct: int | None = None
    subvencion_override_eur: int | None = None
    vehicle_current_price_override_eur: int | None = None
    vehicle_target_price_override_eur: int | None = None
    # Modo de comparación para clarificar el framing del payback.
    # 'switch'    (default) = ya tienes el coche actual; el "precio current"
    #                         es valor residual aproximado por depreciación.
    # 'new_vs_new'           = aún no compraste — comparas PVPs nuevos.
    # El cálculo en sí usa `vehicle_current_price_override_eur` cuando viene;
    # este flag se mantiene sólo para que el resultado pueda renderizar el
    # mensaje correcto.
    purchase_mode: str | None = "switch"
    current_age_years: int | None = None
    assembled_in_eu: bool | None = None
    battery_made_in_eu: bool | None = None


class VehicleSummary(Schema):
    id: int
    make: str
    model: str
    year: int
    propulsion: str
    # Category EU (M1=turismo, N1=furgoneta…). Lo expone el API para que el
    # frontend pueda avisar al usuario si está comparando categorías mixtas
    # (p.ej. Vito N1 vs Torres ADVENTURE M1).
    category: str | None = None
    price_eur: int | None = None
    price_source: str | None = None
    dgt_label: str | None = None
    range_wltp_km: int | None = None
    consumption_kwh_100km: Decimal | None = None
    consumption_l_100km: Decimal | None = None
    # Metadatos de agrupación por (make, model_base, category). Si el grupo
    # es singleton, variant_count=1 y los rangos coinciden con el único.
    variant_count: int = 1
    consumption_min: Decimal | None = None
    consumption_max: Decimal | None = None
    assembled_in_eu: bool = False
    battery_made_in_eu: bool = False


class RecommendOut(Schema):
    ice_generic_id: int
    candidates: list[VehicleSummary]


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
    power_kw: Decimal | None = None
    latitude: float
    longitude: float
    address: str
    distance_km: float | None = None


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
    items: list[IncentiveOut] = []


class ChargingMixOut(Schema):
    home_pct: int
    work_pct: int
    public_ac_pct: int
    public_dc_pct: int


class AdvisorQuoteOut(Schema):
    cp: str
    cp_name: str | None = None
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
    payback_years: Decimal | None = None
    subvencion_eur: Decimal = Decimal("0")
    nearby_chargers: list[ChargerOut] = []
    motorway_pct: float | None = None
    nacional_pct: float | None = None
    urban_pct: float | None = None
    charging_mix: ChargingMixOut | None = None
    weighted_charging_eur_kwh: Decimal | None = None
    incentives: IncentivesBreakdownOut | None = None
    wallbox_capex_eur: Decimal = Decimal("0")
    # Eco del input para que el resultado pueda renderizar el framing
    # apropiado ("vendes tu Vito por X" vs "compras Vito nuevo por Y").
    purchase_mode: str | None = "switch"
    current_age_years: int | None = None
    current_residual_value_eur: int | None = None
    # Composición del ahorro a horizon, ver TCOQuote para fórmula completa.
    operational_savings_eur: Decimal | None = None
    purchase_savings_eur: Decimal | None = None
    total_net_savings_eur: Decimal | None = None
