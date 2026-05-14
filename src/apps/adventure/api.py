from ninja import Router
from typing import List
from .selectors import get_adventure_route
from django.contrib.gis.geos import Polygon
from .models import Fountain

router = Router(tags=["adventure"])

@router.get("/fountains")
def get_fountains(request, bbox: str):
    """Obtiene fuentes dentro de un bounding box: min_lon,min_lat,max_lon,max_lat"""
    try:
        coords = [float(x) for x in bbox.split(',')]
        poly = Polygon.from_bbox(coords)
        fountains = Fountain.objects.filter(location__within=poly)[:100] # Limitamos a 100 por rendimiento
        
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [f.location.x, f.location.y]
                    },
                    "properties": {
                        "id": f.id,
                        "name": f.name or "Fuente",
                        "description": f.description
                    }
                } for f in fountains
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/route")
def get_route(request, coords: str, profile: str = "bikepacking"):
    """
    Calcula una ruta multi-punto.
    coords: string en formato "lon,lat;lon,lat;lon,lat"
    """
    points = [list(map(float, p.split(','))) for p in coords.split(';')]
    if len(points) < 2:
        return {"error": "Se necesitan al menos 2 puntos."}

    full_route = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "total_cost": 0,
            "surface_stats": {}
        }
    }

    # Calculamos la ruta por tramos (segmentos)
    for i in range(len(points) - 1):
        segment = get_adventure_route(points[i], points[i+1], profile=profile)
        if "error" in segment:
            continue
        
        # Marcamos cada feature con el índice del segmento al que pertenece
        for feature in segment["features"]:
            feature["properties"]["segment_index"] = i
        
        full_route["features"].extend(segment["features"])
        full_route["metadata"]["total_cost"] += segment["metadata"]["total_cost"]
        
        # Opcional: Podríamos aquí acumular estadísticas de superficie si ampliamos el selector
    
    return full_route
