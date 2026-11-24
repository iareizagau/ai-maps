from django.contrib import admin

from .models import MapEntry


@admin.register(MapEntry)
class MapEntryAdmin(admin.ModelAdmin):
    list_display = ("day", "date", "category_name", "title", "library", "status")
    list_filter = ("status", "library", "basemap")
    search_fields = ("title", "category_name", "category_slug")
    ordering = ("day",)
