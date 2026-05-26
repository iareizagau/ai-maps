"""Root Ninja router for mubil. Mounts 4 sub-routers per PROPUESTA.md §3 / §17:

  /api/mubil/v1/advisor/  — TCO eléctrico vs combustión (MUST)
  /api/mubil/v1/ask/      — RAG Gemini sobre datasets movilidad (MUST)
  /api/mubil/v1/route/    — EV-aware multimodal (MOCK)
  /api/mubil/v1/plan/     — heatmap demanda carga (MOCK)
"""

from ninja import Router

from .advisor.api import router as advisor_router
from .ask.api import router as ask_router
from .route.api import router as route_router
from .plan.api import router as plan_router


router = Router()
router.add_router('/advisor', advisor_router, tags=['advisor'])
router.add_router('/ask', ask_router, tags=['ask'])
router.add_router('/route', route_router, tags=['route'])
router.add_router('/plan', plan_router, tags=['plan'])


@router.get('/health')
def health(request):
    return {'status': 'ok', 'module': 'mubil', 'version': '0.1.0'}
