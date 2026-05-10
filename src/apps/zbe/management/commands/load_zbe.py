import json
import os
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from apps.zbe.models import LowEmissionZone

class Command(BaseCommand):
    help = 'Carga datos de ZBE desde archivos GeoJSON en la carpeta data/'

    def handle(self, *args, **options):
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f'Directorio de datos no encontrado: {data_dir}'))
            return

        files = [f for f in os.listdir(data_dir) if f.endswith('.geojson')]
        
        if not files:
            self.stdout.write(self.style.WARNING('No se encontraron archivos GeoJSON.'))
            return

        total_count = 0
        for filename in files:
            file_path = os.path.join(data_dir, filename)
            self.stdout.write(f'Procesando {filename}...')
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error al leer {filename}: {e}'))
                    continue

            # Detectar SRID del archivo
            root_srid = 4326
            crs = data.get('crs', {})
            if crs:
                crs_name = crs.get('properties', {}).get('name', '')
                if 'EPSG' in crs_name:
                    try:
                        # Extraer número de strings como "urn:ogc:def:crs:EPSG::27700" o "EPSG:27700"
                        root_srid = int(crs_name.replace('::', ':').split(':')[-1])
                    except:
                        pass

            # Agrupador para fusionar fragmentos con el mismo nombre
            zones_to_process = {} # name -> {'desc': str, 'polygons': []}

            for feature in data.get('features', []):
                properties = feature.get('properties', {})
                geometry = feature.get('geometry')
                
                if not geometry:
                    continue

                geom_type = geometry.get('type')
                if geom_type not in ['Polygon', 'MultiPolygon']:
                    # Ignorar puntos o líneas pero avisar solo si no es Point (para evitar ruido con Málaga)
                    if geom_type != 'Point':
                        self.stdout.write(self.style.WARNING(f'  [Saltado] Tipo de geometría {geom_type} no compatible.'))
                    continue

                # Detectar nombre
                name = properties.get('Izena') or properties.get('zona_zbe') or properties.get('Nombre') or \
                       properties.get('name') or properties.get('nombre') or properties.get('BOUNDARY')
                
                if not name:
                    name = os.path.splitext(filename)[0].replace('_', ' ').title()
                
                # Normalizar nombres genéricos para evitar colisiones entre ciudades
                if name.lower() in ['low emission zone', 'zbe', 'zbe interior', 'zbe exterior']:
                    city = os.path.splitext(filename)[0].split('_')[-1].title()
                    name = f"{name} ({city})"

                try:
                    # Corregir anidación malformada (extra brackets)
                    def get_depth(l):
                        if isinstance(l, list) and len(l) > 0:
                            return 1 + get_depth(l[0])
                        return 0
                    
                    coords = geometry.get('coordinates', [])
                    depth = get_depth(coords)
                    
                    if geom_type == 'Polygon' and depth == 4:
                        geometry['type'] = 'MultiPolygon'
                    elif geom_type == 'MultiPolygon' and depth == 3:
                        geometry['type'] = 'Polygon'

                    # Crear geometría GEOS
                    geom = GEOSGeometry(json.dumps(geometry))
                    if geom.srid is None or geom.srid <= 0:
                        geom.srid = root_srid
                    
                    # Transformar a WGS84 si es necesario
                    if geom.srid != 4326:
                        geom.transform(4326)

                    # Forzar 2D
                    if geom.hasz:
                        from django.contrib.gis.geos import WKBWriter
                        wkb_w = WKBWriter()
                        wkb_w.outdim = 2
                        geom = GEOSGeometry(wkb_w.write(geom))

                    # Acumular polígonos para este nombre
                    if name not in zones_to_process:
                        description_parts = [f"Fuente: {filename}"]
                        for k, v in properties.items():
                            if k.lower() not in ['izena', 'zona_zbe', 'nombre', 'name', 'fid', 'objectid', 'boundary']:
                                description_parts.append(f"{k}: {v}")
                        zones_to_process[name] = {'desc': "\n".join(description_parts), 'polygons': []}
                    
                    if isinstance(geom, Polygon):
                        zones_to_process[name]['polygons'].append(geom)
                    elif isinstance(geom, MultiPolygon):
                        zones_to_process[name]['polygons'].extend([p for p in geom])

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error en fragmento de {name}: {e}'))

            # Guardar las zonas fusionadas
            for name, info in zones_to_process.items():
                if not info['polygons']:
                    continue
                
                try:
                    merged_geom = MultiPolygon(info['polygons'])
                    zone, created = LowEmissionZone.objects.update_or_create(
                        name=name,
                        defaults={
                            'description': info['desc'],
                            'geom': merged_geom
                        }
                    )
                    
                    status = "Creada" if created else "Actualizada (Fusionada)"
                    self.stdout.write(self.style.SUCCESS(f'  [{status}] {name} ({len(info["polygons"])} fragmentos)'))
                    total_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error al guardar zona fusionada {name}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Proceso finalizado. Total de zonas procesadas: {total_count}'))
