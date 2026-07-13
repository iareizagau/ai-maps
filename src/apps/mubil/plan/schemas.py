"""Schemas for `plan`. PROPUESTA.md §3.4."""

from typing import Literal

from ninja import Schema


class HeatmapQuery(Schema):
    municipality_naia: str
    horizon: Literal[1, 3, 5] = 3


class TopLocationOut(Schema):
    h3_index: str
    municipality_naia: str
    score: float
    components: dict
