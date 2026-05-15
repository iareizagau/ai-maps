from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Route, PointOfInterest
from apps.core.models import Follow

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
def dashboard_view(request):
    """
    Dashboard para ver las rutas guardadas del usuario.
    """
    routes = Route.objects.filter(user=request.user).select_related('user')
    context = {
        "title": "Mis Rutas de Aventura",
        "app_slug": "adventure",
        "routes": routes
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
