from django.contrib import admin
from django.contrib.gis import admin as gis_admin
from .models import Club, Outing, Crag, Sector, Route, Topo

@admin.register(Club)
class ClubAdmin(gis_admin.GISModelAdmin):
    list_display = ('name', 'website')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Outing)
class OutingAdmin(gis_admin.GISModelAdmin):
    list_display = ('title', 'club', 'date', 'difficulty')
    list_filter = ('club', 'date', 'difficulty')
    search_fields = ('title', 'description')

class SectorInline(admin.TabularInline):
    model = Sector
    extra = 1

@admin.register(Crag)
class CragAdmin(gis_admin.GISModelAdmin):
    list_display = ('name_es', 'name_eu', 'location')
    search_fields = ('name_es', 'name_eu')
    prepopulated_fields = {'slug': ('name_es',)}
    inlines = [SectorInline]

class RouteInline(admin.TabularInline):
    model = Route
    extra = 5

@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'crag', 'orientation')
    list_filter = ('crag', 'orientation')
    inlines = [RouteInline]

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('name_es', 'name_eu', 'sector', 'grade', 'is_bolted')
    list_filter = ('sector__crag', 'grade', 'is_bolted')
    search_fields = ('name_es', 'name_eu', 'description_es', 'description_eu')

@admin.register(Topo)
class TopoAdmin(admin.ModelAdmin):
    list_display = ('title', 'sector', 'outing')
