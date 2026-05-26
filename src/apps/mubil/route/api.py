"""`route` sub-router — EV-aware multimodal (MOCK, datos precomputados).

Endpoints (PROPUESTA.md §3.3):
  POST /ev-plan   → EVPlanIn → EVPlanOut

MVP demo set: 5 pares O-D precomputados (Donostia ↔ Bilbao/Vitoria/Pamplona/Tolosa/Eibar).
Para queries fuera del set, fallback simple Dijkstra (sin SOC dinámico, sin GTFS).

Construcción real (pgRouting+SOC+GTFS multimodal): fuera de scope, ver §6.
"""

from ninja import Router

router = Router()


@router.get('/health')
def health(request):
    return {'status': 'ok', 'module': 'route'}
