from django.contrib.gis.geos import Polygon, Point, LineString
from .models import ExplorationRecord
import math

def discover_sectors_from_route(route):
    """
    Analiza la ruta e INTERPOLA puntos cada ~50m para asegurar que no haya saltos
    en el descubrimiento de sectores.
    """
    user = route.user
    cell_size = 0.001 # ~100m
    new_sectors_count = 0
    pioneer_count = 0
    seen_keys = set()

    # Convertimos la ruta en una lista de líneas para procesarlas
    lines = []
    if route.geom.geom_type == 'MultiLineString':
        lines = list(route.geom)
    else:
        lines = [route.geom]

    for line in lines:
        # Interpolación: Generamos puntos a lo largo de la línea cada 50 metros
        # para asegurar que tocamos todos los sectores por los que pasa la ruta.
        length = line.length # En grados, aproximado
        # Estimamos pasos: 0.0005 grados es aprox 50m
        steps = max(2, int(length / 0.0005))
        
        for i in range(steps + 1):
            # Obtenemos el punto interpolado
            pt = line.interpolate_normalized(i / steps)
            lng, lat = pt.x, pt.y
            
            lat_idx = math.floor(lat / cell_size)
            lng_idx = math.floor(lng / cell_size)
            key = f"{lat_idx}:{lng_idx}"

            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Registro de exploración
            record, created = ExplorationRecord.objects.get_or_create(
                user=user,
                sector_key=key,
                defaults={
                    'geom': Polygon.from_bbox((
                        lng_idx * cell_size, 
                        lat_idx * cell_size, 
                        (lng_idx + 1) * cell_size, 
                        (lat_idx + 1) * cell_size
                    ))
                }
            )

            if created:
                new_sectors_count += 1
                if not ExplorationRecord.objects.filter(sector_key=key).exclude(id=record.id).exists():
                    record.is_pioneer = True
                    record.save(update_fields=['is_pioneer'])
                    pioneer_count += 1

    return {
        "new_sectors": new_sectors_count,
        "pioneer_sectors": pioneer_count
    }
