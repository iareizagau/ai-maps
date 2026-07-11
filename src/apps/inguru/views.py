from django.views.generic import TemplateView
from .models import EnvironmentalStation
import json

class InguruHomeView(TemplateView):
    template_name = 'inguru/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Prefetch related measurements ordered by timestamp to efficiently get the latest one
        stations = EnvironmentalStation.objects.prefetch_related('measurements')
        
        stations_data = []
        for s in stations:
            latest_m = s.measurements.first()
            measurement_data = None
            if latest_m:
                measurement_data = {
                    'timestamp': latest_m.timestamp.isoformat(),
                    'values': latest_m.values,
                    'eco_score': latest_m.eco_score,
                }
            
            stations_data.append({
                'id': s.id,
                'name': s.name,
                'type': s.station_type,
                'latitude': s.location.y,
                'longitude': s.location.x,
                'municipality': s.municipality,
                'province': s.province,
                'latest_measurement': measurement_data
            })
            
        context['stations_json'] = json.dumps(stations_data)
        context['station_types'] = EnvironmentalStation.StationType.choices
        
        return context

