"""Root Ninja router for mubil. Mounts 4 sub-routers per PROPUESTA.md §3 / §17:

  /estrata/api/v1/advisor/  — TCO eléctrico vs combustión (MUST)
  /estrata/api/v1/ask/      — RAG Gemini sobre datasets movilidad (MUST)
  /estrata/api/v1/route/    — EV-aware multimodal (MOCK)
  /estrata/api/v1/plan/     — heatmap demanda carga (MOCK)
"""

from ninja import Router

from .advisor.api import router as advisor_router
from .ask.api import router as ask_router
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
