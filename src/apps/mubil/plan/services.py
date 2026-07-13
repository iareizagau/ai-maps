"""Demand-scoring services for the `plan` MOCK (PROPUESTA.md §3.4).

What this is, and what it is not:

- It IS a 2.5 km grid over Gipuzkoa (≈ 0.025°×0.030°), with each cell scored
  on a weighted blend of "expected EV demand" minus "existing supply" so the
  heatmap highlights underserved areas. Scores are stored in
  :class:`DemandHex` and recomputed offline by
  ``manage.py compute_demand_scores`` (cron monthly).
- It IS NOT real H3 — we don't depend on ``h3-py``. The model's
  ``h3_index`` field carries a square-cell slug (``sq{row}_{col}``) so the
  PK stays stable across runs and the migration path to true H3 is a
  drop-in: replace this generator with H3 ids and the rest of the pipeline
  (storage, API, choropleth) keeps working.
- It IS NOT calibrated on real demand. The three components are deterministic
  heuristics (population proxy from a Donostia/Bilbao Gaussian, corridor
  proxy from distance to the AP-8/AP-1 axes, supply from
  :class:`ChargingStation` density). They are good enough for "where would I
  put the next charger?" intuition; a real model is §6 follow-up.

Re-running ``compute_demand_scores`` is idempotent: each cell is keyed on its
slug and uses ``update_or_create``. Cells outside Gipuzkoa get pruned.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.contrib.gis.geos import Polygon
from django.db import transaction

from apps.mubil.models import ChargingStation, DemandHex

# ─────────────────────────────────────────────── grid definition


# Gipuzkoa-ish bounding box (slightly padded so border municipalities are not
# clipped — Eibar/Soraluze in the west, Hondarribia in the east).
GIPUZKOA_BBOX = {
    "min_lat": 42.95,
    "max_lat": 43.45,
    "min_lon": -2.55,
    "max_lon": -1.65,
}

# Step ≈ 2.5 km on both axes. 0.025° of latitude ≈ 2.78 km; at 43°N,
# 0.030° of longitude ≈ 2.44 km.
LAT_STEP = 0.025
LON_STEP = 0.030

# Reference centres for the population proxy. Donostia centre + Bilbao
# centre dominate Gipuzkoa demand because that's where commuting and EV
# uptake actually concentrate today.
POP_CENTRES: list[tuple[float, float, float]] = [
    (43.318, -1.985, 1.00),  # Donostia
    (43.263, -2.935, 0.55),  # Bilbao (just outside Gipuzkoa, still pulls demand)
    (43.184, -2.471, 0.30),  # Eibar
    (43.135, -2.078, 0.30),  # Tolosa
]

# Two corridors approximated as straight segments — distance from the cell
# centre to the segment proxies "trips per day on this axis". Real MITMA
# O-D would replace this.
CORRIDORS: list[tuple[tuple[float, float], tuple[float, float]]] = [
    ((43.318, -1.985), (43.263, -2.935)),  # AP-8 Donostia → Bilbao
    ((43.318, -1.985), (42.846, -2.673)),  # AP-1 Donostia → Vitoria
    ((43.318, -1.985), (42.815, -1.644)),  # AP-15 Donostia → Iruñea
]

# Charger-supply radius. The advisor card uses 5 km for "what's near me";
# 3 km here means a cell that already sits next to 2-3 chargers is treated
# as "supply present" — drops the score.
SUPPLY_RADIUS_KM = 3.0

# Growth factors applied to score_now to fake out years 3 and 5. The 30%/60%
# bumps are loose: EV registrations are roughly doubling every 3 years in EH,
# but the score is bounded so the heatmap stays interpretable.
GROWTH_Y3 = Decimal("1.30")
GROWTH_Y5 = Decimal("1.60")


# ─────────────────────────────────────────────── geometry helpers


def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Great-circle distance, km. Sufficient for the heatmap (~m error)."""
    lat1, lon1 = map(math.radians, p1)
    lat2, lon2 = map(math.radians, p2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(a))


def _point_segment_distance_km(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Perpendicular distance from ``p`` to segment ``ab`` (km, flat-earth)."""
    # Project to a local equirectangular approximation around the segment.
    # Good enough at EH scale; full geodesics would be overkill.
    mid_lat = (a[0] + b[0]) / 2
    cos_mid = math.cos(math.radians(mid_lat))

    def to_xy(pt):
        return (pt[1] * cos_mid * 111.32, pt[0] * 110.57)  # km

    px, py = to_xy(p)
    ax, ay = to_xy(a)
    bx, by = to_xy(b)
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len2))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


@dataclass(frozen=True)
class GridCell:
    slug: str  # ≤ 15 chars (PK constraint on DemandHex.h3_index)
    row: int
    col: int
    centre: tuple[float, float]  # (lat, lon)
    bounds: tuple[float, float, float, float]  # (min_lat, min_lon, max_lat, max_lon)


def iter_grid(bbox: dict = GIPUZKOA_BBOX) -> Iterable[GridCell]:
    """Walk the grid row-by-row. Slugs are deterministic by (row, col).

    Iterating on integer indices (not an incrementing float) prevents the
    classic ``while lat < max_lat`` overshoot — with step=0.025 over a
    0.50° range the floating-point accumulator can land on
    ``43.450000…0001`` and emit an extra row.
    """
    min_lat, min_lon = bbox["min_lat"], bbox["min_lon"]
    max_lat, max_lon = bbox["max_lat"], bbox["max_lon"]
    n_rows = int(round((max_lat - min_lat) / LAT_STEP))
    n_cols = int(round((max_lon - min_lon) / LON_STEP))
    for row in range(n_rows):
        lat = min_lat + row * LAT_STEP
        for col in range(n_cols):
            lon = min_lon + col * LON_STEP
            slug = f"sq{row:03d}_{col:03d}"  # 9 chars — fits max_length=15
            yield GridCell(
                slug=slug,
                row=row,
                col=col,
                centre=(lat + LAT_STEP / 2, lon + LON_STEP / 2),
                bounds=(lat, lon, lat + LAT_STEP, lon + LON_STEP),
            )


def cell_polygon(cell: GridCell) -> Polygon:
    """GEOS polygon for one cell (SRID 4326)."""
    min_lat, min_lon, max_lat, max_lon = cell.bounds
    ring = (
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat),
    )
    return Polygon(ring, srid=4326)


# ─────────────────────────────────────────────── scoring components


def _population_component(centre: tuple[float, float]) -> float:
    """0..1 score, Gaussian-summed contribution from each population centre."""
    total = 0.0
    for lat, lon, weight in POP_CENTRES:
        d_km = _haversine_km(centre, (lat, lon))
        # σ = 8 km → cells within ~10 km of a centre get most of the weight.
        total += weight * math.exp(-(d_km**2) / (2 * 8.0**2))
    return min(total, 1.0)


def _corridor_component(centre: tuple[float, float]) -> float:
    """0..1 score from proximity to commuter corridors (O-D proxy)."""
    best = float("inf")
    for a, b in CORRIDORS:
        d = _point_segment_distance_km(centre, a, b)
        if d < best:
            best = d
    # σ = 5 km → cells within ~6 km of an axis get >0.5; >15 km decays to ~0.
    return math.exp(-(best**2) / (2 * 5.0**2))


def _supply_component(centre: tuple[float, float]) -> int:
    """Count of existing chargers within :data:`SUPPLY_RADIUS_KM` of the centre."""
    # Cheap version: ChargingStation.objects.nearby() (uses GIST). The MOCK
    # values are small enough (~600 chargers EH-wide) that this is sub-ms.
    return ChargingStation.objects.nearby(
        longitude=centre[1],
        latitude=centre[0],
        radius_km=SUPPLY_RADIUS_KM,
    ).count()


def score_cell(centre: tuple[float, float]) -> dict:
    """Composite score + per-component breakdown for one cell.

    Weights mirror PROPUESTA.md §3.4 (pop 0.4 + od 0.4 − supply 0.2), with
    the supply component normalised — counts of ~10+ saturate to 1.
    """
    pop = _population_component(centre)
    od = _corridor_component(centre)
    chargers_n = _supply_component(centre)
    supply_norm = min(chargers_n / 10.0, 1.0)
    score_now = (pop * 0.4) + (od * 0.4) - (supply_norm * 0.2)
    # Clamp to [0, 1] for a clean choropleth domain.
    score_now = max(0.0, min(1.0, score_now))
    return {
        "score_now": score_now,
        "components": {
            "pop": round(pop, 3),
            "od": round(od, 3),
            "chargers_nearby": chargers_n,
            "supply_norm": round(supply_norm, 3),
        },
    }


# ─────────────────────────────────────────────── ingest / API helpers


@dataclass
class DemandComputeStats:
    cells_scored: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute_demand_scores(
    *,
    bbox: dict = GIPUZKOA_BBOX,
    prune_outside_bbox: bool = True,
    dry_run: bool = False,
) -> DemandComputeStats:
    """Score every cell in ``bbox`` and persist into :class:`DemandHex`.

    Args:
        bbox: bounding box dict. Defaults to Gipuzkoa.
        prune_outside_bbox: delete previously stored cells whose slug is
            not produced by the current grid. Useful when the bbox shrinks.
        dry_run: compute + log, no DB writes.

    Returns:
        :class:`DemandComputeStats` with per-step counters.
    """
    stats = DemandComputeStats()
    fresh_slugs: list[str] = []

    for cell in iter_grid(bbox):
        scored = score_cell(cell.centre)
        stats.cells_scored += 1
        fresh_slugs.append(cell.slug)
        if dry_run:
            continue

        score_now = Decimal(str(round(scored["score_now"], 3)))
        defaults = {
            "geom": cell_polygon(cell),
            "municipality_naia": "",  # NAIA enrichment is §6 follow-up
            "score_now": score_now,
            "score_y3": (score_now * GROWTH_Y3).quantize(Decimal("0.001")),
            "score_y5": (score_now * GROWTH_Y5).quantize(Decimal("0.001")),
            "components": scored["components"],
        }
        with transaction.atomic():
            _obj, created = DemandHex.objects.update_or_create(
                h3_index=cell.slug,
                defaults=defaults,
            )
        if created:
            stats.created += 1
        else:
            stats.updated += 1

    if not dry_run and prune_outside_bbox:
        deleted, _ = DemandHex.objects.exclude(h3_index__in=fresh_slugs).delete()
        stats.deleted = deleted

    return stats


# ─────────────────────────────────────────────── read API


def heatmap_geojson(
    *,
    horizon: int = 3,
    min_score: float = 0.0,
    limit: int | None = None,
) -> dict:
    """Build a GeoJSON FeatureCollection of stored cells.

    Args:
        horizon: 1 → ``score_now``; 3 → ``score_y3``; 5 → ``score_y5``.
        min_score: drop cells below this threshold (UI filter).
        limit: cap returned features. Useful when the grid grows.
    """
    field = {1: "score_now", 3: "score_y3", 5: "score_y5"}.get(horizon, "score_now")
    qs = DemandHex.objects.filter(**{f"{field}__gte": min_score}).order_by(f"-{field}")
    if limit is not None:
        qs = qs[:limit]

    features = []
    for hex_row in qs:
        coords = list(hex_row.geom.coords[0])  # outer ring
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "h3_index": hex_row.h3_index,
                    "score": float(getattr(hex_row, field)),
                    "score_now": float(hex_row.score_now),
                    "score_y3": float(hex_row.score_y3),
                    "score_y5": float(hex_row.score_y5),
                    "components": hex_row.components,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def top_locations(*, horizon: int = 3, limit: int = 10) -> list[dict]:
    """Ranked list of best cells. Used by the dashboard sidebar."""
    field = {1: "score_now", 3: "score_y3", 5: "score_y5"}.get(horizon, "score_now")
    out = []
    for hex_row in DemandHex.objects.order_by(f"-{field}")[:limit]:
        centre = hex_row.geom.centroid
        out.append(
            {
                "h3_index": hex_row.h3_index,
                "score": float(getattr(hex_row, field)),
                "centroid_lat": centre.y,
                "centroid_lon": centre.x,
                "components": hex_row.components,
                "municipality_naia": hex_row.municipality_naia,
            }
        )
    return out
