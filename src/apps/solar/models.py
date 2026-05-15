from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _

class Building(models.Model):
    """
    Representa un edificio de OpenStreetMap para el cálculo de potencial solar.
    """
    osm_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    
    # Geometría del edificio (polígono)
    geom = models.PolygonField(srid=4326)
    
    # Atributos de OSM relevantes
    height = models.FloatField(null=True, blank=True)
    levels = models.IntegerField(null=True, blank=True)
    building_type = models.CharField(max_length=100, blank=True) # apartments, house, commercial...
    
    # Metadatos calculados
    roof_area = models.FloatField(null=True, blank=True, help_text=_("Área útil proyectada del tejado en m2"))
    azimuth = models.FloatField(null=True, blank=True, help_text=_("Orientación predominante (0=Sur, 90=Oeste, -90=Este)"))

    class Meta:
        db_table = 'solar_buildings'
        verbose_name = _('Edificio')
        verbose_name_plural = _('Edificios')

    def __str__(self):
        return f"{self.name or 'Edificio'} ({self.osm_id})"

class SolarPotential(models.Model):
    """
    Resultados del cálculo de potencial solar vía PVGIS.
    """
    building = models.OneToOneField(Building, on_delete=models.CASCADE, related_name='potential')
    
    # Resultados de generación
    annual_generation_kwh = models.FloatField(null=True, blank=True)
    monthly_generation_json = models.JSONField(null=True, blank=True) # [jan, feb, ..., dec]
    
    # Configuración de la instalación ideal calculada
    peak_power_kwp = models.FloatField(null=True, blank=True)
    estimated_panels = models.IntegerField(null=True, blank=True)
    
    # Vector de características para pgVector (Similitud)
    # [roof_area, azimuth, height, annual_generation_kwh, building_type_id]
    # Usaremos un campo genérico de Postgres o un plugin si está disponible en Django,
    # si no, usaremos una consulta SQL pura para el vector.
    # feature_vector = models.BinaryField(null=True) # Placeholder para el vector
    
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'solar_potentials'
        verbose_name = _('Potencial Solar')
        verbose_name_plural = _('Potenciales Solares')

    def __str__(self):
        return f"Potencial {self.building.osm_id}: {self.annual_generation_kwh} kWh/año"
