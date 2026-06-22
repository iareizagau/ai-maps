"""Multi-stop route optimizer for electric vehicle fleets.

Solves the Travelling Salesman Problem (TSP) with battery constraints:
given a depot and N delivery locations, find the shortest tour that visits
every location exactly once, returns to the depot, and never lets the
vehicle's State of Charge (SOC) drop below a safety reserve.

Architecture
~~~~~~~~~~~~
1. **Distance matrix** — obtained from the OSRM Table API in a single HTTP
   call (sub-second for ≤20 waypoints). Fallback to haversine × 1.3 if
   the OSRM service is unreachable.
2. **TSP solver** — nearest-neighbor heuristic (O(n²)) improved by a 2-opt
   local search. No external dependencies (no OR-Tools). Produces tours
   within ~5% of the optimal for ≤20 nodes.
3. **Battery simulator** — walks the optimised tour leg by leg, tracking
   SOC. When projected SOC at the next stop drops below
   ``SOC_RESERVE_PCT``, it queries ``ChargingStation.objects.along_route``
   to find the nearest DC fast-charger and inserts a mandatory charge stop
   into the itinerary.
4. **Cost calculator** — prices the EV trip using PVPC rates for home
   charging and operator rates for en-route DC charging, then compares
   against a reference ICE (diesel/petrol) vehicle for the same distance.

All functions are pure Python (+ requests for OSRM). The module is
consumed by :func:`route.services.optimize_multistop`.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────── constants

OSRM_TABLE_URL = "http://router.project-osrm.org/table/v1/driving/{coords}"
OSRM_ROUTE_URL = "http://router.project-osrm.org/route/v1/driving/{coords}"
OSRM_TIMEOUT_S = 10
OSRM_USER_AGENT = "MubilOptimizer/1.0 (iareizagau@gmail.com)"

HAVERSINE_ROAD_FACTOR = 1.3  # straight-line → road distance approximation

# Battery thresholds (shared with route.services but defined here to avoid
# circular imports; values are kept in sync via tests).
SOC_RESERVE_PCT = 15.0          # never plan to arrive below this
SOC_CHARGE_TARGET_PCT = 80.0    # fast-charge up to this level
MIN_CHARGE_KWH = 5.0            # below this a stop is not worth it

# Fast-charger session profile
FAST_CHARGE_KW = 100.0          # representative DC kW
FAST_CHARGE_PRICE_EUR_KWH = 0.45

MAX_STOPS = 20   # hard cap on input locations


# ─────────────────────────────────────────────── data classes

@dataclass
class Location:
    """A waypoint in the optimisation problem."""
    name: str
    lat: float
    lng: float
    is_depot: bool = False
    address: str = ""


@dataclass
class LegResult:
    """One leg (A→B) in the final itinerary."""
    from_idx: int
    to_idx: int
    distance_km: float
    duration_min: float
    arrival_soc: float
    polyline: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class ChargeStopInfo:
    """A charge stop inserted by the battery simulator."""
    after_leg_idx: int          # inserted after this leg in the itinerary
    charger_id: Optional[int] = None
    operator: str = ""
    address: str = ""
    power_kw: Optional[float] = None
    lat: float = 0.0
    lng: float = 0.0
    charge_kwh: float = 0.0
    charge_to_soc: float = 0.0
    duration_min: int = 0


@dataclass
class StopResult:
    """One stop in the ordered itinerary (delivery or charge)."""
    idx: int
    name: str
    lat: float
    lng: float
    arrival_soc: float
    departure_soc: float
    stop_type: str              # 'depot' | 'delivery' | 'charge' | 'depot_return'
    distance_from_prev_km: float = 0.0
    duration_from_prev_min: float = 0.0
    charger: Optional[Dict] = None


@dataclass
class MultiStopResult:
    """Complete result of a multi-stop optimisation."""
    total_distance_km: float
    total_duration_min: float
    total_energy_kwh: float
    ev_cost_eur: float
    ice_cost_eur: float
    savings_eur: float
    co2_saved_kg: float
    needs_charge_stop: bool
    ordered_stops: List[StopResult]
    soc_curve: List[Tuple[float, float]]   # (km_accum, soc_pct)
    tour_order: List[int]                  # indices into the original locations
    optimization_distance_km: float        # distance before optimization (NN order)
    optimization_savings_pct: float        # % distance saved by 2-opt


# ─────────────────────────────────────────────── haversine

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two points."""
    r = 6371.0088
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


# ─────────────────────────────────────────────── distance matrix (OSRM)

def _osrm_table(locations: List[Location]) -> Optional[List[List[float]]]:
    """Fetch the full N×N distance matrix from OSRM Table API.

    Returns distances in **kilometres** (OSRM returns metres).
    Returns ``None`` on any failure (timeout, HTTP error, bad response).
    """
    coords = ";".join(f"{loc.lng},{loc.lat}" for loc in locations)
    url = OSRM_TABLE_URL.format(coords=coords) + "?annotations=distance,duration"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": OSRM_USER_AGENT})
        with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != "Ok":
            log.warning("OSRM Table API returned code=%s", data.get("code"))
            return None
        # Convert metres → km
        return [
            [d / 1000.0 for d in row]
            for row in data["distances"]
        ]
    except Exception as e:
        log.warning("OSRM Table API failed: %s", e)
        return None


def _osrm_durations(locations: List[Location]) -> Optional[List[List[float]]]:
    """Fetch the N×N duration matrix from OSRM (minutes)."""
    coords = ";".join(f"{loc.lng},{loc.lat}" for loc in locations)
    url = OSRM_TABLE_URL.format(coords=coords) + "?annotations=duration"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": OSRM_USER_AGENT})
        with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != "Ok":
            return None
        # Convert seconds → minutes
        return [
            [d / 60.0 for d in row]
            for row in data["durations"]
        ]
    except Exception:
        return None


def _haversine_matrix(locations: List[Location]) -> List[List[float]]:
    """Fallback: haversine × road factor. Always succeeds."""
    n = len(locations)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_km(locations[i].lat, locations[i].lng,
                              locations[j].lat, locations[j].lng) * HAVERSINE_ROAD_FACTOR
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def build_distance_matrix(
    locations: List[Location],
) -> Tuple[List[List[float]], List[List[float]]]:
    """Build (distance_km_matrix, duration_min_matrix).

    Tries OSRM first; falls back to haversine with estimated durations.
    """
    dist = _osrm_table(locations)
    dur = _osrm_durations(locations) if dist is not None else None

    if dist is None:
        log.info("Using haversine fallback for distance matrix (%d locations)", len(locations))
        dist = _haversine_matrix(locations)

    if dur is None:
        # Estimate: 60 km/h average
        dur = [[d / 60.0 * 60.0 for d in row] for row in dist]  # km / (km/h) * 60 = min
        # Simpler: dur[i][j] = dist[i][j] / 60 * 60 = dist[i][j] minutes at 60 km/h
        dur = [[d for d in row] for row in dist]  # 1 km ≈ 1 min at 60 km/h is close enough

    return dist, dur


# ─────────────────────────────────────────────── TSP solver

def _tour_distance(order: List[int], matrix: List[List[float]]) -> float:
    """Total distance of a closed tour (returns to start)."""
    total = 0.0
    for i in range(len(order) - 1):
        total += matrix[order[i]][order[i + 1]]
    total += matrix[order[-1]][order[0]]  # return to depot
    return total


def nearest_neighbor(matrix: List[List[float]], depot: int = 0) -> List[int]:
    """Greedy nearest-neighbor heuristic. O(n²).

    Starts at ``depot``, always visits the closest unvisited node.
    Returns the tour as a list of indices (starting and ending at depot).
    """
    n = len(matrix)
    visited = [False] * n
    tour = [depot]
    visited[depot] = True

    for _ in range(n - 1):
        current = tour[-1]
        best_next = -1
        best_dist = float("inf")
        for j in range(n):
            if not visited[j] and matrix[current][j] < best_dist:
                best_dist = matrix[current][j]
                best_next = j
        if best_next == -1:
            break
        tour.append(best_next)
        visited[best_next] = True

    return tour


def improve_2opt(order: List[int], matrix: List[List[float]], max_iterations: int = 100) -> List[int]:
    """2-opt local search improvement. Reverses sub-sequences to reduce total distance.

    Runs until no improving swap is found or ``max_iterations`` is reached.
    For 20 nodes, converges in <50ms.
    """
    best = list(order)
    best_dist = _tour_distance(best, matrix)
    n = len(best)

    improved = True
    iters = 0
    while improved and iters < max_iterations:
        improved = False
        iters += 1
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # Reverse the segment between i and j
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                d = _tour_distance(candidate, matrix)
                if d < best_dist - 1e-6:  # tolerance to avoid float noise
                    best = candidate
                    best_dist = d
                    improved = True
                    break
            if improved:
                break

    return best


def solve_tsp(matrix: List[List[float]], depot: int = 0) -> List[int]:
    """Solve TSP using nearest-neighbor + 2-opt improvement.

    Returns a tour (list of indices) starting at ``depot``.
    The tour does NOT include the return leg to depot (caller adds it).
    """
    if len(matrix) <= 2:
        return list(range(len(matrix)))

    tour = nearest_neighbor(matrix, depot)
    tour = improve_2opt(tour, matrix)

    # Rotate so depot is first
    if tour[0] != depot:
        idx = tour.index(depot)
        tour = tour[idx:] + tour[:idx]

    return tour


# ─────────────────────────────────────────────── battery simulation

@dataclass
class BatteryLeg:
    """Battery state for one leg of the tour."""
    from_idx: int
    to_idx: int
    distance_km: float
    duration_min: float
    energy_kwh: float
    soc_before: float       # SOC at departure from `from_idx`
    soc_after: float        # SOC at arrival to `to_idx`
    needs_charge: bool = False


def simulate_battery(
    tour: List[int],
    dist_matrix: List[List[float]],
    dur_matrix: List[List[float]],
    kwh_per_100km: float,
    battery_kwh: float,
    soc_start_pct: float,
) -> Tuple[List[BatteryLeg], List[ChargeStopInfo]]:
    """Walk the tour and simulate battery discharge.

    Returns:
        legs: list of BatteryLeg for each segment (including return to depot).
        charge_stops: list of ChargeStopInfo where a charge stop is needed.
    """
    legs: List[BatteryLeg] = []
    charge_stops: List[ChargeStopInfo] = []
    soc = soc_start_pct

    # Build legs: tour[0] → tour[1] → ... → tour[-1] → tour[0] (return)
    full_tour = tour + [tour[0]]  # close the loop

    for i in range(len(full_tour) - 1):
        from_idx = full_tour[i]
        to_idx = full_tour[i + 1]
        dist = dist_matrix[from_idx][to_idx]
        dur = dur_matrix[from_idx][to_idx]
        energy = dist * kwh_per_100km / 100.0
        soc_after = soc - (energy / battery_kwh * 100.0) if battery_kwh > 0 else soc

        needs_charge = soc_after < SOC_RESERVE_PCT

        leg = BatteryLeg(
            from_idx=from_idx,
            to_idx=to_idx,
            distance_km=dist,
            duration_min=dur,
            energy_kwh=energy,
            soc_before=soc,
            soc_after=max(soc_after, 0.0),
            needs_charge=needs_charge,
        )
        legs.append(leg)

        if needs_charge and battery_kwh > 0:
            # Calculate how much to charge to reach target SOC
            kwh_to_add = (SOC_CHARGE_TARGET_PCT - soc_after) / 100.0 * battery_kwh
            if kwh_to_add < MIN_CHARGE_KWH:
                kwh_to_add = MIN_CHARGE_KWH
            charge_duration = max(10, min(45, int(kwh_to_add / FAST_CHARGE_KW * 60)))
            new_soc = soc_after + (kwh_to_add / battery_kwh * 100.0)

            charge_stops.append(ChargeStopInfo(
                after_leg_idx=len(legs) - 1,
                charge_kwh=kwh_to_add,
                charge_to_soc=min(new_soc, 100.0),
                duration_min=charge_duration,
            ))
            # After charging, continue with the boosted SOC
            soc = min(new_soc, 100.0)
        else:
            soc = max(soc_after, 0.0)

    return legs, charge_stops


# ─────────────────────────────────────────────── geocoding

def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """Geocode a street address using Nominatim.

    Returns ``(lat, lng)`` or ``None`` on failure.
    """
    result = geocode_address_full(address)
    if result is None:
        return None
    return result[0], result[1]


def geocode_address_full(address: str) -> Optional[Tuple[float, float, str]]:
    """Geocode an address — returns ``(lat, lng, display_name)`` or ``None``.

    The display_name is Nominatim's pretty label, useful when the address
    came from a click instead of typing and the UI needs a human label.
    """
    params = urllib.parse.urlencode({
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "es",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": OSRM_USER_AGENT,
            "Accept-Language": "es",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data:
            return (
                float(data[0]["lat"]),
                float(data[0]["lon"]),
                str(data[0].get("display_name") or address),
            )
    except Exception as e:
        log.warning("Nominatim geocode failed for '%s': %s", address, e)
    return None


def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """Reverse-geocode coordinates via Nominatim, returning a display name.

    Used when the user pins a stop by clicking the map — without a label
    the optimised itinerary becomes unreadable ("Parada 3 → Parada 5").
    """
    params = urllib.parse.urlencode({
        "lat": f"{lat:.6f}",
        "lon": f"{lng:.6f}",
        "format": "json",
        "zoom": 16,
    })
    url = f"https://nominatim.openstreetmap.org/reverse?{params}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": OSRM_USER_AGENT,
            "Accept-Language": "es",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data.get("display_name") if isinstance(data, dict) else None
        if name:
            return str(name)
    except Exception as e:
        log.warning("Nominatim reverse failed for (%s, %s): %s", lat, lng, e)
    return None


# ─────────────────────────────────────────────── OSRM route polyline

def get_route_polyline(
    origin: Location, dest: Location,
) -> List[Tuple[float, float]]:
    """Get the road polyline between two points from OSRM.

    Returns a list of ``(lat, lng)`` coordinates, or a straight line
    on failure.
    """
    coords = f"{origin.lng},{origin.lat};{dest.lng},{dest.lat}"
    url = OSRM_ROUTE_URL.format(coords=coords) + "?overview=simplified&geometries=geojson"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": OSRM_USER_AGENT})
        with urllib.request.urlopen(req, timeout=OSRM_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == "Ok" and data.get("routes"):
            geom = data["routes"][0]["geometry"]
            # GeoJSON is [lng, lat] — flip to [lat, lng]
            return [(c[1], c[0]) for c in geom["coordinates"]]
    except Exception as e:
        log.debug("OSRM route polyline failed: %s", e)
    # Fallback: straight line
    return [(origin.lat, origin.lng), (dest.lat, dest.lng)]
