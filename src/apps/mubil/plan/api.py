"""`plan` sub-router — demand heatmap for charger siting (MOCK).

Endpoints (PROPUESTA.md §3.4):
    GET  /health
    GET  /heatmap?horizon=1|3|5&min_score=0..1&limit=N
                                          → GeoJSON FeatureCollection
    GET  /top-locations?horizon=&limit=   → ranked best-N cells

Scores are precomputed by ``manage.py compute_demand_scores`` (cron monthly)
— this router only reads from :class:`DemandHex`. No live heuristics here.
"""

from __future__ import annotations

from ninja import Router

from apps.mubil.models import DemandHex
from apps.mubil.plan import services

router = Router()


@router.get("/health")
def health(request):
    return {
        "status": "ok",
        "module": "plan",
        "hexes": DemandHex.objects.count(),
    }


@router.get("/heatmap")
def heatmap(
    request,
    horizon: int = 3,
    min_score: float = 0.0,
    limit: int | None = None,
):
    """GeoJSON FeatureCollection of demand cells.

    ``horizon`` picks which precomputed column to expose as ``properties.score``
    (1 → ``score_now``, 3 → ``score_y3``, 5 → ``score_y5``).
    """
    return services.heatmap_geojson(horizon=horizon, min_score=min_score, limit=limit)


@router.get("/top-locations")
def top_locations(request, horizon: int = 3, limit: int = 10) -> list[dict]:
    """Best ``limit`` cells by score at the chosen horizon."""
    return services.top_locations(horizon=horizon, limit=limit)
