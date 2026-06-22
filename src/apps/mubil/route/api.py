"""`route` sub-router — EV-aware multimodal (MOCK demo).

Endpoints (PROPUESTA.md §3.3):
    GET  /health
    GET  /demos                 → list of 5 precomputed O-D pairs
    GET  /demos/{slug}          → full plan for one demo (default vehicle)
    POST /plan                  → plan one demo with a chosen vehicle + SOC

The real implementation (pgRouting + dynamic SOC + GTFS multimodal) is §6
follow-up; here we serve the cached 5-route grid that backs the demo card.
"""

from __future__ import annotations

from typing import List, Optional

from ninja import Router

from apps.mubil.route import services
from apps.mubil.route.schemas import EVPlanIn, EVPlanOut, RouteSegment

router = Router()


@router.get('/health')
def health(request):
    return {'status': 'ok', 'module': 'route', 'demos': len(services.ROUTE_DEMOS)}


@router.get('/demos')
def demos(request) -> List[dict]:
    """Lightweight metadata for the 5 precomputed routes."""
    return services.list_demos()


@router.get('/demos/{slug}')
def demo_detail(request, slug: str):
    """Full :class:`RoutePlanResult` for one demo slug.

    No vehicle — uses the generic 18 kWh/100km default. Useful for the
    landing card before the user has picked a Vehicle.
    """
    try:
        result = services.plan(slug=slug)
    except ValueError as e:
        return router.api.create_response(request, {"detail": str(e)}, status=404)
    return result.to_dict()


@router.post('/plan', response=EVPlanOut)
def plan(request, payload: EVPlanIn):
    """Plan one demo with a specific vehicle + SOC.

    The schema uses lat/lon for forward compatibility with the real planner;
    in MOCK mode we snap the request to whichever demo has the closest
    origin-destination pair so the visual stays consistent.
    """
    demo = _nearest_demo(payload.origin_lat, payload.origin_lon,
                         payload.dest_lat, payload.dest_lon)
    result = services.plan(
        slug=demo["slug"],
        vehicle_id=payload.vehicle_id,
        soc_start_pct=payload.soc_start,
    )
    polyline = [[lat, lon] for lat, lon in result.polyline]
    segments = [
        RouteSegment(
            kind=s.kind,
            distance_km=float(s.distance_km) if s.distance_km is not None else None,
            duration_min=s.duration_min,
            meta=s.meta,
        )
        for s in result.segments
    ]
    return EVPlanOut(
        polyline=polyline,
        segments=segments,
        distance_km=float(result.distance_km),
        duration_min=result.duration_min,
        energy_kwh=float(result.energy_kwh),
        estimated_cost_eur=float(result.estimated_cost_eur),
    )


def _nearest_demo(o_lat: float, o_lon: float, d_lat: float, d_lon: float) -> dict:
    """Snap an arbitrary O-D to the closest precomputed demo (sum-of-haversine).

    Strictly visual: as long as the user picks a pair within Euskal Herria
    they get a plausible cached route. Real routing is §6.
    """
    best: Optional[dict] = None
    best_score = float("inf")
    for d in services.ROUTE_DEMOS:
        score = (
            abs(d["origin"][0] - o_lat) + abs(d["origin"][1] - o_lon)
            + abs(d["dest"][0] - d_lat) + abs(d["dest"][1] - d_lon)
        )
        if score < best_score:
            best = d
            best_score = score
    assert best is not None
    return best


# ─────────────────────────────────────────────── geocoding helpers
#
# Two thin wrappers around Nominatim, cached for 24 h so a user building
# a 10-stop list as they type doesn't blast the public server. We also
# guard ourselves against the response shape changing — the optimizer
# layer already handles errors gracefully, here we just translate to HTTP.


from django.core.cache import cache

from apps.mubil.route.optimizer import geocode_address_full, reverse_geocode

_GEOCODE_TTL_S = 60 * 60 * 24


@router.get('/geocode')
def geocode(request, q: str):
    """Forward geocode — returns ``{lat, lng, display_name}`` or 404.

    Used by the multi-stop UI to drop a marker on the map as soon as the
    user adds a stop, so they can verify the geocoder's pick before
    paying for the OSRM optimisation round-trip.
    """
    q = (q or '').strip()
    if not q:
        return router.api.create_response(
            request, {"detail": "Falta el parámetro q."}, status=400,
        )
    key = f'mubil:geocode:{q.lower()}'
    cached = cache.get(key)
    if cached is not None:
        return cached if cached else router.api.create_response(
            request, {"detail": "No encontrado."}, status=404,
        )
    found = geocode_address_full(q)
    if found is None:
        cache.set(key, {}, _GEOCODE_TTL_S)  # negative cache — short-circuit retries
        return router.api.create_response(
            request, {"detail": "No encontrado."}, status=404,
        )
    payload = {"lat": found[0], "lng": found[1], "display_name": found[2]}
    cache.set(key, payload, _GEOCODE_TTL_S)
    return payload


@router.get('/geocode/reverse')
def geocode_reverse(request, lat: float, lng: float):
    """Reverse geocode — returns ``{display_name}`` for a clicked point.

    Coordinates are bucketed to ~10 m before caching so identical clicks
    on the same building hit the cache.
    """
    bucket_lat = round(lat, 4)
    bucket_lng = round(lng, 4)
    key = f'mubil:rgeocode:{bucket_lat}:{bucket_lng}'
    cached = cache.get(key)
    if cached is not None:
        return cached if cached else router.api.create_response(
            request, {"detail": "No encontrado."}, status=404,
        )
    name = reverse_geocode(lat, lng)
    if name is None:
        cache.set(key, {}, _GEOCODE_TTL_S)
        return router.api.create_response(
            request, {"detail": "No encontrado."}, status=404,
        )
    payload = {"display_name": name}
    cache.set(key, payload, _GEOCODE_TTL_S)
    return payload


# ─────────────────────────────────────────────── multi-stop optimizer


from ninja import Schema


class OptimizeLocationIn(Schema):
    name: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: str = ""
    is_depot: bool = False


class OptimizeIn(Schema):
    locations: List[OptimizeLocationIn]
    vehicle_id: Optional[int] = None
    soc_start: float = 85.0
    departure_hour: Optional[int] = None
    return_to_depot: bool = True


@router.post('/optimize')
def optimize(request, payload: OptimizeIn):
    """Optimise a multi-stop route for an electric vehicle.

    Accepts 2–20 locations (one marked ``is_depot``). Each location can
    provide ``lat``/``lng`` directly or an ``address`` string that will be
    geocoded via Nominatim.

    Returns the optimised tour order, battery simulation with charge-stop
    insertions, and an EV-vs-ICE cost comparison.
    """
    try:
        result = services.optimize_multistop(
            locations=[loc.dict() for loc in payload.locations],
            vehicle_id=payload.vehicle_id,
            soc_start_pct=payload.soc_start,
            departure_hour=payload.departure_hour,
            return_to_depot=payload.return_to_depot,
        )
        return result
    except ValueError as e:
        return router.api.create_response(
            request, {"detail": str(e)}, status=422,
        )
    except Exception as e:
        return router.api.create_response(
            request, {"detail": f"Error interno: {e}"}, status=500,
        )

