import os
import urllib.request
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Seed adventure app data: downloads OSM PBF, runs POI import, and imports fountains.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pbf-url', 
            type=str, 
            default='https://download.geofabrik.de/europe/spain-latest.osm.pbf',
            help='URL of the OSM PBF file to download'
        )
        parser.add_argument(
            '--pbf-file', 
            type=str, 
            help='Local path to OSM PBF file (skips download if provided)'
        )
        parser.add_argument(
            '--skip-fountains', 
            action='store_true', 
            help='Skip importing fountains'
        )
        parser.add_argument(
            '--skip-pois', 
            action='store_true', 
            help='Skip importing POIs'
        )

    def handle(self, *args, **options):
        pbf_url = options['pbf_url']
        pbf_file = options.get('pbf_file')
        skip_fountains = options['skip_fountains']
        skip_pois = options['skip_pois']
        
        # 1. Import Fountains
        if not skip_fountains:
            self.stdout.write(self.style.SUCCESS("Starting import_fountains..."))
            try:
                call_command('import_fountains')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in import_fountains: {e}"))
        
        # 2. Import POIs
        if not skip_pois:
            self.stdout.write(self.style.SUCCESS("Starting import_adventure_pois..."))
            temp_file = False
            
            if not pbf_file:
                pbf_file = 'temp_adventure.osm.pbf'
                temp_file = True
                self.stdout.write(self.style.WARNING(f"Downloading PBF from {pbf_url}... This may take a while."))
                try:
                    urllib.request.urlretrieve(pbf_url, pbf_file)
                    self.stdout.write(self.style.SUCCESS("Download complete."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Failed to download PBF: {e}"))
                    return
            
            try:
                call_command('import_adventure_pois', pbf_file)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in import_adventure_pois: {e}"))
            
            if temp_file and os.path.exists(pbf_file):
                self.stdout.write("Cleaning up temporary PBF file...")
                os.remove(pbf_file)
        
        self.stdout.write(self.style.SUCCESS("Adventure seeding complete!"))
