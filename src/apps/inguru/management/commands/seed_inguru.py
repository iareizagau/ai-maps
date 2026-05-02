from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.inguru.models import EnvironmentalStation
from django.utils import timezone

class Command(BaseCommand):
    help = 'Semilla inicial de estaciones para Inguru'

    def handle(self, *args, **options):
        stations_data = [
            # Bilbao
            {
                'name': 'Bilbao - Maria Diaz de Haro',
                'external_id': 'BIL_MDH',
                'station_type': 'AIR',
                'location': Point(-2.9416, 43.2627),
                'municipality': 'Bilbao',
                'province': 'Bizkaia'
            },
            {
                'name': 'Bilbao - Parque Doña Casilda',
                'external_id': 'BIL_PDC',
                'station_type': 'POLLEN',
                'location': Point(-2.9410, 43.2640),
                'municipality': 'Bilbao',
                'province': 'Bizkaia'
            },
            # San Sebastian
            {
                'name': 'Donostia - Easo',
                'external_id': 'SS_EASO',
                'station_type': 'AIR',
                'location': Point(-1.9812, 43.3150),
                'municipality': 'Donostia',
                'province': 'Gipuzkoa'
            },
            # Vitoria
            {
                'name': 'Vitoria - Avenida Gasteiz',
                'external_id': 'VIT_AVG',
                'station_type': 'AIR',
                'location': Point(-2.6820, 42.8465),
                'municipality': 'Vitoria-Gasteiz',
                'province': 'Araba'
            }
        ]

        for data in stations_data:
            station, created = EnvironmentalStation.objects.update_or_create(
                external_id=data['external_id'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Creada estación: {station.name}"))
            else:
                self.stdout.write(f"Actualizada estación: {station.name}")
        
        self.stdout.write(self.style.SUCCESS("Semilla de Inguru completada."))
