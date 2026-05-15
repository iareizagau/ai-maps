from django.contrib.gis.db.models.functions import Area, Azimuth
from django.contrib.gis.geos import Polygon, Point
from .models import Building
import math

def get_buildings_in_bbox(bbox_coords):
    """
    Retorna edificios dentro de un bounding box.
    bbox_coords: [min_lon, min_lat, max_lon, max_lat]
    """
    poly = Polygon.from_bbox(bbox_coords)
    # Seleccionamos edificios que tengan geometría de polígono
    return Building.objects.filter(geom__within=poly).select_related('potential')

def calculate_building_geometry_stats(building):
    """
    Calcula el área y la orientación predominante de un edificio.
    """
    # ST_Area devuelve grados al cuadrado si el SRID es 4326. 
    # Para metros cuadrados necesitamos transformar temporalmente o usar un SRID métrico.
    # Usamos 3857 (Web Mercator) para una aproximación rápida en metros.
    area_m2 = building.geom.transform(3857, clone=True).area
    
    # ST_Azimuth requiere dos puntos. Para un edificio, tomamos el centroide 
    # y el punto más al sur, o una técnica similar para encontrar el eje principal.
    # Por ahora, usamos un valor simplificado o el azimuth de la arista más larga.
    # En este prototipo devolvemos 0 (Sur) por defecto si no se puede calcular.
    azimuth = 0 
    
    return area_m2, azimuth

def rad_to_deg(rad):
    return (rad * 180.0) / math.pi
