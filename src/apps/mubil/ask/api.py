"""`ask` sub-router — RAG Gemini over EH mobility datasets (MUST).

Endpoints (PROPUESTA.md §3.2):
  GET  /health          → liveness.
  GET  /suggested       → curated gold prompts (safety net for the demo).
  GET  /corpus/stats    → quick visibility into ingest/embed progress.
  POST /query           → AskQueryIn → AskAnswerOut.

KPI: latency <3s. Model: gemini-2.0-flash. Cache pre-warmed gold prompts.
"""

from __future__ import annotations

from typing import List

from ninja import Router

from apps.mubil.ask import services
from apps.mubil.ask.schemas import (
    AskAnswerOut,
    AskQueryIn,
    CorpusStatsOut,
    SuggestedPromptOut,
)
from apps.mubil.models import MobilityDocument

router = Router()


@router.get("/health")
def health(request):
    return {"status": "ok", "module": "ask"}


@router.get("/suggested", response=List[SuggestedPromptOut])
def suggested(request):
    """Curated prompts pre-warmed for the demo (safety net)."""
    return services.list_suggested()


@router.get("/corpus/stats", response=CorpusStatsOut)
def corpus_stats(request):
    """Quick health metric: how much of the corpus has embeddings."""
    total = MobilityDocument.objects.count()
    with_emb = MobilityDocument.objects.exclude(embedding__isnull=True).count()
    return {
        "total_documents": total,
        "with_embedding": with_emb,
        "pending_embedding": total - with_emb,
    }


@router.post("/query", response={200: AskAnswerOut, 400: dict})
def post_query(request, payload: AskQueryIn):
    """RAG pipeline: embed query → pgvector top-k → Gemini Flash answer."""
    try:
        result = services.answer(
            query=payload.q,
            k=payload.k,
            municipality_naia=payload.municipality_naia,
        )
    except ValueError as e:
        return 400, {"message": str(e)}
    return 200, result.to_out()
