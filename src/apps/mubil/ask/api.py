"""`ask` sub-router — RAG Gemini sobre datasets movilidad EH (MUST).

Endpoints (PROPUESTA.md §3.2):
  POST /query       → AskQueryIn → AskAnswerOut
  GET  /suggested   → 5 prompts curados (red de seguridad para la demo).

KPI: latencia <3s. Modelo: `gemini-flash` (no Pro). Cache 5 prompts gold pre-calentados.
"""

from ninja import Router

router = Router()


@router.get('/health')
def health(request):
    return {'status': 'ok', 'module': 'ask'}
