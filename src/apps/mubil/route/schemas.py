"""Schemas for `route`. PROPUESTA.md §3.3."""

from typing import List, Optional

from ninja import Schema


class EVPlanIn(Schema):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    vehicle_id: int
    soc_start: float = 80.0  # percentage


class RouteSegment(Schema):
    kind: str  # drive | charge_stop | transit_leg
    distance_km: Optional[float] = None
    duration_min: Optional[int] = None
    meta: dict = {}


class EVPlanOut(Schema):
    polyline: List[List[float]]  # [[lat, lon], ...]
    segments: List[RouteSegment]
    distance_km: float
    duration_min: int
    energy_kwh: float
    estimated_cost_eur: float
