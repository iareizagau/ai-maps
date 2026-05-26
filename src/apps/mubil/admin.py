"""Admin registrations for mubil. PROPUESTA.md §3."""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import (
    Vehicle,
    FuelStation,
    ChargingStation,
    EnergyPricePVPC,
    EVRegistration,
    MobilityTrip,
    MobilityDocument,
    DemandHex,
    EVRoutePlan,
)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('make', 'model', 'year', 'propulsion', 'battery_kwh', 'range_wltp_km', 'price_eur')
    list_filter = ('propulsion', 'year')
    search_fields = ('make', 'model')


@admin.register(FuelStation)
class FuelStationAdmin(GISModelAdmin):
    list_display = ('brand', 'municipality_name', 'postal_code', 'sale_type', 'updated_at')
    list_filter = ('brand', 'sale_type')
    search_fields = ('brand', 'municipality_name', 'address')
    readonly_fields = ('updated_at', 'last_seen_at')


@admin.register(ChargingStation)
class ChargingStationAdmin(GISModelAdmin):
    list_display = ('operator', 'power_kw', 'source', 'address', 'last_seen_at')
    list_filter = ('source', 'operator')
    search_fields = ('operator', 'address', 'external_id')
    readonly_fields = ('created_at', 'updated_at', 'last_seen_at')


@admin.register(EnergyPricePVPC)
class EnergyPricePVPCAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'tariff', 'price_eur_mwh')
    list_filter = ('tariff',)
    date_hierarchy = 'timestamp'


@admin.register(EVRegistration)
class EVRegistrationAdmin(admin.ModelAdmin):
    list_display = ('municipality_name', 'year', 'month', 'propulsion', 'count')
    list_filter = ('propulsion', 'year')
    search_fields = ('municipality_name', 'municipality_naia')


@admin.register(MobilityTrip)
class MobilityTripAdmin(admin.ModelAdmin):
    list_display = ('date', 'hour', 'origin_naia', 'dest_naia', 'mode', 'motive', 'n_trips')
    list_filter = ('mode', 'motive')
    date_hierarchy = 'date'


@admin.register(MobilityDocument)
class MobilityDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_type', 'municipality_naia', 'ingested_at')
    list_filter = ('source_type',)
    search_fields = ('title', 'content')
    readonly_fields = ('ingested_at', 'updated_at', 'content_hash')


@admin.register(DemandHex)
class DemandHexAdmin(GISModelAdmin):
    list_display = ('h3_index', 'municipality_naia', 'score_now', 'score_y3', 'score_y5', 'computed_at')
    list_filter = ('municipality_naia',)
    readonly_fields = ('computed_at',)


@admin.register(EVRoutePlan)
class EVRoutePlanAdmin(GISModelAdmin):
    list_display = ('vehicle', 'distance_km', 'duration_min', 'energy_kwh', 'estimated_cost_eur', 'computed_at')
    readonly_fields = ('computed_at',)
