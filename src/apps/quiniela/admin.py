"""Registro en el admin de los modelos de la quiniela."""

from django.contrib import admin

from .models import (
    Aviso,
    Boleto,
    Equipo,
    EquipoAlias,
    Jornada,
    Noticia,
    PartidoHistorico,
    PartidoJornada,
    Pronostico,
)


class EquipoAliasInline(admin.TabularInline):
    model = EquipoAlias
    extra = 1


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    search_fields = ("nombre", "aliases__texto")
    inlines = (EquipoAliasInline,)


@admin.register(EquipoAlias)
class EquipoAliasAdmin(admin.ModelAdmin):
    list_display = ("texto", "equipo")
    search_fields = ("texto", "equipo__nombre")
    autocomplete_fields = ("equipo",)


@admin.register(PartidoHistorico)
class PartidoHistoricoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "division", "local", "goles_local", "goles_visitante", "visitante", "cuota_tipo")
    list_filter = ("division", "temporada")
    search_fields = ("local__nombre", "visitante__nombre")
    date_hierarchy = "fecha"


class PartidoJornadaInline(admin.TabularInline):
    model = PartidoJornada
    extra = 0
    autocomplete_fields = ("local", "visitante")
    fields = (
        "posicion",
        "local",
        "local_texto",
        "visitante",
        "visitante_texto",
        "fecha",
        "cuota_1",
        "cuota_x",
        "cuota_2",
        "goles_local",
        "goles_visitante",
    )


@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "fecha_cierre")
    list_filter = ("temporada",)
    inlines = (PartidoJornadaInline,)


@admin.register(Pronostico)
class PronosticoAdmin(admin.ModelAdmin):
    list_display = ("partido", "fuente", "p1", "px", "p2", "calculado_at")
    list_filter = ("fuente", "partido__jornada")


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "publicada_at", "feed")
    search_fields = ("titulo",)
    filter_horizontal = ("equipos",)


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ("partido", "equipo", "tipo", "jugador", "resumen")
    list_filter = ("tipo", "partido__jornada")


@admin.register(Boleto)
class BoletoAdmin(admin.ModelAdmin):
    list_display = ("jornada", "configuracion", "coste", "p11", "confirmado_at", "aciertos")

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.confirmado:
            return [f.name for f in self.model._meta.fields]
        return ("confirmado_at", "aciertos", "pleno_acertado")

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.confirmado:
            return False
        return super().has_delete_permission(request, obj)
