from ninja import Router, Query
from django.shortcuts import get_object_or_404
from typing import List
from .models import EnvironmentalStation, Measurement
from .schemas import StationOut, MeasurementOut, EcoScoreSummary
from .services.euskadi_api import EuskadiOpenDataClient

router = Router()

def _station_to_schema(station: EnvironmentalStation) -> dict:
    return {
        'id': station.id,
        'name': station.name,
        'external_id': station.external_id,
        'station_type': station.station_type,
        'latitude': station.location.y,
        'longitude': station.location.x,
        'municipality': station.municipality,
        'province': station.province,
        'metadata': station.metadata
    }

@router.get("/stations/", response=List[StationOut])
def list_stations(request, station_type: str = Query(None)):
    """List all environmental stations, optionally filtered by type"""
    queryset = EnvironmentalStation.objects.all()
    if station_type:
        queryset = queryset.filter(station_type=station_type)
    return [_station_to_schema(s) for s in queryset]

@router.get("/stations/{station_id}/latest/", response=MeasurementOut)
def get_latest_measurement(request, station_id: int):
    """Get the most recent measurement for a specific station"""
    station = get_object_or_404(EnvironmentalStation, id=station_id)
    measurement = station.measurements.first()
    if not measurement:
        # If no measurement in DB, try to fetch from API and cache?
        # For now return 404 if not found
        from ninja.errors import HttpError
        raise HttpError(404, "No measurement found for this station")
    return measurement

@router.get("/summary/eco-score/", response=EcoScoreSummary)
def get_eco_score(request, lat: float, lon: float):
    """
    Calculates a unified Eco-Score for a given coordinate based on nearest stations.
    """
    # This is a placeholder for the unified score logic
    # In a real scenario, we would find the nearest AIR, POLLEN and METEO stations
    from django.contrib.gis.geos import Point
    from django.contrib.gis.db.models.functions import Distance
    from django.utils import timezone
    
    pnt = Point(lon, lat, srid=4326)
    nearest_station = EnvironmentalStation.objects.annotate(
        distance=Distance('location', pnt)
    ).order_by('distance').first()

    if not nearest_station:
        from ninja.errors import HttpError
        raise HttpError(404, "No stations found nearby")

    measurement = nearest_station.measurements.first()
    
    return {
        "station_name": nearest_station.name,
        "station_type": nearest_station.station_type,
        "score": 85,  # Mock score
        "status": "Bueno",
        "main_pollutant": "O3",
        "last_update": measurement.timestamp if measurement else timezone.now()
    }
