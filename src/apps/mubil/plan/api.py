"""`plan` sub-router — heatmap demanda infraestructura carga (MOCK).

Endpoints (PROPUESTA.md §3.4):
  GET /heatmap?municipality=&horizon=  → GeoJSON FeatureCollection (DemandHex)
  GET /top-locations?municipality=&limit=  → ranking top-N

Score heurístico precomputado: registrationsEV×0.4 + od_density×0.4 − current_chargers×0.2.
Sin modelo ML — extensión post-premio.
"""

from ninja import Router

router = Router()


@router.get('/health')
def health(request):
    return {'status': 'ok', 'module': 'plan'}
