"""Infrastructure layer for the ``/mubil/infrastructure/`` map view.

Two responsibilities, both read-only:

1. :func:`chargers_geojson` — flatten ``ChargingStation`` rows into a GeoJSON
   FeatureCollection ready for Leaflet. When a ``vehicle_id`` is supplied,
   every feature gets a ``compatible`` flag computed from a connector-type
   heuristic (no per-vehicle connector field exists in :class:`Vehicle`).

2. :func:`fast_charger_grid` — a coarse square grid over Euskal Herria where
   each cell carries a count of fast (≥50 kW) chargers within ``radius_km``
   of its centroid. Drives the "fast-charging desert" choropleth layer; the
   point is to show *driveable* coverage, not just dot density.

Performance: the grid does ``cell_count`` PostGIS ``ST_DWithin`` queries.
With the default 5 km step over the EH bbox that's ~280 cells, each <5 ms
on a GIST-indexed table — overall <1.5 s. Wrap the API view with a short
cache_page if the page gets hot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from django.db import models
from django.db.models import Func
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.geos import Point, Polygon

from apps.mubil.models import ChargingStation, Vehicle, FuelStation


def _eh_polygon() -> Polygon:
    """EH bbox polygon — same one the OCM ingest uses. Built lazily so we
    don't pay GEOS init cost when callers only need the dot-grid helpers."""
    from apps.mubil.data.openchargemap_client import EH_BBOX_NE, EH_BBOX_SW
    sw_lat, sw_lon = EH_BBOX_SW
    ne_lat, ne_lon = EH_BBOX_NE
    poly = Polygon.from_bbox((sw_lon, sw_lat, ne_lon, ne_lat))
    poly.srid = 4326
    return poly


class ST_X(Func):
    function = 'ST_X'
    output_field = models.FloatField()


class ST_Y(Func):
    function = 'ST_Y'
    output_field = models.FloatField()


# ─────────────────────────────────────────────── connector compatibility


# DATEX II / OCM connector strings considered compatible with a modern EU BEV.
# Defensible default (no per-vehicle connector data exists in the catalog):
# every post-2017 BEV sold in EH ships Type 2 AC + CCS2 DC. Older Nissan/
# Mitsubishi BEVs use CHAdeMO — we keep it in the set so the few legacy
# vehicles in the catalog are not silently shown as "no compatible station".
# Values are normalised to lowercase before comparison.
_COMPATIBLE_CONNECTORS = frozenset({
    "iec62196t2",        # Type 2 AC (mennekes)
    "iec62196t2combo",   # CCS Combo 2 (DC fast)
    "ccs",               # OCM legacy label, same as above
    "type2",             # OCM legacy label
    "chademo",           # Legacy DC (Nissan Leaf 1/2, Mitsubishi i-MiEV)
})

# Power tier thresholds (kW). Drives the marker color in the Leaflet layer.
# The thresholds map to the realistic user experience: slow = overnight only,
# medium = top-up while shopping, fast = highway recharging.
POWER_TIER_SLOW = 22.0       # AC single-phase or 3-phase 11 kW typical
POWER_TIER_FAST = 50.0       # DC fast, useful for highway stops

# Euskal Herria bounding box (lat/lon corners). Same one as the OCM client.
EH_BBOX_SW = (42.30, -3.45)
EH_BBOX_NE = (43.55, -1.30)


def _power_tier(power_kw: Optional[float]) -> str:
    """Bucket a kW value into ``slow`` / ``medium`` / ``fast`` / ``unknown``."""
    if power_kw is None:
        return "unknown"
    if power_kw >= POWER_TIER_FAST:
        return "fast"
    if power_kw >= POWER_TIER_SLOW:
        return "medium"
    return "slow"


def _connector_is_compatible(connectors: Iterable[dict]) -> bool:
    """True if any connector type matches the EU BEV-compatible set."""
    if not connectors:
        return False
    for c in connectors:
        if not isinstance(c, dict):
            continue
        ctype = (c.get("type") or "").strip().lower()
        if ctype in _COMPATIBLE_CONNECTORS:
            return True
    return False


def _vehicle_takes_ev_charge(vehicle: Vehicle) -> bool:
    """Only BEV and PHEV plug into public chargers."""
    return vehicle.propulsion in (
        Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV,
    )


# ─────────────────────────────────────────────── chargers GeoJSON


@dataclass(frozen=True)
class ChargerStyle:
    """Per-feature presentation hints baked into the GeoJSON properties.

    Kept on the server so the template doesn't have to re-encode the
    business rules in JS. ``color`` mirrors the legend the UI shows.
    """
    tier: str          # slow | medium | fast | unknown
    compatible: bool   # True if compatible with the session vehicle (or no vehicle)
    color: str         # CSS color literal, e.g. "#16a34a"


# Tailwind-aligned palette. Matches the legend rendered in the template so
# changing colors in one place is enough.
_TIER_COLORS = {
    "fast":    "#2563eb",   # blue-600 — DC fast
    "medium":  "#16a34a",   # green-600 — useful daily
    "slow":    "#ca8a04",   # yellow-600 — overnight only
    "unknown": "#6b7280",   # gray-500 — no power data
}
_INCOMPATIBLE_COLOR = "#9ca3af"  # gray-400, regardless of power


def _style_for(power_tier: str, compatible: bool) -> ChargerStyle:
    if not compatible:
        return ChargerStyle(tier=power_tier, compatible=False, color=_INCOMPATIBLE_COLOR)
    return ChargerStyle(
        tier=power_tier,
        compatible=True,
        color=_TIER_COLORS.get(power_tier, _TIER_COLORS["unknown"]),
    )


def chargers_geojson(
    *,
    vehicle_id: Optional[int] = None,
    sources: Optional[Iterable[str]] = None,
    scope: str = 'eh',
) -> dict:
    """Return all charging stations as a GeoJSON FeatureCollection.

    Args:
        vehicle_id: optional :class:`Vehicle` PK from the advisor session.
            When provided AND the vehicle is BEV/PHEV, each feature carries
            a ``compatible`` flag based on its connector list. When absent
            (or vehicle isn't a plug-in), every feature is treated as
            compatible — the layer degrades to a plain power-tiered map.
        sources: restrict to a subset of source slugs (e.g. ``["dgt_nap"]``).

    Properties on each feature:
        id, source, operator, address, power_kw, tier, color, compatible,
        connectors (list), last_seen_at (ISO or null).
    """
    vehicle = None
    if vehicle_id is not None:
        vehicle = Vehicle.objects.filter(pk=vehicle_id).only(
            "id", "propulsion", "make", "model",
        ).first()

    # Only honour the vehicle filter when it actually plugs in. A diesel in
    # the session shouldn't grey out the entire infrastructure layer.
    apply_compat = vehicle is not None and _vehicle_takes_ev_charge(vehicle)

    qs = ChargingStation.objects.exclude(geom__isnull=True)
    if scope == 'eh':
        # Spatial filter; uses the same GIST-indexed bbox the ingest writes to.
        qs = qs.filter(geom__within=_eh_polygon())
    if sources:
        qs = qs.filter(source__in=list(sources))
    qs = qs.annotate(
        x=ST_X("geom"),
        y=ST_Y("geom"),
    ).values(
        "id", "source", "operator", "address",
        "power_kw", "connectors", "last_seen_at",
        "x", "y"
    )

    features: List[dict] = []
    for s in qs:
        power_kw = float(s["power_kw"]) if s["power_kw"] is not None else None
        tier = _power_tier(power_kw)
        compatible = (
            _connector_is_compatible(s["connectors"]) if apply_compat else True
        )
        style = _style_for(tier, compatible)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["x"], s["y"]],
            },
            "properties": {
                "id": s["id"],
                "source": s["source"],
                "operator": s["operator"],
                "address": s["address"],
                "power_kw": power_kw,
                "tier": style.tier,
                "color": style.color,
                "compatible": style.compatible,
                "connectors": s["connectors"] or [],
                "last_seen_at": s["last_seen_at"].isoformat() if s["last_seen_at"] else None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "count": len(features),
            "vehicle_id": vehicle.id if vehicle else None,
            "vehicle_label": (
                f"{vehicle.make} {vehicle.model}" if vehicle else None
            ),
            "compatibility_applied": apply_compat,
        },
    }


# ─────────────────────────────────────────────── fast-charger grid


# Steps of ~0.045° lat ≈ 5 km, ~0.062° lon ≈ 5 km at 43°N. Coarse enough
# to render quickly, fine enough to draw clear "deserts" between Bilbao,
# Donostia, Vitoria and Pamplona.
DEFAULT_STEP_DEG = 0.05
DEFAULT_RADIUS_KM = 25


def fast_charger_grid(
    *,
    radius_km: float = DEFAULT_RADIUS_KM,
    step_deg: float = DEFAULT_STEP_DEG,
    sw: tuple = EH_BBOX_SW,
    ne: tuple = EH_BBOX_NE,
) -> List[dict]:
    """Build a square-grid coverage layer over EH.

    For each cell centroid, count fast (≥50 kW) chargers within ``radius_km``.
    The driving question is "could I reach a fast charger from here in 25 km
    on real roads?" — not just dot density. Cells with zero fast chargers
    are the "deserts" we want to flag.

    Args:
        radius_km: search radius around each centroid.
        step_deg: grid spacing in degrees; 0.05 ≈ 5 km, ~280 cells over EH.
        sw, ne: bounding-box corners (lat, lon).

    Returns:
        List of dicts ``{lat, lon, fast_count, score}`` where ``score`` is in
        ``[0, 1]`` (1 = best coverage, 0 = no fast chargers in range). The
        score saturates at 5 fast chargers to keep urban hot-spots from
        flattening the rural gradient.
    """
    sw_lat, sw_lon = sw
    ne_lat, ne_lon = ne

    # Pre-compute lat / lon ranges. Float drift is fine — we want roughly
    # uniform cells, not metric precision.
    lats: List[float] = []
    lat = sw_lat
    while lat <= ne_lat + 1e-9:
        lats.append(round(lat, 4))
        lat += step_deg
    lons: List[float] = []
    lon = sw_lon
    while lon <= ne_lon + 1e-9:
        lons.append(round(lon, 4))
        lon += step_deg

    # Pre-build the queryset filter once; ``.fast()`` is the custom manager.
    fast_qs = ChargingStation.objects.fast()
    saturation = 5

    # PostGIS requires a *numeric degrees* radius for ST_DWithin on
    # geographic (SRID 4326) geometry columns — passing ``D(km=…)`` raises
    # "Only numeric values of degree units are allowed". 1° ≈ 111 km at the
    # equator; at EH latitudes (~43°N) 1° lon ≈ 81 km so the search is
    # slightly wider E-W, which is fine for a coverage indicator. Same trick
    # as :meth:`ChargingStationQuerySet.along_route`.
    radius_deg = float(radius_km) / 111.0

    cells: List[dict] = []
    for lat in lats:
        for lon in lons:
            centroid = Point(lon, lat, srid=4326)
            fast_count = fast_qs.filter(
                geom__dwithin=(centroid, radius_deg)
            ).count()
            # Score saturates at `saturation` so 1 charger ≠ same as 20.
            score = min(fast_count, saturation) / saturation
            cells.append({
                "lat": lat,
                "lon": lon,
                "fast_count": fast_count,
                "score": round(score, 3),
            })

    return cells


def fuel_stations_geojson(*, scope: str = 'eh') -> dict:
    """Return fuel stations as a GeoJSON FeatureCollection.

    ``scope='eh'`` (default) restricts to the Euskal Herria bbox so the Mapa
    page stays coherent with the product premise. ``scope='spain'`` returns
    the full national snapshot — useful for the explicit "ampliar a España"
    toggle but ~18× bigger payload.

    Optimized using ST_X/ST_Y database functions and .values() lookup to bypass
    full Django model instantiation and WKB parsing.
    """
    qs = FuelStation.objects.exclude(geom__isnull=True)
    if scope == 'eh':
        qs = qs.filter(geom__within=_eh_polygon())
    qs = qs.annotate(
        x=ST_X("geom"),
        y=ST_Y("geom"),
    ).values(
        "id", "brand", "address", "municipality_name",
        "prices", "schedule", "sale_type", "last_seen_at",
        "x", "y"
    )

    features = []
    for s in qs:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["x"], s["y"]],
            },
            "properties": {
                "id": s["id"],
                "brand": s["brand"],
                "address": s["address"],
                "municipality_name": s["municipality_name"],
                "prices": s["prices"] or {},
                "schedule": s["schedule"],
                "sale_type": s["sale_type"],
                "last_seen_at": s["last_seen_at"].isoformat() if s["last_seen_at"] else None,
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
