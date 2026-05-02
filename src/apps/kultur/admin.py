from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import CulturalEvent

@admin.register(CulturalEvent)
class CulturalEventAdmin(GISModelAdmin):
    list_display = ('title_es', 'start_date', 'venue_name_es', 'municipality_es')
    list_filter = ('start_date', 'municipality_es')
    search_fields = ('title_es', 'title_eu', 'venue_name_es', 'description_es')
    date_hierarchy = 'start_date'
