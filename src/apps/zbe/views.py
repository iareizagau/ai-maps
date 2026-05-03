import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from .models import LowEmissionZone

@ensure_csrf_cookie
def home(request):
    zones = LowEmissionZone.objects.all()
    # Construct a simple GeoJSON FeatureCollection
    features = []
    for zone in zones:
        if zone.geom:
            feature = {
                "type": "Feature",
                "properties": {
                    "id": zone.id,
                    "name": zone.name,
                    "description": zone.description
                },
                "geometry": json.loads(zone.geom.geojson)
            }
            features.append(feature)
            
    feature_collection = {
        "type": "FeatureCollection",
        "features": features
    }
    
    context = {
        'zones_geojson': feature_collection
    }
    return render(request, 'zbe/home.html', context)

def save_zones(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            features = data.get('features', [])
            
            # Clear existing to avoid duplicates on every save
            LowEmissionZone.objects.all().delete()
            
            saved_count = 0
            for i, feature in enumerate(features):
                geom_str = json.dumps(feature['geometry'])
                geom = GEOSGeometry(geom_str)
                
                # Convert Polygon to MultiPolygon if needed
                if geom.geom_type == 'Polygon':
                    geom = MultiPolygon(geom)
                
                name = feature.get('properties', {}).get('name', f'Zona {i+1}')
                
                LowEmissionZone.objects.create(
                    name=name,
                    geom=geom
                )
                saved_count += 1
                
            return JsonResponse({'status': 'success', 'saved': saved_count})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
