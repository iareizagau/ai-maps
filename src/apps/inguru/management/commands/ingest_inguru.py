from django.core.management.base import BaseCommand
from apps.inguru.services.ingestion import InguruIngestor

class Command(BaseCommand):
    help = 'Ejecuta la ingesta de datos desde Open Data Euskadi'

    def handle(self, *args, **options):
        ingestor = InguruIngestor()
        
        self.stdout.write("Iniciando ingesta de Calidad del Aire...")
        air_count = ingestor.ingest_air_quality()
        self.stdout.write(self.style.SUCCESS(f"Procesadas {air_count} estaciones de aire."))

        self.stdout.write("Iniciando ingesta de Polen...")
        pollen_count = ingestor.ingest_pollen()
        self.stdout.write(self.style.SUCCESS(f"Procesadas {pollen_count} estaciones de polen."))

        self.stdout.write(self.style.SUCCESS("Ingesta completada correctamente."))
