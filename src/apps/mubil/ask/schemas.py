"""Schemas for `ask`. PROPUESTA.md §3.2."""

from typing import List, Optional

from ninja import Schema


class AskQueryIn(Schema):
    q: str
    k: int = 5
    municipality_naia: Optional[str] = None


class AskSource(Schema):
    title: str
    url: str
    score: float
    source_type: str


class AskAnswerOut(Schema):
    answer_md: str
    sources: List[AskSource]
    latency_ms: int
