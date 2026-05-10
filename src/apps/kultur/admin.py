from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import CulturalEvent, EventFavorite, KulturPrefs


@admin.register(CulturalEvent)
class CulturalEventAdmin(GISModelAdmin):
    list_display = ('title_es', 'start_date', 'venue_name_es', 'municipality_es')
    list_filter = ('start_date', 'municipality_es')
    search_fields = ('title_es', 'title_eu', 'venue_name_es', 'description_es')
    date_hierarchy = 'start_date'


@admin.register(EventFavorite)
class EventFavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'event__title_es', 'event__title_eu')
    autocomplete_fields = ('user', 'event')
    readonly_fields = ('created_at',)


@admin.register(KulturPrefs)
class KulturPrefsAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_municipality', 'updated_at')
    search_fields = ('user__username', 'default_municipality')
    autocomplete_fields = ('user',)
    readonly_fields = ('updated_at',)
