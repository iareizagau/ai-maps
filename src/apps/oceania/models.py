from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

class PacificCountry(models.Model):
    """Naciones insulares del Pacífico y sus métricas climáticas."""
    name = models.CharField(_("Nombre del País"), max_length=100)
    code = models.CharField(_("Código ISO"), max_length=3, unique=True)
    population = models.IntegerField(_("Población"), default=0)
    co2_emissions = models.FloatField(_("Emisiones de CO2 per cápita (toneladas)"), default=0.0)
    nd_gain_vulnerability = models.FloatField(_("Índice de Vulnerabilidad ND-GAIN"), default=0.0)
    nd_gain_readiness = models.FloatField(_("Índice de Preparación ND-GAIN"), default=0.0)
    geom = models.MultiPolygonField(_("Geometría"), srid=4326, blank=True, null=True)
    capital_coords = models.PointField(_("Coordenadas de la Capital"), srid=4326, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("País del Pacífico")
        verbose_name_plural = _("Países del Pacífico")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

class CycloneEvent(models.Model):
    """Registro histórico de Ciclones Tropicales devastadores."""
    name = models.CharField(_("Nombre del Ciclón"), max_length=50)
    year = models.IntegerField(_("Año"))
    category = models.IntegerField(_("Categoría (Saffir-Simpson)"), default=1)
    max_wind_speed = models.FloatField(_("Velocidad de Viento Máx (km/h)"), default=0.0)
    damage_usd = models.DecimalField(_("Daños Estimados (USD)"), max_digits=15, decimal_places=2, null=True, blank=True)
    route_geom = models.LineStringField(_("Trayectoria del Ciclón"), srid=4326)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Ciclón")
        verbose_name_plural = _("Ciclones")
        ordering = ['-year', 'name']

    def __str__(self):
        return f"TC {self.name} ({self.year}) - Cat {self.category}"
