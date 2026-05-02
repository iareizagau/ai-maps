from ninja import Schema
from datetime import datetime
from typing import Dict, Any, List, Optional

class StationOut(Schema):
    id: int
    name: str
    external_id: str
    station_type: str
    latitude: float
    longitude: float
    municipality: str
    province: str
    metadata: Dict[str, Any]

class MeasurementOut(Schema):
    id: int
    station_id: int
    timestamp: datetime
    values: Dict[str, Any]
    eco_score: Optional[int]

class EcoScoreSummary(Schema):
    station_name: str
    station_type: str
    score: int
    status: str  # e.g., "Bueno", "Regular", "Pobre"
    main_pollutant: Optional[str]
    last_update: datetime
