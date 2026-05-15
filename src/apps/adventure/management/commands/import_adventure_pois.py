import osmium
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.adventure.models import PointOfInterest

class POIHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.pois = []
        self.batch_size = 5000

    def save_batch(self):
        if self.pois:
            PointOfInterest.objects.bulk_create(
                self.pois, 
                ignore_conflicts=True
            )
            self.pois = []

    def process_node(self, node):
        tags = dict(node.tags)
        poi_type = None

        if tags.get('amenity') == 'drinking_water' or tags.get('waterway') == 'water_point':
            poi_type = 'water'
        elif tags.get('tourism') in ['alpine_hut', 'wilderness_hut'] or tags.get('amenity') == 'shelter':
            poi_type = 'shelter'
        elif tags.get('amenity') in ['cafe', 'bar', 'restaurant']:
            poi_type = 'cafe'
        elif tags.get('public_transport') == 'station' or tags.get('railway') == 'station' or tags.get('highway') == 'bus_stop':
            poi_type = 'station'

        if poi_type:
            # osmium locations are valid if apply_file(locations=True) is used, but for nodes it's always valid
            poi = PointOfInterest(
                osm_id=node.id,
                poi_type=poi_type,
                name=tags.get('name', ''),
                location=Point(node.location.lon, node.location.lat, srid=4326),
                tags=tags
            )
            self.pois.append(poi)

            if len(self.pois) >= self.batch_size:
                self.save_batch()

    def node(self, n):
        self.process_node(n)

class Command(BaseCommand):
    help = 'Importa Puntos de Interés (Fuentes, Refugios, Transporte) desde un archivo OSM PBF'

    def add_arguments(self, parser):
        parser.add_argument('pbf_file', type=str, help='Ruta al archivo .osm.pbf (ej: spain-latest.osm.pbf)')

    def handle(self, *args, **options):
        pbf_file = options['pbf_file']
        
        self.stdout.write(self.style.SUCCESS(f'Iniciando importación desde {pbf_file}...'))
        
        # Limpiar tabla antes de importar opcionalmente
        # PointOfInterest.objects.all().delete()
        
        handler = POIHandler()
        try:
            handler.apply_file(pbf_file) # nodes always have locations, no need for locations=True
            handler.save_batch() # Guardar el último lote
            
            count = PointOfInterest.objects.count()
            self.stdout.write(self.style.SUCCESS(f'Importación completada. Total de POIs en BD: {count}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al procesar: {str(e)}'))
