import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.adventure.models import Fountain

class Command(BaseCommand):
    help = 'Import drinking water fountains from OpenStreetMap via Overpass API'

    def handle(self, *args, **options):
        self.stdout.write('Fetching fountains from Overpass API...')
        
        # Query for Basque Country using ISO code
        query = """
        [out:json][timeout:60];
        area["ISO3166-2"="ES-PV"]->.a;
        node["amenity"="drinking_water"](area.a);
        out body;
        """
        url = "https://overpass-api.de/api/interpreter"
        headers = {
            'User-Agent': 'MapsEusAdventurePlanner/1.0 (imanol@maps.eus)',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(url, data={'data': query}, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            elements = data.get('elements', [])
            self.stdout.write(f'Found {len(elements)} fountains. Importing...')
            
            count = 0
            for el in elements:
                osm_id = el['id']
                lat = el['lat']
                lon = el['lon']
                tags = el.get('tags', {})
                name = tags.get('name', '')
                
                # Update or create
                fountain, created = Fountain.objects.update_or_create(
                    osm_id=osm_id,
                    defaults={
                        'name': name,
                        'location': Point(lon, lat),
                        'description': tags.get('description', ''),
                        'operational': tags.get('disused', 'no') == 'no'
                    }
                )
                if created:
                    count += 1
            
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} new fountains (Total: {len(elements)})'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing fountains: {e}'))
