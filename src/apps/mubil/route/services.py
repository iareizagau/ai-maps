"""Route planning services for the MOCK demo (PROPUESTA.md §3.3).

Five precomputed O-D pairs (Donostia ↔ Bilbao / Vitoria / Pamplona / Tolosa /
Eibar) with hand-curated polylines that approximate the real motorway trace,
plus a deterministic energy-and-cost estimator. No pgRouting, no live SOC —
those are §6 follow-up work after the MUBIL submission.

The output shape (``RoutePlanResult``) is what both the JSON API and the
HTMX partial consume. Keeping all map / energy / cost decisions here means
the templates stay JSON-fed and the API can serialise the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from django.db.models import Avg
from django.db.models.functions import ExtractHour

from apps.mubil.data import fuel_ingest, pvpc_ingest
from apps.mubil.models import ChargingStation, EnergyPricePVPC, EVRoutePlan, Vehicle


# ─────────────────────────────────────────────── demo set


# Hand-traced polylines along the main motorway between Euskal Herria pairs.
# Resolution is intentionally coarse (~10 waypoints) — enough for a visible
# Leaflet polyline without shipping a 200-point GeoJSON per route.
ROUTE_DEMOS: List[dict] = [
    {
        "slug": "donostia-bilbao",
        "label": "Donostia ↔ Bilbao",
        "origin_name": "Donostia",
        "dest_name": "Bilbao",
        "origin": (43.3183, -1.9812),
        "dest": (43.2627, -2.9253),
        "via": "AP-8",
        # (lat, lon) waypoints along AP-8 costa: Lasarte, Zarautz, Zumaia,
        # Deba, Mutriku, Ondarroa, Lekeitio, Gernika, Mungia, Bilbao.
        "polyline": [
            (43.3183, -1.9812),
            (43.2710, -2.0782),
            (43.2912, -2.1672),
            (43.2999, -2.2562),
            (43.2785, -2.3502),
            (43.3074, -2.4242),
            (43.3576, -2.4970),
            (43.3144, -2.6810),
            (43.3520, -2.8470),
            (43.2627, -2.9253),
        ],
        "distance_km": Decimal("102"),
        "duration_min": 68,
    },
    {
        "slug": "donostia-vitoria",
        "label": "Donostia ↔ Vitoria",
        "origin_name": "Donostia",
        "dest_name": "Vitoria-Gasteiz",
        "origin": (43.3183, -1.9812),
        "dest": (42.8467, -2.6716),
        "via": "AP-1",
        # (lat, lon) along N-1 / AP-1 via Tolosa, Beasain, Etxegarate,
        # Salvatierra, Vitoria.
        "polyline": [
            (43.3183, -1.9812),
            (43.1944, -2.0570),
            (43.1352, -2.0780),
            (43.0490, -2.2010),
            (42.9750, -2.3120),
            (42.9120, -2.4452),
            (42.8782, -2.5635),
            (42.8467, -2.6716),
        ],
        "distance_km": Decimal("112"),
        "duration_min": 74,
    },
    {
        "slug": "donostia-pamplona",
        "label": "Donostia ↔ Iruñea (Pamplona)",
        "origin_name": "Donostia",
        "dest_name": "Iruñea",
        "origin": (43.3183, -1.9812),
        "dest": (42.8181, -1.6447),
        "via": "AP-15",
        # AP-15 via Andoain, Leitza, Irurtzun, Pamplona.
        "polyline": [
            (43.3183, -1.9812),
            (43.2156, -2.0210),
            (43.0698, -1.9120),
            (42.9930, -1.8020),
            (42.9210, -1.6938),
            (42.8635, -1.6650),
            (42.8181, -1.6447),
        ],
        "distance_km": Decimal("85"),
        "duration_min": 58,
    },
    {
        "slug": "donostia-tolosa",
        "label": "Donostia ↔ Tolosa",
        "origin_name": "Donostia",
        "dest_name": "Tolosa",
        "origin": (43.3183, -1.9812),
        "dest": (43.1352, -2.0780),
        "via": "N-1",
        "polyline": [
            (43.3183, -1.9812),
            (43.2700, -1.9920),
            (43.2156, -2.0210),
            (43.1740, -2.0480),
            (43.1352, -2.0780),
        ],
        "distance_km": Decimal("28"),
        "duration_min": 24,
    },
    {
        "slug": "donostia-eibar",
        "label": "Donostia ↔ Eibar",
        "origin_name": "Donostia",
        "dest_name": "Eibar",
        "origin": (43.3183, -1.9812),
        "dest": (43.1844, -2.4711),
        "via": "AP-8 / AP-1",
        # AP-8 hasta Eibar saliendo por Bergara/Eibar.
        "polyline": [
            (43.3183, -1.9812),
            (43.2710, -2.0782),
            (43.2920, -2.1670),
            (43.2410, -2.2980),
            (43.2080, -2.4060),
            (43.1844, -2.4711),
        ],
        "distance_km": Decimal("48"),
        "duration_min": 38,
    },
]


# ─────────────────────────────────────────────── plan output


@dataclass(frozen=True)
class RouteSegment:
    kind: str  # 'drive' | 'charge_stop'
    distance_km: Optional[Decimal] = None
    duration_min: Optional[int] = None
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RoutePlanResult:
    slug: str
    label: str
    origin_name: str
    dest_name: str
    via: str
    origin: Tuple[float, float]
    dest: Tuple[float, float]
    polyline: List[Tuple[float, float]]
    distance_km: Decimal
    duration_min: int
    energy_kwh: Decimal
    estimated_cost_eur: Decimal
    soc_start_pct: Decimal
    soc_end_pct: Decimal
    segments: List[RouteSegment]
    vehicle_id: Optional[int] = None
    vehicle_label: Optional[str] = None
    # ── Fase 1 additions (Frontend Phase 4 consumes these). All optional so
    # legacy callers and demo seeds keep working without changes.
    mode: str = "demo"                                           # 'demo' | 'free'
    departure_hour: Optional[int] = None                         # 0–23, Madrid local
    soc_curve: List[Tuple[float, float]] = field(default_factory=list)
    cost_by_hour: List[Tuple[int, float]] = field(default_factory=list)
    nearby_chargers: List[dict] = field(default_factory=list)
    selected_charger: Optional[dict] = None
    ice_baseline: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "label": self.label,
            "origin_name": self.origin_name,
            "dest_name": self.dest_name,
            "via": self.via,
            "origin": list(self.origin),
            "dest": list(self.dest),
            "polyline": [list(p) for p in self.polyline],
            "distance_km": float(self.distance_km),
            "duration_min": self.duration_min,
            "energy_kwh": float(self.energy_kwh),
            "estimated_cost_eur": float(self.estimated_cost_eur),
            "soc_start_pct": float(self.soc_start_pct),
            "soc_end_pct": float(self.soc_end_pct),
            "vehicle_id": self.vehicle_id,
            "vehicle_label": self.vehicle_label,
            "mode": self.mode,
            "departure_hour": self.departure_hour,
            "soc_curve": [list(p) for p in self.soc_curve],
            "cost_by_hour": [list(p) for p in self.cost_by_hour],
            "nearby_chargers": self.nearby_chargers,
            "selected_charger": self.selected_charger,
            "ice_baseline": self.ice_baseline,
            "segments": [
                {
                    "kind": s.kind,
                    "distance_km": float(s.distance_km) if s.distance_km is not None else None,
                    "duration_min": s.duration_min,
                    "meta": s.meta,
                }
                for s in self.segments
            ],
        }


# ─────────────────────────────────────────────── public API


# Comfortable EV energy efficiency when consumption_kwh_100km is missing —
# 18 kWh/100km is a fleet-average figure for a B/C-segment BEV (≈ Niro EV,
# Megane E-Tech). Used only as a fallback so a Vehicle row without WLTP
# data still produces a believable plan.
DEFAULT_KWH_PER_100KM = Decimal("18.0")

# 10% reserve. We force a charge stop whenever the trip would end below this
# SOC — leaves headroom for detours / cold-weather range loss.
SOC_RESERVE_PCT = Decimal("10")

# Fast-charger session profile used when a stop is needed.
FAST_CHARGE_KW = Decimal("100")            # representative DC kW
FAST_CHARGE_PRICE_EUR_KWH = Decimal("0.45") # IONITY / Iberdrola fast-DC band

# Stop duration is "energy delivered ÷ effective power" — see
# :func:`_charge_stop_duration_min`. Cap to keep the demo card readable.
MAX_STOP_DURATION_MIN = 45

# Average highway speed across Euskal Herria for free-O/D duration estimation
# when the underlying routing source (OSRM / pgRouting) doesn't return one.
# Calibrated against the demo set: 102 km / 68 min ≈ 90 km/h, 28 km / 24 min
# ≈ 70 km/h — 75 splits the difference.
FREE_MODE_AVG_KMH = Decimal("75")

# Reference ICE gasoline car for the EV vs ICE baseline card. Closest match to
# the IDAE fleet-average B/C-segment petrol that the advisor cites.
ICE_BASELINE_L_PER_100KM = Decimal("6.5")
ICE_BASELINE_FUEL_KEY = "gasolina_95_e5"

# How many waypoints the SOC curve interpolates between the polyline vertices.
# 30 is enough for a smooth ECharts line without bloating the JSON payload.
SOC_CURVE_TARGET_SAMPLES = 30

# Madrid local time matches the PVPC tariff schedule (see pvpc_ingest).
_PVPC_LOCAL_TZ = ZoneInfo("Europe/Madrid")


def _midpoint(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[float, float]:
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


def _charge_stop_duration_min(kwh_to_add: Decimal) -> int:
    """How long a fast-charge stop should take (minutes), capped.

    Real DC sessions taper after ~80% SOC; we don't model that — the demo
    only needs an order-of-magnitude number. ``MAX_STOP_DURATION_MIN``
    keeps the result UI-friendly even on absurd inputs.
    """
    minutes = (kwh_to_add / FAST_CHARGE_KW) * Decimal("60")
    capped = min(int(minutes.to_integral_value()), MAX_STOP_DURATION_MIN)
    return max(capped, 10)  # never show <10 min — implausible


def _vehicle_kwh_per_100km(vehicle: Optional[Vehicle]) -> Decimal:
    if vehicle is None or vehicle.consumption_kwh_100km is None:
        return DEFAULT_KWH_PER_100KM
    return Decimal(vehicle.consumption_kwh_100km)


def _vehicle_battery_kwh(vehicle: Optional[Vehicle]) -> Optional[Decimal]:
    if vehicle is None or vehicle.battery_kwh is None:
        return None
    return Decimal(vehicle.battery_kwh)


def _energy_price_eur_kwh_home() -> Decimal:
    """Best estimate of the home recharge price (€/kWh)."""
    return pvpc_ingest.current_price_eur_kwh(night_charging=True)


# ─────────────────────────────────────────────── new helpers (Phase 1)


def _haversine_km(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1 = p1
    lat2, lon2 = p2
    r = 6371.0088  # WGS-84 mean radius
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _cumulative_km(polyline: List[Tuple[float, float]]) -> List[float]:
    """Cumulative haversine distance at each vertex (km). First entry = 0."""
    if len(polyline) < 2:
        return [0.0] * len(polyline)
    cum = [0.0]
    for i in range(1, len(polyline)):
        cum.append(cum[-1] + _haversine_km(polyline[i - 1], polyline[i]))
    return cum


def _pvpc_24h_curve(window_days: int = 7) -> List[Decimal]:
    """Average PVPC €/kWh per hour-of-day (Madrid local), 24 values, last N days.

    The Frontend Phase 4 chart shows what each departure hour would cost. We
    bucket by Madrid-local hour because the 2.0TD tariff schedule (and what
    the user perceives as "valle" / "punta") is defined in local time.

    Falls back to a flat curve at :func:`pvpc_ingest.current_price_eur_kwh`
    when the table is empty — keeps the FE rendering even on a cold DB.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
    rows = (
        EnergyPricePVPC.objects
        .filter(timestamp__gte=cutoff)
        .annotate(hour=ExtractHour('timestamp', tzinfo=_PVPC_LOCAL_TZ))
        .values('hour')
        .annotate(avg=Avg('price_eur_mwh'))
        .order_by('hour')
    )
    by_hour: dict = {}
    for r in rows:
        if r['avg'] is None:
            continue
        by_hour[int(r['hour'])] = (Decimal(r['avg']) / Decimal('1000'))

    if not by_hour:
        fallback = pvpc_ingest.current_price_eur_kwh(night_charging=False)
        return [Decimal(fallback).quantize(Decimal('0.0001'))] * 24

    overall = sum(by_hour.values(), Decimal('0')) / Decimal(len(by_hour))
    return [
        by_hour.get(h, overall).quantize(Decimal('0.0001'))
        for h in range(24)
    ]


def _cost_by_hour(
    energy_kwh: Decimal,
    kwh_fast_charge: Decimal,
    pvpc_curve: List[Decimal],
) -> List[Tuple[int, float]]:
    """Cost of the trip if it departed at each hour 0..23.

    Model: home/destination charging tracks the hourly PVPC, the en-route
    fast-charge slice is operator-priced and hour-independent. ``energy_kwh``
    is the total trip consumption; we charge the slice that isn't covered by
    fast-DC at the home rate.
    """
    home_kwh = max(energy_kwh - kwh_fast_charge, Decimal('0'))
    fast_cost = (kwh_fast_charge * FAST_CHARGE_PRICE_EUR_KWH)
    out: List[Tuple[int, float]] = []
    for h in range(24):
        c = (home_kwh * pvpc_curve[h] + fast_cost).quantize(Decimal('0.01'))
        out.append((h, float(c)))
    return out


def _ice_trip_cost(distance_km: Decimal, *, postal_code: Optional[str] = None) -> dict:
    """Comparable gasoline-95 trip cost for the EV vs ICE badge."""
    fuel_l = (distance_km * ICE_BASELINE_L_PER_100KM / Decimal('100')).quantize(Decimal('0.01'))
    price_l = fuel_ingest.current_price_eur_l(
        fuel_key=ICE_BASELINE_FUEL_KEY, postal_code=postal_code,
    )
    cost_eur = (fuel_l * price_l).quantize(Decimal('0.01'))
    return {
        "fuel_l": float(fuel_l),
        "price_eur_l": float(price_l.quantize(Decimal('0.001'))),
        "cost_eur": float(cost_eur),
    }


def _ice_vs_ev(ev_cost_eur: Decimal, ice: dict) -> dict:
    """Augments ``ice`` with vs-EV deltas. EV cheaper → positive savings."""
    ice_cost = Decimal(str(ice["cost_eur"]))
    savings = (ice_cost - ev_cost_eur).quantize(Decimal('0.01'))
    pct = Decimal('0')
    if ice_cost > 0:
        pct = (savings / ice_cost * Decimal('100')).quantize(Decimal('0.1'))
    return {
        **ice,
        "vs_ev_eur": float(savings),
        "vs_ev_pct": float(pct),
    }


def _chargers_along_route(
    polyline_latlon: List[Tuple[float, float]],
    *, radius_km: int = 5, min_kw: int = 50, limit: int = 10,
) -> List[dict]:
    """Top-N DC fast chargers within ``radius_km`` of the route line."""
    if len(polyline_latlon) < 2:
        return []
    polyline_lonlat = [(lon, lat) for lat, lon in polyline_latlon]
    qs = (
        ChargingStation.objects
        .filter(power_kw__gte=min_kw)
        .along_route(polyline_lonlat, radius_km=radius_km)[:limit]
    )
    out: List[dict] = []
    for c in qs:
        out.append({
            "id": c.id,
            "operator": c.operator or "",
            "address": c.address or "",
            "power_kw": float(c.power_kw) if c.power_kw is not None else None,
            "lat": c.geom.y,
            "lon": c.geom.x,
            # `distance` is a Distance object (m). Round to km for the UI.
            "distance_km": round(c.distance.m / 1000.0, 2) if c.distance else None,
        })
    return out


def _select_charge_stop(
    polyline_latlon: List[Tuple[float, float]],
    distance_km: Decimal,
    soc_start_pct: Decimal,
    energy_kwh: Decimal,
    battery_kwh: Optional[Decimal],
    nearby_chargers: List[dict],
) -> Optional[dict]:
    """Pick the closest real fast-charger to the point where SOC crosses reserve.

    Returns the matching dict from ``nearby_chargers`` (with ``charge_km``
    annotation), or ``None`` if no stop is needed or no candidate exists.
    """
    if not battery_kwh or battery_kwh <= 0 or not nearby_chargers:
        return None
    kwh_per_km = energy_kwh / distance_km if distance_km > 0 else Decimal('0')
    # km at which SOC would drop to reserve
    soc_drop_kwh = (soc_start_pct - SOC_RESERVE_PCT) / Decimal('100') * battery_kwh
    if soc_drop_kwh >= energy_kwh:
        return None  # arrives with margin, no stop
    if kwh_per_km <= 0:
        return None
    threshold_km = float(soc_drop_kwh / kwh_per_km)

    cum = _cumulative_km(polyline_latlon)
    total_geom = cum[-1] if cum else 0.0
    if total_geom <= 0:
        return None
    scale = float(distance_km) / total_geom
    # Find polyline point closest to threshold (in real km)
    idx = 0
    for i, c in enumerate(cum):
        if c * scale >= threshold_km:
            idx = i
            break
    target = polyline_latlon[idx]

    best = None
    best_d = float('inf')
    for ch in nearby_chargers:
        d = _haversine_km(target, (ch["lat"], ch["lon"]))
        if d < best_d:
            best_d = d
            best = ch
    if best is None:
        return None
    return {**best, "charge_km": round(threshold_km, 1), "detour_km": round(best_d, 2)}


def _soc_curve_points(
    polyline_latlon: List[Tuple[float, float]],
    distance_km: Decimal,
    energy_kwh: Decimal,
    battery_kwh: Optional[Decimal],
    soc_start_pct: Decimal,
    charge_km: Optional[float] = None,
    charge_kwh: Decimal = Decimal('0'),
) -> List[Tuple[float, float]]:
    """``(km_acum, soc_pct)`` samples for the FE line chart.

    Returns ``[]`` when the catalog row has no ``battery_kwh`` — same
    contract as the legacy "no SOC math" branch in :func:`_plan_for_demo`.
    """
    if not battery_kwh or battery_kwh <= 0 or len(polyline_latlon) < 2:
        return []
    cum = _cumulative_km(polyline_latlon)
    total_geom = cum[-1]
    if total_geom <= 0:
        return []
    scale = float(distance_km) / total_geom
    cum_real = [c * scale for c in cum]

    kwh_per_km = float(energy_kwh) / float(distance_km) if distance_km > 0 else 0.0
    soc_per_kwh = 100.0 / float(battery_kwh)
    bump = float(charge_kwh) * soc_per_kwh if charge_km is not None else 0.0

    # Subsample to keep payload bounded — pick evenly-spaced indices.
    n = len(polyline_latlon)
    step = max(1, n // SOC_CURVE_TARGET_SAMPLES)
    indices = list(range(0, n, step))
    if indices[-1] != n - 1:
        indices.append(n - 1)

    out: List[Tuple[float, float]] = []
    soc = float(soc_start_pct)
    bumped = False
    last_km = 0.0
    for i in indices:
        delta_km = cum_real[i] - last_km
        soc -= delta_km * kwh_per_km * soc_per_kwh
        if not bumped and charge_km is not None and cum_real[i] >= charge_km:
            soc = min(100.0, soc + bump)
            bumped = True
        out.append((round(cum_real[i], 2), round(soc, 2)))
        last_km = cum_real[i]
    return out


# ─────────────────────────────────────────────── legacy segment builder


def _build_segments(
    distance_km: Decimal,
    duration_min: int,
    polyline: List[Tuple[float, float]],
    needs_stop: bool,
    kwh_to_add: Decimal,
) -> List[RouteSegment]:
    if not needs_stop:
        return [RouteSegment(kind="drive", distance_km=distance_km, duration_min=duration_min)]

    half_km = (distance_km / Decimal("2")).quantize(Decimal("0.1"))
    half_min = duration_min // 2
    midpoint = _midpoint(polyline[0], polyline[-1])
    stop_min = _charge_stop_duration_min(kwh_to_add)
    return [
        RouteSegment(kind="drive", distance_km=half_km, duration_min=half_min),
        RouteSegment(
            kind="charge_stop",
            duration_min=stop_min,
            meta={
                "location": list(midpoint),
                "kwh_added": float(kwh_to_add.quantize(Decimal("0.1"))),
                "kw_session": float(FAST_CHARGE_KW),
            },
        ),
        RouteSegment(
            kind="drive",
            distance_km=(distance_km - half_km).quantize(Decimal("0.1")),
            duration_min=duration_min - half_min,
        ),
    ]


def _plan_for_demo(
    demo: dict,
    vehicle: Optional[Vehicle],
    soc_start_pct: Decimal,
    *,
    departure_hour: Optional[int] = None,
    postal_code: Optional[str] = None,
) -> RoutePlanResult:
    distance_km = Decimal(demo["distance_km"])
    duration_min = int(demo["duration_min"])
    kwh_per_100 = _vehicle_kwh_per_100km(vehicle)
    energy_kwh = (kwh_per_100 * distance_km / Decimal("100")).quantize(Decimal("0.01"))

    battery_kwh = _vehicle_battery_kwh(vehicle)
    # SOC math is only meaningful when the catalog row carries a battery size.
    # Without it we fall back to "no stop needed" and show the trip as-is —
    # better than fabricating a charge_stop on imaginary capacity.
    if battery_kwh and battery_kwh > 0:
        soc_consumed_pct = (energy_kwh / battery_kwh * Decimal("100")).quantize(Decimal("0.1"))
        soc_end_pct = (soc_start_pct - soc_consumed_pct).quantize(Decimal("0.1"))
        needs_stop = soc_end_pct < SOC_RESERVE_PCT
    else:
        soc_end_pct = (soc_start_pct - Decimal("0")).quantize(Decimal("0.1"))
        needs_stop = False

    if needs_stop and battery_kwh:
        # Top up just enough to land at ~80% (typical fast-charge cut-off
        # before taper). kwh_to_add is the energy delivered during the stop.
        target_soc = Decimal("80")
        kwh_to_add = ((target_soc - soc_end_pct) / Decimal("100") * battery_kwh).quantize(Decimal("0.1"))
        if kwh_to_add < Decimal("5"):
            # Anything <5 kWh is below the noise floor for a real stop.
            needs_stop = False
            kwh_to_add = Decimal("0")
    else:
        kwh_to_add = Decimal("0")

    price_home = _energy_price_eur_kwh_home()
    drive_cost = (energy_kwh * price_home).quantize(Decimal("0.01"))
    stop_cost = (kwh_to_add * FAST_CHARGE_PRICE_EUR_KWH).quantize(Decimal("0.01"))
    estimated_cost_eur = (drive_cost + stop_cost).quantize(Decimal("0.01"))

    if needs_stop:
        stop_min = _charge_stop_duration_min(kwh_to_add)
        total_duration_min = duration_min + stop_min
        soc_end_pct = (soc_end_pct + (kwh_to_add / battery_kwh * Decimal("100"))).quantize(Decimal("0.1"))
    else:
        total_duration_min = duration_min

    segments = _build_segments(distance_km, duration_min, demo["polyline"], needs_stop, kwh_to_add)

    polyline = demo["polyline"]
    nearby_chargers = _chargers_along_route(polyline)
    selected_charger = (
        _select_charge_stop(polyline, distance_km, soc_start_pct, energy_kwh,
                            battery_kwh, nearby_chargers)
        if needs_stop else None
    )
    charge_km = float(selected_charger["charge_km"]) if selected_charger else None
    soc_curve = _soc_curve_points(
        polyline, distance_km, energy_kwh, battery_kwh, soc_start_pct,
        charge_km=charge_km, charge_kwh=kwh_to_add,
    )
    pvpc_curve = _pvpc_24h_curve()
    cost_by_hour = _cost_by_hour(energy_kwh, kwh_to_add, pvpc_curve)
    ice_baseline = _ice_vs_ev(estimated_cost_eur,
                              _ice_trip_cost(distance_km, postal_code=postal_code))

    return RoutePlanResult(
        slug=demo["slug"],
        label=demo["label"],
        origin_name=demo["origin_name"],
        dest_name=demo["dest_name"],
        via=demo["via"],
        origin=demo["origin"],
        dest=demo["dest"],
        polyline=polyline,
        distance_km=distance_km,
        duration_min=total_duration_min,
        energy_kwh=energy_kwh,
        estimated_cost_eur=estimated_cost_eur,
        soc_start_pct=soc_start_pct,
        soc_end_pct=soc_end_pct,
        segments=segments,
        vehicle_id=vehicle.id if vehicle else None,
        vehicle_label=f"{vehicle.make} {vehicle.model}" if vehicle else None,
        mode="demo",
        departure_hour=departure_hour,
        soc_curve=soc_curve,
        cost_by_hour=cost_by_hour,
        nearby_chargers=nearby_chargers,
        selected_charger=selected_charger,
        ice_baseline=ice_baseline,
    )


def list_demos() -> List[dict]:
    """Lightweight metadata for the route selector dropdown / API list."""
    return [
        {
            "slug": d["slug"],
            "label": d["label"],
            "origin_name": d["origin_name"],
            "dest_name": d["dest_name"],
            "via": d["via"],
            "distance_km": float(Decimal(d["distance_km"])),
            "duration_min": int(d["duration_min"]),
        }
        for d in ROUTE_DEMOS
    ]


def get_demo(slug: str) -> Optional[dict]:
    for d in ROUTE_DEMOS:
        if d["slug"] == slug:
            return d
    return None


def _polyline_from_route_geojson(route_geojson: dict) -> List[Tuple[float, float]]:
    """Flatten a FeatureCollection of LineStrings into a ``(lat, lon)`` list.

    Matches the shape returned by ``advisor.services.get_commute_route``
    (pgRouting fan-out as N segments, or OSRM as one). Duplicate consecutive
    points across feature boundaries are dropped.
    """
    out: List[Tuple[float, float]] = []
    features = (route_geojson or {}).get("features", [])
    for feat in features:
        geom = (feat or {}).get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        for lon, lat in geom.get("coordinates", []):
            pt = (float(lat), float(lon))
            if not out or out[-1] != pt:
                out.append(pt)
    return out


def _plan_for_free_od(
    *,
    origin_lng: float, origin_lat: float,
    dest_lng: float, dest_lat: float,
    vehicle: Optional[Vehicle],
    soc_start_pct: Decimal,
    departure_hour: Optional[int],
    postal_code: Optional[str],
) -> RoutePlanResult:
    """Plan a route with arbitrary origin/destination via advisor's pgRouting.

    Reuses :func:`advisor.services.get_commute_route` for the heavy lifting
    (pgRouting → OSRM → straight-line fallback ladder) so we get a real road
    polyline whenever the OSM topology covers the request.
    """
    # Local import: keep advisor isolation; avoids circular imports if the
    # advisor ever imports route helpers.
    from apps.mubil.advisor.services import get_commute_route

    route = get_commute_route(origin_lng, origin_lat, dest_lng, dest_lat)
    distance_km = Decimal(str(route.get("distance_km") or 0)).quantize(Decimal("0.01"))
    if distance_km <= 0:
        raise ValueError("Routing returned zero distance")

    polyline = _polyline_from_route_geojson(route.get("route_geojson") or {})
    if len(polyline) < 2:
        # Fallback to the bare O/D line so downstream consumers (map, SOC
        # curve) always have something to render. This mirrors what the
        # advisor's geometric fallback does.
        polyline = [(origin_lat, origin_lng), (dest_lat, dest_lng)]

    # Duration: routing layer doesn't surface one; estimate from avg speed.
    duration_min = int((distance_km / FREE_MODE_AVG_KMH * Decimal("60")).to_integral_value())

    kwh_per_100 = _vehicle_kwh_per_100km(vehicle)
    energy_kwh = (kwh_per_100 * distance_km / Decimal("100")).quantize(Decimal("0.01"))
    battery_kwh = _vehicle_battery_kwh(vehicle)

    if battery_kwh and battery_kwh > 0:
        soc_consumed_pct = (energy_kwh / battery_kwh * Decimal("100")).quantize(Decimal("0.1"))
        soc_end_pct = (soc_start_pct - soc_consumed_pct).quantize(Decimal("0.1"))
        needs_stop = soc_end_pct < SOC_RESERVE_PCT
    else:
        soc_end_pct = soc_start_pct.quantize(Decimal("0.1"))
        needs_stop = False

    if needs_stop and battery_kwh:
        target_soc = Decimal("80")
        kwh_to_add = ((target_soc - soc_end_pct) / Decimal("100") * battery_kwh).quantize(Decimal("0.1"))
        if kwh_to_add < Decimal("5"):
            needs_stop = False
            kwh_to_add = Decimal("0")
    else:
        kwh_to_add = Decimal("0")

    price_home = _energy_price_eur_kwh_home()
    drive_cost = (energy_kwh * price_home).quantize(Decimal("0.01"))
    stop_cost = (kwh_to_add * FAST_CHARGE_PRICE_EUR_KWH).quantize(Decimal("0.01"))
    estimated_cost_eur = (drive_cost + stop_cost).quantize(Decimal("0.01"))

    if needs_stop:
        stop_min = _charge_stop_duration_min(kwh_to_add)
        total_duration_min = duration_min + stop_min
        soc_end_pct = (soc_end_pct + (kwh_to_add / battery_kwh * Decimal("100"))).quantize(Decimal("0.1"))
    else:
        total_duration_min = duration_min

    segments = _build_segments(distance_km, duration_min, polyline, needs_stop, kwh_to_add)

    nearby_chargers = _chargers_along_route(polyline)
    selected_charger = (
        _select_charge_stop(polyline, distance_km, soc_start_pct, energy_kwh,
                            battery_kwh, nearby_chargers)
        if needs_stop else None
    )
    charge_km = float(selected_charger["charge_km"]) if selected_charger else None
    soc_curve = _soc_curve_points(
        polyline, distance_km, energy_kwh, battery_kwh, soc_start_pct,
        charge_km=charge_km, charge_kwh=kwh_to_add,
    )
    pvpc_curve = _pvpc_24h_curve()
    cost_by_hour = _cost_by_hour(energy_kwh, kwh_to_add, pvpc_curve)
    ice_baseline = _ice_vs_ev(estimated_cost_eur,
                              _ice_trip_cost(distance_km, postal_code=postal_code))

    label = f"{origin_lat:.4f},{origin_lng:.4f} → {dest_lat:.4f},{dest_lng:.4f}"
    return RoutePlanResult(
        slug="free",
        label=label,
        origin_name="Origen",
        dest_name="Destino",
        via="",
        origin=(origin_lat, origin_lng),
        dest=(dest_lat, dest_lng),
        polyline=polyline,
        distance_km=distance_km,
        duration_min=total_duration_min,
        energy_kwh=energy_kwh,
        estimated_cost_eur=estimated_cost_eur,
        soc_start_pct=soc_start_pct,
        soc_end_pct=soc_end_pct,
        segments=segments,
        vehicle_id=vehicle.id if vehicle else None,
        vehicle_label=f"{vehicle.make} {vehicle.model}" if vehicle else None,
        mode="free",
        departure_hour=departure_hour,
        soc_curve=soc_curve,
        cost_by_hour=cost_by_hour,
        nearby_chargers=nearby_chargers,
        selected_charger=selected_charger,
        ice_baseline=ice_baseline,
    )


def plan(
    *,
    slug: Optional[str] = None,
    origin_lng: Optional[float] = None,
    origin_lat: Optional[float] = None,
    dest_lng: Optional[float] = None,
    dest_lat: Optional[float] = None,
    vehicle_id: Optional[int] = None,
    soc_start_pct: float = 80.0,
    departure_hour: Optional[int] = None,
    postal_code: Optional[str] = None,
) -> RoutePlanResult:
    """Build a :class:`RoutePlanResult`.

    Dispatch:
        * ``slug`` set → use one of :data:`ROUTE_DEMOS` (fast, no pgRouting).
        * O/D coords set (all four) → call ``advisor.get_commute_route`` for
          a real-roads polyline.

    Args:
        slug: one of :data:`ROUTE_DEMOS` slugs. Takes precedence over O/D.
        origin_lng/origin_lat/dest_lng/dest_lat: free-mode endpoints.
        vehicle_id: optional :class:`Vehicle` pk. If ``None`` the plan uses
            :data:`DEFAULT_KWH_PER_100KM` and skips SOC math (no stops).
        soc_start_pct: starting battery percentage, 0-100.
        departure_hour: 0-23 Madrid local; only carried through to the FE so
            the hour-cost chart can highlight it.
        postal_code: optional CP for the ICE fuel-price baseline lookup.
    """
    if not (0 <= soc_start_pct <= 100):
        raise ValueError(f"soc_start_pct out of range (0-100): {soc_start_pct}")
    if departure_hour is not None and not (0 <= departure_hour <= 23):
        raise ValueError(f"departure_hour out of range (0-23): {departure_hour}")

    vehicle = None
    if vehicle_id is not None:
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            raise ValueError(f"Vehicle id={vehicle_id} not found")

    if slug:
        demo = get_demo(slug)
        if demo is None:
            raise ValueError(f"Unknown route slug: {slug}")
        return _plan_for_demo(
            demo, vehicle, Decimal(str(soc_start_pct)),
            departure_hour=departure_hour, postal_code=postal_code,
        )

    coords = (origin_lng, origin_lat, dest_lng, dest_lat)
    if any(c is None for c in coords):
        raise ValueError(
            "plan() requires either `slug` or all four O/D coordinates"
        )
    return _plan_for_free_od(
        origin_lng=float(origin_lng), origin_lat=float(origin_lat),
        dest_lng=float(dest_lng), dest_lat=float(dest_lat),
        vehicle=vehicle,
        soc_start_pct=Decimal(str(soc_start_pct)),
        departure_hour=departure_hour,
        postal_code=postal_code,
    )


# ─────────────────────────────────────────────── seed (persist demo plans)


def upsert_demo_plans(default_vehicle: Optional[Vehicle] = None) -> int:
    """Persist the 5 demos into :class:`EVRoutePlan` (idempotent).

    Used by ``manage.py seed_route_demos``. The cache row is keyed on the
    origin/dest geometry — re-running the seed overwrites the previous
    snapshot rather than duplicating it.
    """
    from django.contrib.gis.geos import Point

    count = 0
    for demo in ROUTE_DEMOS:
        plan_result = _plan_for_demo(demo, default_vehicle, Decimal("80"))
        origin = Point(demo["origin"][1], demo["origin"][0], srid=4326)
        dest = Point(demo["dest"][1], demo["dest"][0], srid=4326)
        defaults = {
            "vehicle": default_vehicle,
            "soc_start": Decimal("80.00"),
            "geojson": plan_result.to_dict(),
            "distance_km": plan_result.distance_km,
            "duration_min": plan_result.duration_min,
            "energy_kwh": plan_result.energy_kwh,
            "estimated_cost_eur": plan_result.estimated_cost_eur,
        }
        # No natural-key UNIQUE on the model — match the previous row for the
        # same (origin, dest, vehicle) tuple to keep the cache idempotent.
        existing = EVRoutePlan.objects.filter(
            origin=origin, dest=dest, vehicle=default_vehicle,
        ).first()
        if existing is None:
            EVRoutePlan.objects.create(origin=origin, dest=dest, **defaults)
        else:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.save(update_fields=list(defaults.keys()))
        count += 1
    return count


# ─────────────────────────────────────────────── multi-stop optimizer


def optimize_multistop(
    *,
    locations: List[dict],
    vehicle_id: Optional[int] = None,
    soc_start_pct: float = 85.0,
    departure_hour: Optional[int] = None,
    return_to_depot: bool = True,
) -> dict:
    """Optimise a multi-stop route for an electric vehicle.

    Public entry point consumed by the ``/api/route/optimize`` endpoint.
    Stateless — no DB writes, all computation in memory.

    Args:
        locations: list of dicts with keys ``name``, and either ``lat``/``lng``
            or ``address`` (geocoded via Nominatim). One must have
            ``is_depot: true``.
        vehicle_id: optional ``Vehicle`` pk for battery/consumption data.
        soc_start_pct: starting battery percentage (0–100).
        departure_hour: 0–23 (Madrid local), for PVPC costing.
        return_to_depot: if True, the tour returns to the depot at the end.

    Returns:
        A dict ready for JSON serialisation with the optimised itinerary,
        battery curve, costs, and EV-vs-ICE comparison.
    """
    from apps.mubil.route.optimizer import (
        Location,
        MultiStopResult,
        StopResult,
        build_distance_matrix,
        geocode_address,
        get_route_polyline,
        simulate_battery,
        solve_tsp,
        _tour_distance,
        FAST_CHARGE_PRICE_EUR_KWH,
    )

    if len(locations) < 2:
        raise ValueError("Se necesitan al menos 2 ubicaciones (depot + 1 parada).")
    if len(locations) > 20:
        raise ValueError("Máximo 20 paradas por optimización.")

    # ── 1. Resolve locations (geocode if needed)
    locs: List[Location] = []
    for raw in locations:
        lat = raw.get("lat")
        lng = raw.get("lng")
        if lat is None or lng is None:
            address = raw.get("address", "")
            if not address:
                raise ValueError(f"Ubicación '{raw.get('name', '?')}' sin coordenadas ni dirección.")
            coords = geocode_address(address)
            if coords is None:
                raise ValueError(f"No se pudo geocodificar: '{address}'")
            lat, lng = coords
        locs.append(Location(
            name=raw.get("name", f"Parada {len(locs) + 1}"),
            lat=float(lat),
            lng=float(lng),
            is_depot=bool(raw.get("is_depot", False)),
            address=raw.get("address", ""),
        ))

    # Ensure exactly one depot
    depot_indices = [i for i, loc in enumerate(locs) if loc.is_depot]
    if not depot_indices:
        locs[0].is_depot = True
        depot_indices = [0]
    depot_idx = depot_indices[0]

    # ── 2. Vehicle data
    vehicle = None
    if vehicle_id is not None:
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            raise ValueError(f"Vehículo id={vehicle_id} no encontrado.")

    kwh_per_100 = float(_vehicle_kwh_per_100km(vehicle))
    battery_kwh = float(_vehicle_battery_kwh(vehicle) or Decimal("60"))

    # ── 3. Distance matrix
    dist_matrix, dur_matrix = build_distance_matrix(locs)

    # ── 4. Solve TSP
    tour = solve_tsp(dist_matrix, depot=depot_idx)

    # Measure improvement
    nn_order = list(range(len(locs)))
    nn_dist = _tour_distance(nn_order, dist_matrix)
    opt_dist = _tour_distance(tour, dist_matrix)
    opt_savings_pct = max(0.0, (1.0 - opt_dist / nn_dist) * 100) if nn_dist > 0 else 0.0

    # ── 5. Simulate battery
    legs, charge_stops = simulate_battery(
        tour=tour,
        dist_matrix=dist_matrix,
        dur_matrix=dur_matrix,
        kwh_per_100km=kwh_per_100,
        battery_kwh=battery_kwh,
        soc_start_pct=soc_start_pct,
    )

    # ── 6. Find real chargers for charge stops
    for cs in charge_stops:
        leg = legs[cs.after_leg_idx]
        from_loc = locs[leg.from_idx]
        to_loc = locs[leg.to_idx]
        # Find charger along this leg's corridor
        polyline_lonlat = [
            (from_loc.lng, from_loc.lat),
            (to_loc.lng, to_loc.lat),
        ]
        chargers = list(
            ChargingStation.objects
            .filter(power_kw__gte=50)
            .along_route(polyline_lonlat, radius_km=10)[:5]
        )
        if chargers:
            best = chargers[0]
            cs.charger_id = best.id
            cs.operator = best.operator or ""
            cs.address = best.address or ""
            cs.power_kw = float(best.power_kw) if best.power_kw else None
            cs.lat = best.geom.y
            cs.lng = best.geom.x

    # ── 7. Build ordered stops list
    ordered_stops: List[dict] = []
    total_dist = 0.0
    total_dur = 0.0
    total_energy = 0.0
    soc_curve: List[List[float]] = []  # [km_accum, soc_pct]

    km_accum = 0.0
    soc_curve.append([0.0, round(soc_start_pct, 1)])

    # First stop is the depot
    ordered_stops.append({
        "idx": 0,
        "name": locs[tour[0]].name,
        "lat": locs[tour[0]].lat,
        "lng": locs[tour[0]].lng,
        "arrival_soc": round(soc_start_pct, 1),
        "departure_soc": round(soc_start_pct, 1),
        "type": "depot",
        "distance_from_prev_km": 0,
        "duration_from_prev_min": 0,
    })

    charge_stop_map = {cs.after_leg_idx: cs for cs in charge_stops}

    for leg_idx, leg in enumerate(legs):
        total_dist += leg.distance_km
        total_dur += leg.duration_min
        total_energy += leg.energy_kwh
        km_accum += leg.distance_km

        # Is the destination the return to depot?
        is_last = leg_idx == len(legs) - 1
        dest_loc = locs[leg.to_idx]
        stop_type = "depot_return" if is_last else "delivery"

        # SOC at arrival
        arrival_soc = round(leg.soc_after, 1)
        departure_soc = arrival_soc

        soc_curve.append([round(km_accum, 1), arrival_soc])

        # Check if there's a charge stop after this leg
        if leg_idx in charge_stop_map:
            cs = charge_stop_map[leg_idx]
            departure_soc = round(cs.charge_to_soc, 1)
            total_dur += cs.duration_min

            # Insert charge stop before the delivery
            if cs.lat and cs.lng:
                ordered_stops.append({
                    "idx": len(ordered_stops),
                    "name": f"⚡ Carga rápida — {cs.operator or 'DC ≥50 kW'}",
                    "lat": cs.lat,
                    "lng": cs.lng,
                    "arrival_soc": arrival_soc,
                    "departure_soc": departure_soc,
                    "type": "charge",
                    "distance_from_prev_km": round(leg.distance_km, 1),
                    "duration_from_prev_min": round(leg.duration_min, 0),
                    "charger": {
                        "id": cs.charger_id,
                        "operator": cs.operator,
                        "power_kw": cs.power_kw,
                        "charge_kwh": round(cs.charge_kwh, 1),
                        "charge_min": cs.duration_min,
                    },
                })
                soc_curve.append([round(km_accum, 1), departure_soc])
                # The delivery itself comes next with zero distance
                ordered_stops.append({
                    "idx": len(ordered_stops),
                    "name": dest_loc.name,
                    "lat": dest_loc.lat,
                    "lng": dest_loc.lng,
                    "arrival_soc": departure_soc,
                    "departure_soc": departure_soc,
                    "type": stop_type,
                    "distance_from_prev_km": 0,
                    "duration_from_prev_min": 0,
                })
                continue

        ordered_stops.append({
            "idx": len(ordered_stops),
            "name": dest_loc.name,
            "lat": dest_loc.lat,
            "lng": dest_loc.lng,
            "arrival_soc": arrival_soc,
            "departure_soc": departure_soc,
            "type": stop_type,
            "distance_from_prev_km": round(leg.distance_km, 1),
            "duration_from_prev_min": round(leg.duration_min, 0),
        })

    # ── 7.5. Fetch polylines for the entire tour
    full_polyline = []
    for leg in legs:
        from_loc = locs[leg.from_idx]
        to_loc = locs[leg.to_idx]
        leg_poly = get_route_polyline(from_loc, to_loc)
        full_polyline.extend(leg_poly)

    # ── 8. Cost calculation
    price_home = float(_energy_price_eur_kwh_home())
    charge_energy = sum(cs.charge_kwh for cs in charge_stops)
    home_energy = max(total_energy - charge_energy, 0.0)
    ev_cost = home_energy * price_home + charge_energy * FAST_CHARGE_PRICE_EUR_KWH

    ice_baseline = _ice_trip_cost(Decimal(str(total_dist)))
    ice_cost = float(ice_baseline["cost_eur"])
    savings = ice_cost - ev_cost

    # CO2: ~2.31 kg/L diesel, ~0.2 kg/kWh grid mix
    co2_ice = float(ice_baseline["fuel_l"]) * 2.31
    co2_ev = total_energy * 0.2
    co2_saved = max(co2_ice - co2_ev, 0.0)

    # ── 9. Build response
    return {
        "total_distance_km": round(total_dist, 1),
        "total_duration_min": round(total_dur, 0),
        "total_energy_kwh": round(total_energy, 1),
        "ev_cost_eur": round(ev_cost, 2),
        "ice_cost_eur": round(ice_cost, 2),
        "savings_eur": round(savings, 2),
        "co2_saved_kg": round(co2_saved, 1),
        "needs_charge_stop": len(charge_stops) > 0,
        "ordered_stops": ordered_stops,
        "soc_curve": soc_curve,
        "tour_order": tour,
        "optimization_savings_pct": round(opt_savings_pct, 1),
        "vehicle_label": f"{vehicle.make} {vehicle.model}" if vehicle else None,
        "battery_kwh": battery_kwh,
        "soc_start": round(soc_start_pct, 1),
        "polyline": full_polyline,
    }




