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
from decimal import Decimal
from typing import List, Optional, Tuple

from apps.mubil.data import pvpc_ingest
from apps.mubil.models import EVRoutePlan, Vehicle


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

    return RoutePlanResult(
        slug=demo["slug"],
        label=demo["label"],
        origin_name=demo["origin_name"],
        dest_name=demo["dest_name"],
        via=demo["via"],
        origin=demo["origin"],
        dest=demo["dest"],
        polyline=demo["polyline"],
        distance_km=distance_km,
        duration_min=total_duration_min,
        energy_kwh=energy_kwh,
        estimated_cost_eur=estimated_cost_eur,
        soc_start_pct=soc_start_pct,
        soc_end_pct=soc_end_pct,
        segments=segments,
        vehicle_id=vehicle.id if vehicle else None,
        vehicle_label=f"{vehicle.make} {vehicle.model}" if vehicle else None,
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


def plan(
    *,
    slug: str,
    vehicle_id: Optional[int] = None,
    soc_start_pct: float = 80.0,
) -> RoutePlanResult:
    """Build a :class:`RoutePlanResult` for one demo slug.

    Args:
        slug: one of :data:`ROUTE_DEMOS` slugs.
        vehicle_id: optional :class:`Vehicle` pk. If ``None`` the plan uses
            :data:`DEFAULT_KWH_PER_100KM` and skips SOC math (no stops).
        soc_start_pct: starting battery percentage, 0-100. Defaults to 80%
            — a realistic "drove from home" condition.
    """
    demo = get_demo(slug)
    if demo is None:
        raise ValueError(f"Unknown route slug: {slug}")
    if not (0 <= soc_start_pct <= 100):
        raise ValueError(f"soc_start_pct out of range (0-100): {soc_start_pct}")

    vehicle = None
    if vehicle_id is not None:
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            raise ValueError(f"Vehicle id={vehicle_id} not found")

    return _plan_for_demo(demo, vehicle, Decimal(str(soc_start_pct)))


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
