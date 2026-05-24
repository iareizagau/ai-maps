from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Route, PointOfInterest, TrailEdge
from apps.core.models import Follow
import json

def map_view(request):
    """
    Vista principal del planificador de rutas de aventura.
    Permite cargar una ruta existente si se pasa ?edit=ID
    """
    edit_id = request.GET.get('edit')
    
    context = {
        "title": "Adventure Lab - Planificador de Rutas",
        "app_slug": "adventure",
        "edit_route_id": edit_id
    }
    return render(request, "adventure/map.html", context)

@login_required
def vanlife_planner_view(request):
    """
    Vista del Planificador Táctico de Viajes en Furgoneta Camper (Vanlife TSP Planner).
    """
    context = {
        "title": "Vanlife Planner - Planificador de Expedición Camper",
        "app_slug": "adventure",
    }
    return render(request, "adventure/vanlife_planner.html", context)

@login_required
def dashboard_view(request):
    """
    Dashboard para ver las rutas guardadas del usuario.
    """
    import json
    routes = Route.objects.filter(user=request.user).select_related('user')
    
    routes_list = []
    for r in routes:
        # Extraer porcentajes de superficie de forma segura
        surface = r.surface_percentages
        routes_list.append({
            "id": r.id,
            "name": r.name,
            "description": r.description or "",
            "profile": r.profile,
            "distance": float(r.distance_km),
            "gain": float(r.elevation_gain or 0),
            "loss": float(r.elevation_loss or 0),
            "asphalt": float(surface.get("asphalt", 0)),
            "dirt": float(surface.get("dirt", 0)),
            "difficulty": r.difficulty_badge,
            "isPublic": bool(r.is_public),
            "location": f"{r.location_city or ''}, {r.location_province or ''}".strip(", "),
            "geojson": json.loads(r.geom_simplified_geojson) if r.geom_simplified_geojson else {}
        })
        
    context = {
        "title": "Mis Rutas de Aventura",
        "app_slug": "adventure",
        "routes": routes,
        "routes_json": json.dumps(routes_list)
    }
    return render(request, "adventure/dashboard.html", context)

@login_required
def explore_view(request):
    """
    Feed social para descubrir rutas públicas de otros aventureros.
    """
    # Rutas públicas recientes
    routes = Route.objects.filter(is_public=True).select_related('user').order_by('-created_at')[:50]
    
    # Obtener IDs de usuarios a los que ya sigue el request.user en el contexto de adventure
    
    following_ids = Follow.objects.filter(
        follower=request.user, 
        app_context='adventure'
    ).values_list('followed_id', flat=True)

    context = {
        "title": "Explorar Aventuras",
        "app_slug": "adventure",
        "routes": routes,
        "following_ids": list(following_ids)
    }
    return render(request, "adventure/explore.html", context)

@login_required
def route_detail_view(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    
    # PostGIS Magic: ST_DWithin para buscar POIs a ~200 metros de la ruta
    # SRID 4326 usa grados. 1 grado = 111.32 km. 200m = 0.0018 grados
    pois = PointOfInterest.objects.filter(location__dwithin=(route.geom, 0.0018))
    
    # Contabilizar tipos de POI para el resumen
    poi_counts = {}
    for p in pois:
        label = p.get_poi_type_display()
        poi_counts[label] = poi_counts.get(label, 0) + 1
        
    context = {
        "title": route.name,
        "app_slug": "adventure",
        "route": route,
        "route_geojson": route.geom.geojson,
        "pois": pois,
        "poi_counts": poi_counts
    }
    return render(request, "adventure/route_detail.html", context)

@login_required
def scout_view(request):
    context = {
        "title": "Scouting Mode",
        "app_slug": "adventure",
    }
    return render(request, "adventure/scout.html", context)


@login_required
def follow_view(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    
    # Generate terrain FeatureCollection for data-driven styling
    edges = TrailEdge.objects.filter(geom__dwithin=(route.geom, 0.0001))
    terrain_features = []
    for edge in edges:
        terrain_features.append({
            "type": "Feature",
            "geometry": json.loads(edge.geom.geojson),
            "properties": {
                "surface": edge.surface or "unknown",
                "highway": edge.highway or "unknown"
            }
        })
        
    # Fallback: Si la ruta se importó de GPX o está en una zona sin datos de TrailEdge,
    # inyectamos la geometría original para que la línea no desaparezca.
    if not terrain_features:
        terrain_features.append({
            "type": "Feature",
            "geometry": json.loads(route.geom.geojson),
            "properties": {
                "surface": "unknown",
                "highway": "unknown"
            }
        })
        
    terrain_geojson = {
        "type": "FeatureCollection",
        "features": terrain_features
    }

    context = {
        "title": f"Siguiendo: {route.name}",
        "app_slug": "adventure",
        "route": route,
        "route_geojson": route.geom.geojson,
        "terrain_geojson": json.dumps(terrain_geojson),
    }
    return render(request, "adventure/follow.html", context)


@login_required
def photo_route_view(request):
    context = {
        "title": "Ruta Forense EXIF",
        "app_slug": "adventure",
    }
    return render(request, "adventure/photo_route.html", context)


@login_required
def exploration_view(request):
    """
    Vista inmersiva a pantalla completa del Mando de Operaciones (Fog of War).
    """
    context = {
        "title": "Mando de Operaciones - Exploración Global",
        "app_slug": "adventure",
    }
    return render(request, "adventure/exploration.html", context)
