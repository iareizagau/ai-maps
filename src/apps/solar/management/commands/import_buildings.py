import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon, LinearRing
from apps.solar.models import Building

class Command(BaseCommand):
    help = 'Import buildings from OpenStreetMap via Overpass API'

    def add_arguments(self, parser):
        parser.add_argument('--bbox', type=str, default='43.316,-1.985,43.322,-1.975', help='lat_min,lon_min,lat_max,lon_max')

    def handle(self, *args, **options):
        bbox = options['bbox']
        self.stdout.write(f'Fetching buildings for bbox [{bbox}] from Overpass...')
        
        query = f"""
        [out:json][timeout:90];
        (
          way["building"]({bbox});
          relation["building"]({bbox});
        );
        out body;
        >;
        out skel qt;
        """
        url = "https://overpass-api.de/api/interpreter"
        headers = {
            'User-Agent': 'MapsEusSolar/1.0 (imanol@maps.eus)',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(url, data={'data': query}, headers=headers, timeout=100)
            response.raise_for_status()
            data = response.json()
            
            elements = data.get('elements', [])
            self.stdout.write(f"Total elements received: {len(elements)}")
            
            # Helper to build geometries
            nodes = {el['id']: (el['lon'], el['lat']) for el in elements if el['type'] == 'node'}
            ways = [el for el in elements if el['type'] == 'way']
            self.stdout.write(f"Total nodes: {len(nodes)}, Total ways: {len(ways)}")
            
            count = 0
            for way in ways:
                if count == 0:
                    self.stdout.write(f"First way tags: {way.get('tags')}")
                osm_id = way['id']
                tags = way.get('tags', {})
                
                # Convert nodes to polygon
                way_nodes = way.get('nodes', [])
                if len(way_nodes) < 3:
                    continue
                
                coords = []
                for node_id in way_nodes:
                    if node_id in nodes:
                        coords.append(nodes[node_id])
                
                if len(coords) < 3:
                    continue
                
                # Close the polygon if not closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                
                try:
                    poly = Polygon(coords)
                    
                    height_str = tags.get('height', tags.get('building:height', ''))
                    height = 9.0
                    if height_str:
                        try:
                            # Remove 'm' if present
                            height = float(height_str.replace('m', '').split(';')[0])
                        except:
                            pass
                    
                    levels_str = tags.get('building:levels', '')
                    if levels_str and not tags.get('height'):
                        try:
                            height = float(levels_str) * 3.0
                        except:
                            pass

                    building, created = Building.objects.update_or_create(
                        osm_id=osm_id,
                        defaults={
                            'name': tags.get('name', ''),
                            'geom': poly,
                            'height': height,
                            'building_type': tags.get('building', 'yes'),
                        }
                    )
                    if created:
                        count += 1
                except Exception as e:
                    # self.stdout.write(f"Error processing way {osm_id}: {e}")
                    continue
            
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} buildings'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
