import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.adventure.models import PointOfInterest

class Command(BaseCommand):
    help = 'Import rich POIs (shelters, cafes, stations, campsites) from OpenStreetMap via Overpass API'

    def handle(self, *args, **options):
        self.stdout.write('Fetching POIs from Overpass API...')
        
        # Query for Basque Country using ISO code
        # We fetch: shelter, alpine_hut, wilderness_hut, cafe, bar, pub, restaurant, station, camp_site, caravan_site
        query = """
        [out:json][timeout:90];
        area["ISO3166-2"="ES-PV"]->.a;
        (
          node["amenity"="shelter"](area.a);
          node["tourism"="alpine_hut"](area.a);
          node["tourism"="wilderness_hut"](area.a);
          node["amenity"="cafe"](area.a);
          node["amenity"="restaurant"](area.a);
          node["tourism"="camp_site"](area.a);
          node["tourism"="caravan_site"](area.a);
          node["railway"="station"](area.a);
          node["public_transport"="station"](area.a);
        );
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
            self.stdout.write(f'Found {len(elements)} POI elements. Importing...')
            
            count = 0
            pois_to_create = []
            
            for el in elements:
                osm_id = el['id']
                lat = el['lat']
                lon = el['lon']
                tags = el.get('tags', {})
                name = tags.get('name', '')
                
                # Determine POI type
                poi_type = 'other'
                
                # 1. Shelter
                if tags.get('amenity') == 'shelter' or tags.get('tourism') in ['alpine_hut', 'wilderness_hut']:
                    poi_type = 'shelter'
                # 2. Cafe / Rest
                elif tags.get('amenity') in ['cafe', 'restaurant', 'bar', 'pub']:
                    poi_type = 'cafe'
                # 3. Camping (Paid)
                elif tags.get('tourism') == 'camp_site':
                    # Determine if it's paid or free (default paid)
                    fee = tags.get('fee', 'yes')
                    if fee == 'no':
                        poi_type = 'camp_free'
                    else:
                        poi_type = 'camp_paid'
                # 4. Camper / Free area
                elif tags.get('tourism') == 'caravan_site' or tags.get('amenity') == 'caravan_site':
                    poi_type = 'camp_free'
                # 5. Station
                elif tags.get('railway') == 'station' or tags.get('public_transport') == 'station':
                    poi_type = 'station'
                
                # We skip 'other' to keep it clean and high-quality
                if poi_type == 'other':
                    continue
                
                poi = PointOfInterest(
                    osm_id=osm_id,
                    poi_type=poi_type,
                    name=name,
                    location=Point(lon, lat, srid=4326),
                    tags=tags
                )
                pois_to_create.append(poi)
            
            # Bulk create
            if pois_to_create:
                PointOfInterest.objects.bulk_create(pois_to_create, ignore_conflicts=True)
                count = len(pois_to_create)
                
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} rich POIs from Overpass!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing POIs: {e}'))
