from django.contrib import admin

from .models import POI, AemetStation, Promocion, PromocionClima, SolarPotential


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


@admin.register(SolarPotential)
class SolarPotentialAdmin(admin.ModelAdmin):
    list_display = ("promocion", "kwh_kwp_year", "irradiation_year", "updated_at")
    search_fields = ("promocion__nombre", "promocion__slug")
    autocomplete_fields = ("promocion",)
    readonly_fields = (
        "promocion",
        "kwh_kwp_year",
        "monthly_json",
        "irradiation_year",
        "tilt_deg",
        "azimuth_deg",
        "system_loss_pct",
        "pvgis_version",
        "raw_json",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(AemetStation)
class AemetStationAdmin(admin.ModelAdmin):
    list_display = ("idema", "nombre", "provincia", "altitud_m", "updated_at")
    list_filter = ("provincia",)
    search_fields = ("idema", "nombre")
    readonly_fields = ("idema", "nombre", "provincia", "altitud_m", "location", "raw_json", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(PromocionClima)
class PromocionClimaAdmin(admin.ModelAdmin):
    list_display = ("promocion", "station", "distance_m", "period_label", "updated_at")
    search_fields = ("promocion__nombre", "promocion__slug", "station__nombre")
    autocomplete_fields = ("promocion", "station")
    readonly_fields = (
        "promocion",
        "station",
        "distance_m",
        "temp_mean",
        "precipitation",
        "sun_hours",
        "period_label",
        "raw_json",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
