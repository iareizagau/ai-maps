import json
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.generic import ListView, DetailView
from django.contrib.gis.geos import Point
from django.conf import settings
from .models import Crag, Outing, Route
from django.db.models import Count

def home(request):
    """Home view for Gailur"""
    recent_outings = Outing.objects.all()
    featured_crags = Crag.objects.all()
    
    # Fetch all crags with valid coordinates for the map and annotate total routes
    target_point = Point(0, 0)
    all_crags = Crag.objects.exclude(location=target_point).annotate(routes_count=Count('sectors__routes'))
    
    # Serialize ALL valid crags for the map
    crags_data = []
    for crag in all_crags:
        crags_data.append({
            'id': crag.id,
            'name': crag.name,
            'lat': crag.location.y,
            'lon': crag.location.x,
            'description': crag.description[:100] + '...',
            'routes_count': crag.routes_count,
            'url': reverse('gailur:crag_detail', args=[crag.id])
        })
    
    # Fetch recent routes for the gallery
    recent_routes = Route.objects.all().order_by('-created_at')
    
    return render(request, 'gailur/home.html', {
        'recent_outings': recent_outings,
        'featured_crags': featured_crags,
        'recent_routes': recent_routes,
        'crags_json': json.dumps(crags_data),
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    })

class RouteDetailView(DetailView):
    model = Route
    template_name = 'gailur/route_detail.html'
    context_object_name = 'route'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class CragDetailView(DetailView):
    model = Crag
    template_name = 'gailur/crag_detail.html'
    context_object_name = 'crag'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch sectors and their routes
        context['sectors'] = self.object.sectors.all().prefetch_related('routes')
        return context
