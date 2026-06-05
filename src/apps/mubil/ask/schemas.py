"""Schemas for `ask`. PROPUESTA.md §3.2."""

from typing import List, Optional

from ninja import Schema


class AskQueryIn(Schema):
    q: str
    k: int = 8
    municipality_naia: Optional[str] = None


class AskSource(Schema):
    title: str
    url: str
    score: float
    source_type: str
    kind: str = "dataset"
    date: Optional[str] = None


class AskAnswerOut(Schema):
    answer_md: str
    sources: List[AskSource]
    latency_ms: int


class SuggestedPromptOut(Schema):
    id: str
    label: str


class CorpusStatsOut(Schema):
    total_documents: int
    with_embedding: int
    pending_embedding: int
