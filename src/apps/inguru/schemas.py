from datetime import datetime
from typing import Any

from ninja import Schema


class StationOut(Schema):
    id: int
    name: str
    external_id: str
    station_type: str
    latitude: float
    longitude: float
    municipality: str
    province: str
    metadata: dict[str, Any]


class MeasurementOut(Schema):
    id: int
    station_id: int
    timestamp: datetime
    values: dict[str, Any]
    eco_score: int | None


class EcoScoreSummary(Schema):
    station_name: str
    station_type: str
    score: int
    status: str  # e.g., "Bueno", "Regular", "Pobre"
    main_pollutant: str | None
    last_update: datetime
