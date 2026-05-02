import logging
from django.utils import timezone
from django.contrib.gis.geos import Point
from .euskadi_api import EuskadiOpenDataClient
from ..models import EnvironmentalStation, Measurement

logger = logging.getLogger(__name__)

class InguruIngestor:
    def __init__(self):
        self.client = EuskadiOpenDataClient()

    def ingest_air_quality(self):
        """Ingesta de calidad del aire y creación de estaciones si no existen."""
        data = self.client.get_air_quality()
        logger.info(f"Air Quality Data type: {type(data)}")
        if not data:
            return 0

        count = 0
        # Supongamos que data es una lista de mediciones
        for item in data:
            # Extraer info de la estación
            ext_id = item.get('stationId') or item.get('codigo')
            if not ext_id: continue

            station, _ = EnvironmentalStation.objects.update_or_create(
                external_id=ext_id,
                defaults={
                    'name': item.get('stationName') or item.get('nombre') or f"Estación {ext_id}",
                    'station_type': EnvironmentalStation.StationType.AIR,
                    'location': Point(float(item.get('longitude', 0)), float(item.get('latitude', 0))),
                    'municipality': item.get('municipality', ''),
                }
            )

            # Guardar medición
            Measurement.objects.create(
                station=station,
                timestamp=timezone.now(), # O usar el del item si existe
                values=item.get('measurements') or item,
                eco_score=self._calculate_eco_score(item)
            )
            count += 1
        return count

    def ingest_pollen(self):
        """Ingesta de niveles de polen."""
        data = self.client.get_pollen_levels()
        logger.info(f"Pollen Data type: {type(data)}")
        if not data:
            return 0
        
        count = 0
        for item in data:
            ext_id = item.get('stationId') or item.get('codigo')
            if not ext_id: continue

            station, _ = EnvironmentalStation.objects.update_or_create(
                external_id=f"POLLEN_{ext_id}",
                defaults={
                    'name': item.get('stationName') or f"Polen {ext_id}",
                    'station_type': EnvironmentalStation.StationType.POLLEN,
                    'location': Point(float(item.get('longitude', 0)), float(item.get('latitude', 0))),
                }
            )

            Measurement.objects.create(
                station=station,
                timestamp=timezone.now(),
                values=item
            )
            count += 1
        return count

    def _calculate_eco_score(self, data):
        """Lógica simplificada para calcular el Eco-Score (0-100)."""
        # Esto es un placeholder. En realidad usaríamos fórmulas de ICA (Índice Calidad Aire).
        return 80 # Valor por defecto para el MVP
