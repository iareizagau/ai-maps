from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from apps.inguru.models import EnvironmentalStation


class Command(BaseCommand):
    help = "Semilla inicial de estaciones para Inguru"

    def handle(self, *args, **options):
        # Delete old seeded stations with incorrect IDs to avoid duplicates
        old_ids = ["BIL_MDH", "BIL_PDC", "SS_EASO", "VIT_AVG"]
        deleted_count, _ = EnvironmentalStation.objects.filter(
            external_id__in=old_ids
        ).delete()
        if deleted_count > 0:
            self.stdout.write(
                f"Eliminadas {deleted_count} estaciones antiguas obsoletas."
            )

        stations_data = [
            # Bilbao
            {
                "name": "Bilbao - Maria Diaz de Haro",
                "external_id": "81",
                "station_type": "AIR",
                "location": Point(-2.9416, 43.2627),
                "municipality": "Bilbao",
                "province": "Bizkaia",
            },
            {
                "name": "Bilbao - Parque Doña Casilda",
                "external_id": "POLLEN_020",
                "station_type": "POLLEN",
                "location": Point(-2.9410, 43.2640),
                "municipality": "Bilbao",
                "province": "Bizkaia",
            },
            # San Sebastian
            {
                "name": "Donostia - Easo",
                "external_id": "89",
                "station_type": "AIR",
                "location": Point(-1.9812, 43.3150),
                "municipality": "Donostia",
                "province": "Gipuzkoa",
            },
            # Vitoria
            {
                "name": "Vitoria - Avenida Gasteiz",
                "external_id": "78",
                "station_type": "AIR",
                "location": Point(-2.6820, 42.8465),
                "municipality": "Vitoria-Gasteiz",
                "province": "Araba",
            },
        ]

        for data in stations_data:
            station, created = EnvironmentalStation.objects.update_or_create(
                external_id=data["external_id"], defaults=data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Creada estación: {station.name}")
                )
            else:
                self.stdout.write(f"Actualizada estación: {station.name}")

        self.stdout.write(self.style.SUCCESS("Semilla de Inguru completada."))
