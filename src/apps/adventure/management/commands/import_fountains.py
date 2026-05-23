import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.adventure.models import Fountain

class Command(BaseCommand):
    help = 'Import drinking water fountains from OpenStreetMap via Overpass API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            type=str,
            help='ISO 3166-1 country code (e.g. ES, FR, CH)'
        )
        parser.add_argument(
            '--region',
            type=str,
            help='ISO 3166-2 region code (e.g. ES-PV, FR-ARA, CH-BE)'
        )
        parser.add_argument(
            '--bbox',
            type=str,
            help='Bounding box in format "min_lon,min_lat,max_lon,max_lat"'
        )

    def handle(self, *args, **options):
        country = options.get('country')
        region = options.get('region')
        bbox = options.get('bbox')
        
        if region:
            area_expr = f'area["ISO3166-2"="{region}"]->.a;'
            filter_expr = '(area.a)'
            self.stdout.write(f'Fetching fountains for region {region} from Overpass API...')
        elif country:
            area_expr = f'area["ISO3166-1"="{country}"]->.a;'
            filter_expr = '(area.a)'
            self.stdout.write(f'Fetching fountains for country {country} from Overpass API...')
        elif bbox:
            coords = [c.strip() for c in bbox.split(',')]
            if len(coords) != 4:
                self.stdout.write(self.style.ERROR('Bbox format must be "min_lon,min_lat,max_lon,max_lat"'))
                return
            # Overpass expects (lat_min, lon_min, lat_max, lon_max)
            area_expr = ''
            filter_expr = f'({coords[1]},{coords[0]},{coords[3]},{coords[2]})'
            self.stdout.write(f'Fetching fountains for bounding box {bbox} from Overpass API...')
        else:
            # Default to ES-PV
            area_expr = 'area["ISO3166-2"="ES-PV"]->.a;'
            filter_expr = '(area.a)'
            self.stdout.write('Fetching fountains for default region (Basque Country, ES-PV) from Overpass API...')

        query = f"""
        [out:json][timeout:90];
        {area_expr}
        node["amenity"="drinking_water"]{filter_expr};
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
            
            if 'remark' in data:
                self.stdout.write(self.style.WARNING(f"Overpass API Warning/Error: {data['remark']}"))
                
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
