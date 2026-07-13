from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import CycloneEvent, PacificCountry


@admin.register(PacificCountry)
class PacificCountryAdmin(GISModelAdmin):
    list_display = (
        "name",
        "code",
        "population",
        "co2_emissions",
        "nd_gain_vulnerability",
        "nd_gain_readiness",
    )
    search_fields = ("name", "code")
    gis_widget_kwargs = {
        "attrs": {
            "default_zoom": 3,
            "default_lon": 180.0,
            "default_lat": -15.0,
        }
    }


@admin.register(CycloneEvent)
class CycloneEventAdmin(GISModelAdmin):
    list_display = ("name", "year", "category", "max_wind_speed", "damage_usd")
    search_fields = ("name", "year")
    gis_widget_kwargs = {
        "attrs": {
            "default_zoom": 3,
            "default_lon": 180.0,
            "default_lat": -15.0,
        }
    }
