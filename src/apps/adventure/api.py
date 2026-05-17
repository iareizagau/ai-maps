from ninja import Router, Schema, Form, File
from ninja.files import UploadedFile
from typing import List, Dict, Any, Optional
import json
from .selectors import get_adventure_route
from django.contrib.gis.geos import Polygon, LineString, MultiLineString, Point
from .models import Fountain, Route, IntelDrop, TrailEdge, ExplorationRecord
from .services import discover_sectors_from_route
from django.db.models import Count
from django.contrib.auth import get_user_model
from apps.core.models import Follow
import gpxpy
import requests

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
        
        # Marcamos cada feature con el Ã­ndice del segmento al que pertenece
        for feature in segment["features"]:
            feature["properties"]["segment_index"] = i
        
        full_route["features"].extend(segment["features"])
        full_route["metadata"]["total_cost"] += segment["metadata"]["total_cost"]
        
        # Opcional: PodrÃ­amos aquÃ­ acumular estadÃ­sticas de superficie si ampliamos el selector
    
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
        return {"error": "AutenticaciÃ³n requerida. Por favor, inicia sesiÃ³n para guardar rutas."}
        
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
            return {"error": "La ruta no tiene geometrÃ­a vÃ¡lida."}
            
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
        
        # Fog of War: Desbloquear sectores
        discovery = discover_sectors_from_route(route)
        
        return {
            "success": True, 
            "id": route.id, 
            "message": "Ruta guardada correctamente.",
            "discovery": discovery
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/routes/forensic")
def save_forensic_route(
    request, 
    name: str = Form(...), 
    description: str = Form(""), 
    profile: str = Form("hiking"),
    geojson: str = Form(...),
    distance_meters: float = Form(0),
    photo_metadata: str = Form(...), # JSON string mapping filename -> {lat, lng, time}
    photos: List[UploadedFile] = File(...)
):
    if not request.user.is_authenticated:
        return {"error": "Autenticación requerida"}
        
    try:
        # 1. Parsear Geometría
        geo_data = json.loads(geojson)
        coords = geo_data['coordinates']
        line = LineString(coords)
        geom = MultiLineString(line)
        
        # 2. Crear la Ruta
        route = Route.objects.create(
            user=request.user,
            name=name,
            description=description,
            profile=profile,
            waypoints=coords,
            geom=geom,
            distance_meters=distance_meters,
            elevation_gain=0,
            elevation_loss=0
        )
        
        # 3. Procesar Fotos e IntelDrops
        metadata = json.loads(photo_metadata)
        for photo_file in photos:
            meta = metadata.get(photo_file.name)
            if meta:
                IntelDrop.objects.create(
                    user=request.user,
                    route=route,
                    intel_type='photo_epic',
                    location=Point(float(meta['lng']), float(meta['lat'])),
                    description=f"Evidencia de la expedición: {name}",
                    image=photo_file
                )
        
        # Fog of War: Desbloquear sectores
        discovery = discover_sectors_from_route(route)
        
        return {
            "success": True, 
            "id": route.id, 
            "message": "Expedición reconstruida con éxito.",
            "discovery": discovery
        }
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": str(e)}

@router.post("/routes/gpx")
def upload_gpx(request, file: UploadedFile = File(...)):
    """Sube y procesa un archivo GPX para convertirlo en una Ruta"""
    if not request.user.is_authenticated:
        return {"error": "AutenticaciÃ³n requerida"}
    
    try:
        # Leemos el contenido del archivo
        gpx_data = file.read().decode('utf-8')
        gpx = gpxpy.parse(gpx_data)
        
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append((point.longitude, point.latitude))
                    
        if not points:
            return {"error": "El archivo GPX no contiene tracks o puntos vÃ¡lidos."}
            
        # Crear la geometrÃ­a espacial
        line = LineString(points)
        geom = MultiLineString(line)
        
        # Calcular estadÃ­sticas bÃ¡sicas
        distance_2d = gpx.length_2d()
        uphill, downhill = gpx.get_uphill_downhill()
        
        # El nombre del GPX, o el nombre del archivo si no tiene
        name = gpx.name if gpx.name else file.name.replace('.gpx', '')
        
        # Reverse Geocoding via Nominatim
        city, province = None, None
        if points:
            try:
                first_point = points[0]
                headers = {'User-Agent': 'AdventureMapsApp/1.0'}
                url = f"https://nominatim.openstreetmap.org/reverse?lat={first_point[1]}&lon={first_point[0]}&format=json"
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    address = data.get('address', {})
                    city = address.get('city') or address.get('town') or address.get('village') or address.get('municipality')
                    province = address.get('province') or address.get('state')
            except Exception:
                pass

        # Guardar en base de datos
        route = Route.objects.create(
            user=request.user,
            name=name,
            description=gpx.description or "",
            is_public=False, # Privada por defecto para que el usuario la revise
            profile="bikepacking",
            # Guardamos un array simplificado de waypoints (mÃ¡x ~50 para no reventar el frontend en ediciÃ³n)
            waypoints=[[p[0], p[1]] for p in points[0::max(1, len(points)//50)]],
            geom=geom,
            distance_meters=distance_2d,
            elevation_gain=uphill or 0,
            elevation_loss=downhill or 0,
            surface_stats={"unknown": 100}, # Placeholder hasta que crucemos con TrailEdge
            location_city=city,
            location_province=province
        )
        
        # 3. CÃ¡lculo de Superficies (ST_Intersects usando buffer / dwithin)
        edges = TrailEdge.objects.filter(geom__dwithin=(geom, 0.0002))
        
        stats = {}
        total_edges = edges.count()
        if total_edges > 0:
            surface_counts = edges.values('surface').annotate(count=Count('id'))
            for item in surface_counts:
                surface = item['surface'] or 'unknown'
                pct = (item['count'] / total_edges) * 100
                stats[surface] = stats.get(surface, 0) + pct
            route.surface_stats = {k: round(v, 2) for k, v in stats.items()}
            route.save(update_fields=['surface_stats'])

        # Buscar fuentes cercanas (aprox 200m)
        fountains_count = Fountain.objects.filter(location__dwithin=(geom, 0.0018)).count()

        # Fog of War: Desbloquear sectores
        discovery = discover_sectors_from_route(route)

        return {
            "success": True, 
            "id": route.id, 
            "message": f"GPX procesado y guardado con éxito. ¡Hay {fountains_count} fuentes cerca!",
            "distance_km": round(distance_2d / 1000, 2),
            "fountains": fountains_count,
            "discovery": discovery
        }
        
    except Exception as e:
        return {"error": f"Error procesando GPX: {str(e)}"}

@router.get("/exploration/sectors")
def get_user_exploration(request):
    """Retorna los sectores descubiertos por el usuario en formato GeoJSON"""
    if not request.user.is_authenticated:
        return {"error": "No autenticado"}
    
    sectors = ExplorationRecord.objects.filter(user=request.user)
    features = []
    for s in sectors:
        features.append({
            "type": "Feature",
            "geometry": json.loads(s.geom.geojson),
            "properties": {
                "is_pioneer": s.is_pioneer,
                "discovered_at": s.discovered_at.isoformat()
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }

@router.get("/exploration/intel")
def get_user_intel(request):
    """Retorna todos los Intel Drops del usuario para el Mando de Operaciones"""
    if not request.user.is_authenticated:
        return {"error": "No autenticado"}
    
    drops = IntelDrop.objects.filter(user=request.user)
    features = []
    for d in drops:
        features.append({
            "type": "Feature",
            "geometry": json.loads(d.location.geojson),
            "properties": {
                "id": d.id,
                "type": d.intel_type,
                "type_display": d.get_intel_type_display(),
                "description": d.description,
                "image_url": d.image.url if d.image else None,
                "created_at": d.created_at.isoformat()
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.get("/routes/{route_id}")
def get_route_by_id(request, route_id: int):
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

@router.delete("/routes/{route_id}")
def delete_route(request, route_id: int):
    if not request.user.is_authenticated:
        return {"error": "AutenticaciÃ³n requerida.", "success": False}
    try:
        route = Route.objects.get(id=route_id, user=request.user)
        route.delete()
        return {"success": True, "message": "Ruta eliminada correctamente."}
    except Route.DoesNotExist:
        return {"error": "Ruta no encontrada o no tienes permisos.", "success": False}

@router.post("/users/{user_id}/follow")
def toggle_follow(request, user_id: int):
    if not request.user.is_authenticated:
        return {"error": "AutenticaciÃ³n requerida."}
        
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
    """Crea un nuevo Reporte TÃ¡ctico (Intel Drop)"""
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
        
