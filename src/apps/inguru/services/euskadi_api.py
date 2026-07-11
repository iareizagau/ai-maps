import requests
import logging
from django.conf import settings
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class EuskadiOpenDataClient:
    """
    Cliente para interactuar con las APIs de Open Data Euskadi.
    """
    BASE_URL = "https://api.euskadi.eus"
    
    # Endpoints base
    ENDPOINTS = {
        "air_quality_stations": "/air-quality/stations",
        "pollen_species": "/pollen-quality/species",
        "water_mass_stations": "/watermass-quality/sampling-points",
        "drinking_water_stations": "/water-quality/sampling-points",
        "euskalmet_forecast": "/euskalmet/weather/forecast/daily",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'EUSKALMET_API_KEY', None)
        self.session = requests.Session()

    def _get(self, endpoint_key: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{self.ENDPOINTS.get(endpoint_key)}"
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching from {endpoint_key}: {e}")
            return {}

    # --- Calidad del Aire (Air Quality) ---
    
    def get_air_quality_stations(self) -> List[Dict[str, Any]]:
        """Obtiene la lista de estaciones de calidad del aire."""
        res = self._get("air_quality_stations")
        return res.get("features", [])

    def get_air_quality_measurements(self, station_id: str, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """
        Obtiene las mediciones horarias de calidad del aire para una estación en un rango de fechas.
        date_from y date_to deben tener formato 'YYYY-MM-DDTHH:MM' (ej: '2026-07-10T00:00').
        """
        url = f"{self.BASE_URL}/air-quality/measurements/hourly/stations/{station_id}/from/{date_from}/to/{date_to}"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching air quality measurements for station {station_id}: {e}")
            return []

    # --- Polen (Pollen Quality) ---

    def get_pollen_species(self) -> List[Dict[str, Any]]:
        """Obtiene todas las especies de polen controladas."""
        res = self._get("pollen_species")
        return res if isinstance(res, list) else []

    def get_pollen_measurements(self, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """
        Obtiene los niveles de polen de todos los municipios en un rango de fechas.
        date_from y date_to deben tener formato 'YYYY-MM-DD'.
        """
        url = f"{self.BASE_URL}/pollen-quality/measurements/municipalities/from/{date_from}/to/{date_to}"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching pollen measurements: {e}")
            return []

    # --- Calidad de Masas de Agua (URA) ---

    def get_water_mass_sampling_points(self) -> List[Dict[str, Any]]:
        """Obtiene los puntos de muestreo de calidad de masas de agua."""
        res = self._get("water_mass_stations")
        return res.get("features", [])

    def get_water_mass_measurements(self, point_id: str, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """
        Obtiene las mediciones de calidad de aguas para un punto específico y rango de fechas.
        date_from y date_to deben tener formato 'YYYY-MM-DD'.
        """
        url = f"{self.BASE_URL}/watermass-quality/measurements/sampling-points/{point_id}/from/{date_from}/to/{date_to}"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            res_json = response.json()
            return res_json.get("measurements", [])
        except Exception as e:
            logger.error(f"Error fetching water mass measurements for point {point_id}: {e}")
            return []

    # --- Aguas de Consumo (Drinking Water) ---

    def get_drinking_water_sampling_points(self) -> List[Dict[str, Any]]:
        """Obtiene los puntos de muestreo de aguas de consumo."""
        res = self._get("drinking_water_stations")
        return res.get("items", [])

    def get_drinking_water_measurements(self, point_id: str, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """
        Obtiene las mediciones de aguas de consumo para un punto específico en un rango de fechas.
        date_from y date_to deben tener formato 'YYYY-MM-DD'.
        """
        url = f"{self.BASE_URL}/water-quality/sampling-points/{point_id}/measurements/from/{date_from}/to/{date_to}"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching drinking water measurements for point {point_id}: {e}")
            return []

    # --- Meteorología (Euskalmet) ---

    def get_weather_forecast(self) -> Dict[str, Any]:
        """
        Obtiene la predicción diaria de Euskalmet.
        Requiere API Key. Si no existe, devuelve datos mock para desarrollo.
        """
        if not self.api_key:
            return {
                "status": "mock",
                "forecast": "Soleado con intervalos nubosos",
                "temp_max": 22,
                "temp_min": 12
            }
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = requests.get(f"{self.BASE_URL}{self.ENDPOINTS['euskalmet_forecast']}", headers=headers, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Euskalmet API failed: {e}")
            return {"status": "error", "message": "Euskalmet API failed"}

