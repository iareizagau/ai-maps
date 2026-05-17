from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Seed solar app data: imports buildings via Overpass.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bbox', 
            type=str, 
            default='43.316,-1.985,43.322,-1.975',
            help='Bounding Box (lat_min,lon_min,lat_max,lon_max)'
        )

    def handle(self, *args, **options):
        bbox = options['bbox']
        
        self.stdout.write(self.style.SUCCESS(f"Starting import_buildings for bbox: {bbox}..."))
        
        try:
            call_command('import_buildings', bbox=bbox)
            self.stdout.write(self.style.SUCCESS("Solar seeding complete!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error in import_buildings: {e}"))
