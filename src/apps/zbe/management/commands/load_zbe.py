import json
import os
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from apps.zbe.models import LowEmissionZone

class Command(BaseCommand):
    help = 'Carga la ZBE de Donostia desde un archivo GeoJSON'

    def handle(self, *args, **options):
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f'Directorio de datos no encontrado: {data_dir}'))
            return

        files = [f for f in os.listdir(data_dir) if f.endswith('.geojson')]
        
        if not files:
            self.stdout.write(self.style.WARNING('No se encontraron archivos GeoJSON en el directorio data.'))
            return

        total_count = 0
        for filename in files:
            file_path = os.path.join(data_dir, filename)
            self.stdout.write(f'Procesando {filename}...')
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error al leer {filename}: {e}'))
                    continue

            for feature in data.get('features', []):
                properties = feature.get('properties', {})
                geometry = feature.get('geometry')
                
                if not geometry:
                    continue

                geom_type = geometry.get('type')
                if geom_type not in ['Polygon', 'MultiPolygon']:
                    self.stdout.write(self.style.WARNING(f'  [Saltado] Tipo de geometría {geom_type} no compatible con ZBE.'))
                    continue

                # Try common name fields
                name = properties.get('Izena') or properties.get('zona_zbe') or properties.get('Nombre') or properties.get('name') or properties.get('nombre')
                if not name:
                    name = os.path.splitext(filename)[0].replace('_', ' ').title()
                
                # Combine extra properties into description
                description_parts = [f"Fuente: {filename}"]
                for k, v in properties.items():
                    if k.lower() not in ['izena', 'zona_zbe', 'nombre', 'name', 'fid', 'objectid']:
                        description_parts.append(f"{k}: {v}")
                description = "\n".join(description_parts)
                
                try:
                    # Fix malformed nesting (some exporters add extra brackets)
                    def get_depth(l):
                        if isinstance(l, list) and len(l) > 0:
                            return 1 + get_depth(l[0])
                        return 0
                    
                    coords = geometry.get('coordinates', [])
                    depth = get_depth(coords)
                    
                    # Polygon should have depth 3, MultiPolygon depth 4
                    if geom_type == 'Polygon' and depth == 4:
                        geometry['type'] = 'MultiPolygon'
                    elif geom_type == 'MultiPolygon' and depth == 3:
                        geometry['type'] = 'Polygon'

                    # Convert geometry to GEOS object
                    geom = GEOSGeometry(json.dumps(geometry))
                    
                    # Force 2D if it has Z dimension
                    if geom.hasz:
                        from django.contrib.gis.geos import WKBWriter
                        wkb_w = WKBWriter()
                        wkb_w.outdim = 2
                        geom = GEOSGeometry(wkb_w.write(geom))
                    
                    # Ensure it's a MultiPolygon
                    if isinstance(geom, Polygon):
                        geom = MultiPolygon(geom)
                    elif not isinstance(geom, MultiPolygon):
                         self.stdout.write(self.style.WARNING(f'  [Saltado] Geometría no es Polygon/MultiPolygon: {name}'))
                         continue
                    
                    # Create or update
                    zone, created = LowEmissionZone.objects.update_or_create(
                        name=name,
                        defaults={
                            'description': description,
                            'geom': geom
                        }
                    )
                    
                    status = "Creada" if created else "Actualizada"
                    self.stdout.write(self.style.SUCCESS(f'  [{status}] {name}'))
                    total_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error procesando zona en {filename}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Proceso finalizado. Total de zonas procesadas: {total_count}'))
