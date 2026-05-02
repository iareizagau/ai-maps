from django.shortcuts import render
from django.http import JsonResponse
from django.core.serializers import serialize
from .models import CulturalEvent

def map_view(request):
    """
    Main view that renders the Leaflet map.
    """
    return render(request, 'kultur/map.html')

def events_geojson(request):
    """
    Returns CulturalEvents as GeoJSON.
    """
    # Filter out events without location
    events = CulturalEvent.objects.exclude(location__isnull=True)
    
    # We could add bounding box filtering here if requested
    
    # Using Django's built-in GeoJSON serializer
    geojson = serialize(
        'geojson', 
        events,
        geometry_field='location',
        fields=(
            'title_es', 'title_eu', 
            'description_es', 'description_eu', 
            'venue_name_es', 'venue_name_eu', 
            'municipality_es', 'municipality_eu',
            'opening_hours_es', 'opening_hours_eu',
            'price_es', 'price_eu',
            'start_date', 'image_url', 
            'url_es', 'url_eu', 
            'purchase_url_es', 'purchase_url_eu',
            'event_type_es', 'event_type_eu'
        )
    )
    
    return JsonResponse(geojson, safe=False)
