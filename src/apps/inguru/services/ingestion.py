import logging
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware, make_aware

from ..models import EnvironmentalStation, Measurement
from .euskadi_api import EuskadiOpenDataClient

logger = logging.getLogger(__name__)


class InguruIngestor:
    def __init__(self):
        self.client = EuskadiOpenDataClient()

    def ingest_air_quality(self):
        """Ingesta de calidad del aire y creación de estaciones si no existen."""
        # 1. Obtener y actualizar/crear todas las estaciones
        station_features = self.client.get_air_quality_stations()
        logger.info(f"Retrieved {len(station_features)} air quality stations.")

        for feature in station_features:
            props = feature.get("properties", {})
            ext_id = props.get("id")
            if not ext_id:
                continue

            coords = feature.get("geometry", {}).get("coordinates", [0, 0])
            loc_data = props.get("location", {})

            EnvironmentalStation.objects.update_or_create(
                external_id=str(ext_id),
                defaults={
                    "name": props.get("name") or f"Estación {ext_id}",
                    "station_type": EnvironmentalStation.StationType.AIR,
                    "location": Point(float(coords[0]), float(coords[1])),
                    "municipality": loc_data.get("municipality", ""),
                    "province": loc_data.get("county", ""),
                    "metadata": {"address": props.get("address", "")},
                },
            )

        # 2. Obtener mediciones para las estaciones activas/actualizadas
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        date_from = yesterday.strftime("%Y-%m-%dT00:00")
        date_to = now.strftime("%Y-%m-%dT23:59")

        air_stations = EnvironmentalStation.objects.filter(
            station_type=EnvironmentalStation.StationType.AIR
        )
        measurement_count = 0

        for station in air_stations:
            measurements_data = self.client.get_air_quality_measurements(
                station.external_id, date_from, date_to
            )
            for item in measurements_data:
                date_str = item.get("date")
                if not date_str:
                    continue

                timestamp = parse_datetime(date_str)
                if not timestamp:
                    continue
                if not is_aware(timestamp):
                    timestamp = make_aware(timestamp)

                station_list = item.get("station", [])
                if not station_list:
                    continue
                station_data = station_list[0]

                # Mapear mediciones a un diccionario plano
                values_dict = {}
                for m in station_data.get("measurements", []):
                    values_dict[m["name"]] = m["value"]

                Measurement.objects.update_or_create(
                    station=station,
                    timestamp=timestamp,
                    defaults={
                        "values": values_dict,
                        "eco_score": self._calculate_eco_score(station_data),
                    },
                )
                measurement_count += 1

        return measurement_count

    def ingest_pollen(self):
        """Ingesta de niveles de polen."""
        now = timezone.now()
        fourteen_days_ago = now - timedelta(days=14)
        date_from = fourteen_days_ago.strftime("%Y-%m-%d")
        date_to = now.strftime("%Y-%m-%d")

        data = self.client.get_pollen_measurements(date_from, date_to)
        logger.info(f"Pollen measurements retrieved: {len(data)}")
        if not data:
            return 0

        POLLEN_STATIONS_INFO = {
            "020": {
                "name": "Bilbao - Parque Doña Casilda",
                "location": Point(-2.9410, 43.2640),
                "municipality": "Bilbao",
                "province": "Bizkaia",
            },
            "059": {
                "name": "Vitoria-Gasteiz - Mendizorrotza",
                "location": Point(-2.6820, 42.8400),
                "municipality": "Vitoria-Gasteiz",
                "province": "Araba",
            },
            "069": {
                "name": "Donostia-San Sebastián - Easo",
                "location": Point(-1.9812, 43.3150),
                "municipality": "Donostia-San Sebastián",
                "province": "Gipuzkoa",
            },
        }

        count = 0
        for item in data:
            municipality_id = item.get("municipalityId")
            municipality_name = item.get("municipalityName")
            if not municipality_id:
                continue

            info = POLLEN_STATIONS_INFO.get(
                municipality_id,
                {
                    "name": f"Polen - {municipality_name}",
                    "location": Point(-2.9, 43.2),
                    "municipality": municipality_name,
                    "province": "",
                },
            )

            station, _ = EnvironmentalStation.objects.update_or_create(
                external_id=f"POLLEN_{municipality_id}",
                defaults={
                    "name": info["name"],
                    "station_type": EnvironmentalStation.StationType.POLLEN,
                    "location": info["location"],
                    "municipality": info["municipality"],
                    "province": info["province"],
                },
            )

            date_str = item.get("date")
            if not date_str:
                continue

            timestamp = parse_datetime(f"{date_str}T00:00:00")
            if not timestamp:
                continue
            if not is_aware(timestamp):
                timestamp = make_aware(timestamp)

            # Mapear las especies de polen
            values_dict = {}
            for m in item.get("measurements", []):
                values_dict[m["specieId"]] = {
                    "name": m["specieName"],
                    "count": m["pollenCount"],
                }

            # Calcular eco score basándonos en el conteo total
            total_count = item.get("measurementsTotalCount") or 0
            if total_count < 50:
                eco_score = 90
            elif total_count < 150:
                eco_score = 75
            elif total_count < 300:
                eco_score = 60
            else:
                eco_score = 45

            Measurement.objects.update_or_create(
                station=station,
                timestamp=timestamp,
                defaults={"values": values_dict, "eco_score": eco_score},
            )
            count += 1

        return count

    def _calculate_eco_score(self, station_data):
        """Lógica para calcular el Eco-Score (0-100) basado en calidad del aire."""
        aq = station_data.get("airQualityStation")
        if not aq:
            for m in station_data.get("measurements", []):
                if "airquality" in m:
                    aq = m["airquality"]
                    break

        if aq:
            aq = aq.lower()
            if "muy buena" in aq:
                return 95
            elif "buena" in aq:
                return 80
            elif "regular" in aq:
                return 60
            elif "mala" in aq or "pobre" in aq:
                return 40
            elif "muy mala" in aq:
                return 20
        return 75
