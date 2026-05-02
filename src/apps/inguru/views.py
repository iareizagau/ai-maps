from django.views.generic import TemplateView
from .models import EnvironmentalStation, Measurement
import json

class InguruHomeView(TemplateView):
    template_name = 'inguru/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener estaciones para el mapa inicial
        stations = EnvironmentalStation.objects.all()
        
        stations_json = json.dumps([
            {
                'id': s.id,
                'name': s.name,
                'type': s.station_type,
                'latitude': s.location.y,
                'longitude': s.location.x,
                'municipality': s.municipality,
            }
            for s in stations
        ])
        
        context['stations_json'] = stations_json
        context['station_types'] = EnvironmentalStation.StationType.choices
        
        return context
