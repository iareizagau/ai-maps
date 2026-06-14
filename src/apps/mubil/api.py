"""Root Ninja router for mubil. Mounts 4 sub-routers per PROPUESTA.md §3 / §17:

  /estrata/api/v1/advisor/         — TCO eléctrico vs combustión (MUST)
  /estrata/api/v1/ask/             — RAG Gemini sobre datasets movilidad (MUST)
  /estrata/api/v1/route/           — EV-aware multimodal (MOCK)
  /estrata/api/v1/plan/            — heatmap demanda carga (MOCK)
  /estrata/api/v1/infrastructure/  — chargers + fast-charging desert (read-only)
"""

from typing import Optional

from ninja import Router

from .advisor.api import router as advisor_router
from .ask.api import router as ask_router
from .data import infrastructure as infrastructure_data
from .news.api import router as news_router
from .route.api import router as route_router
from .plan.api import router as plan_router


router = Router()
router.add_router('/advisor', advisor_router, tags=['advisor'])
router.add_router('/ask', ask_router, tags=['ask'])
router.add_router('/route', route_router, tags=['route'])
router.add_router('/plan', plan_router, tags=['plan'])
router.add_router('/news', news_router, tags=['news'])


@router.get('/health')
def health(request):
    return {'status': 'ok', 'module': 'mubil', 'version': '0.1.0'}


# ─────────────────────────────────────────────── infrastructure endpoints


@router.get('/infrastructure/chargers.geojson', tags=['infrastructure'])
def infrastructure_chargers(
    request,
    vehicle_id: Optional[int] = None,
    source: Optional[str] = None,
):
    """All EH chargers as GeoJSON, optionally coloured by compatibility.

    ``vehicle_id`` toggles the compatibility flag per feature based on a
    connector-type heuristic; a non-plug-in vehicle (or missing id) is
    silently treated as "no filter". ``source`` accepts a comma-separated
    list (``dgt_nap,ocm``) to limit which ingest sources show.
    """
    sources = [s.strip() for s in source.split(',')] if source else None
    return infrastructure_data.chargers_geojson(
        vehicle_id=vehicle_id, sources=sources,
    )


@router.get('/infrastructure/fuel_stations.geojson', tags=['infrastructure'])
def infrastructure_fuel_stations(request):
    """All EH fuel stations as GeoJSON with live fuel prices."""
    return infrastructure_data.fuel_stations_geojson()


@router.get('/infrastructure/desert.json', tags=['infrastructure'])
def infrastructure_desert(
    request,
    radius_km: float = infrastructure_data.DEFAULT_RADIUS_KM,
    step_deg: float = infrastructure_data.DEFAULT_STEP_DEG,
):
    """Coarse grid over EH with the fast-charger reachability score per cell.

    Drives the "fast-charging desert" overlay on the infrastructure map.
    Defaults to a 5 km grid / 25 km search radius — change at your own
    perf risk (cells = grid_area / step² and each cell hits PostGIS).
    """
    return {
        "cells": infrastructure_data.fast_charger_grid(
            radius_km=radius_km, step_deg=step_deg,
        ),
        "radius_km": radius_km,
        "step_deg": step_deg,
    }
