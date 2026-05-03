from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import LowEmissionZone

@admin.register(LowEmissionZone)
class LowEmissionZoneAdmin(GISModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 10,
            'default_lon': -2.6716,
            'default_lat': 42.8467,
        }
    }
