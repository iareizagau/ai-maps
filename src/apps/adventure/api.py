from ninja import Router, Schema, Form, File
from ninja.files import UploadedFile
from typing import List, Dict, Any, Optional
from .selectors import get_adventure_route
from django.contrib.gis.geos import Polygon, LineString, MultiLineString, Point
from .models import Fountain, Route, IntelDrop
from django.contrib.auth import get_user_model
from apps.core.models import Follow


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

class RouteCreateSchema(Schema):
    name: str
    description: str = ""
    is_public: bool = True
    profile: str
    waypoints: List[List[float]]
    features: List[Dict[str, Any]]
    distance_meters: float
    elevation_gain: float
    elevation_loss: float
    surface_stats: Dict[str, float]

@router.post("/routes")
def save_route(request, data: RouteCreateSchema):
    if not request.user.is_authenticated:
        return {"error": "Autenticación requerida. Por favor, inicia sesión para guardar rutas."}
        
    try:
        lines = []
        for f in data.features:
            coords = f['geometry']['coordinates']
            if f['geometry']['type'] == 'LineString':
                lines.append(LineString(coords))
            elif f['geometry']['type'] == 'MultiLineString':
                for c in coords:
                    lines.append(LineString(c))
                    
        if not lines:
            return {"error": "La ruta no tiene geometría válida."}
            
        geom = MultiLineString(*lines)
        
        route = Route.objects.create(
            user=request.user,
            name=data.name,
            description=data.description,
            is_public=data.is_public,
            profile=data.profile,
            waypoints=data.waypoints,
            geom=geom,
            distance_meters=data.distance_meters,
            elevation_gain=data.elevation_gain,
            elevation_loss=data.elevation_loss,
            surface_stats=data.surface_stats
        )
        return {"success": True, "id": route.id, "message": "Ruta guardada correctamente."}
    except Exception as e:
        return {"error": str(e)}

@router.get("/routes/{route_id}")
def get_route(request, route_id: int):
    try:
        route = Route.objects.get(id=route_id)
        return {
            "success": True,
            "id": route.id,
            "name": route.name,
            "waypoints": route.waypoints,
            "profile": route.profile
        }
    except Route.DoesNotExist:
        return {"error": "Ruta no encontrada."}

@router.post("/users/{user_id}/follow")
def toggle_follow(request, user_id: int):
    if not request.user.is_authenticated:
        return {"error": "Autenticación requerida."}
        
    User = get_user_model()
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {"error": "Usuario no encontrado."}
        
    if request.user == target_user:
        return {"error": "No puedes seguirte a ti mismo."}
        
    # Toggle logic
    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        followed=target_user,
        app_context='adventure'
    )
    
    if not created:
        follow.delete()
        is_following = False
    else:
        is_following = True
        
    return {"success": True, "is_following": is_following}

@router.post("/intel")
def create_intel(
    request,
    intel_type: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    description: str = Form(""),
    route_id: Optional[int] = Form(None),
    image: UploadedFile = File(None)
):
    """Crea un nuevo Reporte Táctico (Intel Drop)"""
    if not request.user.is_authenticated:
        return {"success": False, "error": "No autenticado"}
        
    point = Point(lng, lat, srid=4326)
    route = Route.objects.filter(id=route_id).first() if route_id else None
    
    drop = IntelDrop.objects.create(
        user=request.user,
        route=route,
        intel_type=intel_type,
        location=point,
        description=description,
        image=image
    )
    return {"success": True, "id": drop.id}

@router.get("/intel/route/{route_id}")
def get_route_intel(request, route_id: int):
    """Obtiene los Intel Drops asociados a una ruta (y los cercanos a la misma)"""
    route = Route.objects.filter(id=route_id).first()
    if not route:
        return {"success": False, "error": "Ruta no encontrada"}
        
    # Get direct intel drops for the route
    direct_intel = IntelDrop.objects.filter(route=route)
    nearby_intel = IntelDrop.objects.filter(location__dwithin=(route.geom, 0.0018)).exclude(route=route)
    
    intel_list = []
    for drop in (list(direct_intel) + list(nearby_intel)):
        intel_list.append({
            "id": drop.id,
            "type": drop.intel_type,
            "type_display": drop.get_intel_type_display(),
            "description": drop.description,
            "user": drop.user.username,
            "lng": drop.location.x,
            "lat": drop.location.y,
            "is_fresh": drop.is_fresh,
            "image_url": drop.image.url if drop.image else None,
            "created_at": drop.created_at.isoformat(),
            "is_direct": drop.route_id == route.id
        })
        
    return {"success": True, "intel": intel_list}
