import time
import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.gailur.models import Crag

class Command(BaseCommand):
    help = 'Geocodes Crags using Nominatim API'

    def handle(self, *args, **options):
        # We only geocode those at (0,0)
        target_point = Point(0, 0)
        crags = Crag.objects.filter(location=target_point)
        total = crags.count()
        
        self.stdout.write(self.style.SUCCESS(f'Found {total} crags to geocode.'))
        
        headers = {
            'User-Agent': 'GailurApp/1.0 (Maps.eus)'
        }
        
        success_count = 0
        
        for i, crag in enumerate(crags):
            name = crag.name_es or crag.name_eu
            self.stdout.write(f'[{i+1}/{total}] Searching for: {name}...')
            
            try:
                # We add 'Spain' to increase accuracy
                url = f'https://nominatim.openstreetmap.org/search?q={name}, Spain&format=json&limit=1'
                response = requests.get(url, headers=headers)
                data = response.json()
                
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    
                    crag.location = Point(lon, lat)
                    crag.save()
                    
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Found at: {lat}, {lon}'))
                    success_count += 1
                else:
                    # Try without "Spain" as fallback (some might be in the Pyrenees/France side)
                    url = f'https://nominatim.openstreetmap.org/search?q={name}&format=json&limit=1'
                    response = requests.get(url, headers=headers)
                    data = response.json()
                    if data:
                        lat = float(data[0]['lat'])
                        lon = float(data[0]['lon'])
                        crag.location = Point(lon, lat)
                        crag.save()
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Found at: {lat}, {lon} (global)'))
                        success_count += 1
                    else:
                        self.stdout.write(self.style.WARNING(f'  ✗ No results found.'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ! Error: {str(e)}'))
            
            # Nominatim policy requires 1 request per second
            time.sleep(1.1)

        self.stdout.write(self.style.SUCCESS(f'Finished! Successfully geocoded {success_count}/{total} crags.'))
