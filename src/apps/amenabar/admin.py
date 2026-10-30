from django.contrib import admin

from .models import POI, Promocion


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad", "provincia", "estado", "porcentaje_vendido")
    list_filter = ("estado", "provincia")
    search_fields = ("nombre", "ciudad")
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(POI)
class POIAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "subtipo", "promocion")
    list_filter = ("categoria",)
    search_fields = ("nombre", "subtipo")
    autocomplete_fields = ("promocion",)
