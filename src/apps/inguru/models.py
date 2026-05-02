from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils.translation import gettext_lazy as _

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class EnvironmentalStation(BaseModel):
    """
    Estación de medición (Aire, Agua, Polen, etc.)
    """
    class StationType(models.TextChoices):
        AIR = 'AIR', _('Calidad del Aire')
        POLLEN = 'POLLEN', _('Polen')
        WATER_MASS = 'WATER_MASS', _('Calidad de Aguas (URA)')
        DRINKING_WATER = 'DRINKING_WATER', _('Aguas de Consumo')
        METEO = 'METEO', _('Meteorología (Euskalmet)')

    name = models.CharField(max_length=200)
    external_id = models.CharField(max_length=100, unique=True, help_text="ID en el sistema de Open Data Euskadi")
    station_type = models.CharField(max_length=20, choices=StationType.choices)
    location = gis_models.PointField(srid=4326)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Información adicional específica de la estación")

    def __str__(self):
        return f"[{self.station_type}] {self.name}"

    class Meta:
        indexes = [
            models.Index(fields=['station_type', 'external_id']),
        ]

class Measurement(BaseModel):
    """
    Medición puntual en una estación
    """
    station = models.ForeignKey(EnvironmentalStation, on_delete=models.CASCADE, related_name='measurements')
    timestamp = models.DateTimeField()
    values = models.JSONField(help_text="Valores medidos (ej: {'NO2': 20, 'O3': 40})")
    eco_score = models.IntegerField(null=True, blank=True, help_text="Índice unificado calculado (0-100)")

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['station', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.station.name} @ {self.timestamp}"
