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
    
    # Endpoints
    ENDPOINTS = {
        "air_quality_stations": "/air-quality/stations",
        "air_quality_latest": "/air-quality/measurements",
        "pollen_species": "/pollen-quality/species",
        "pollen_latest": "/pollen-quality/measurements",
        "water_mass_stations": "/watermass-quality/sampling-points",
        "water_mass_latest": "/watermass-quality/measurements",
        "drinking_water_stations": "/water-quality/sampling-points",
        "drinking_water_latest": "/water-quality/measurements",
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

    def get_air_quality(self) -> List[Dict[str, Any]]:
        """Obtiene las mediciones más recientes de calidad del aire."""
        return self._get("air_quality_latest")

    def get_pollen_levels(self) -> List[Dict[str, Any]]:
        """Obtiene los niveles de polen actuales."""
        return self._get("pollen_latest")

    def get_water_quality(self) -> List[Dict[str, Any]]:
        """Obtiene la calidad de las masas de agua (URA)."""
        return self._get("water_mass_latest")

    def get_drinking_water(self) -> List[Dict[str, Any]]:
        """Obtiene datos de la red de vigilancia de aguas de consumo."""
        return self._get("drinking_water_latest")

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
        
        # En una implementación real, aquí se gestionaría el JWT de Euskalmet
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = requests.get(f"{self.BASE_URL}{self.ENDPOINTS['euskalmet_forecast']}", headers=headers)
            return response.json()
        except:
            return {"status": "error", "message": "Euskalmet API failed"}
