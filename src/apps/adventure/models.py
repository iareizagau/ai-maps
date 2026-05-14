from django.contrib.gis.db import models

class TrailEdge(models.Model):
    """
    Modelo base para experimentos de pgRouting.
    Representa un 'arco' o tramo de camino.
    """
    # Campos requeridos por pgRouting
    source = models.IntegerField(null=True, blank=True, db_index=True)
    target = models.IntegerField(null=True, blank=True, db_index=True)
    cost = models.FloatField(null=True, blank=True)
    reverse_cost = models.FloatField(null=True, blank=True)
    
    # Atributos de aventura (OSM tags)
    name = models.CharField(max_length=255, blank=True)
    surface = models.CharField(max_length=100, blank=True, db_index=True)
    highway = models.CharField(max_length=100, blank=True, db_index=True)
    tracktype = models.CharField(max_length=100, blank=True)
    sac_scale = models.CharField(max_length=100, blank=True) # Dificultad senderismo
    mtb_scale = models.CharField(max_length=100, blank=True) # Dificultad MTB
    
    # Geometría
    geom = models.LineStringField(srid=4326)

    class Meta:
        db_table = 'adventure_trails'
        verbose_name = 'Tramo de Aventura'
        verbose_name_plural = 'Tramos de Aventura'

    def __str__(self):
        return f"{self.name or 'Camino'} ({self.highway})"

class Fountain(models.Model):
    """Puntos de agua potable (OSM amenity=drinking_water)"""
    osm_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    location = models.PointField(srid=4326)
    operational = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'adventure_fountains'
        verbose_name = 'Fuente'
        verbose_name_plural = 'Fuentes'

    def __str__(self):
        return self.name or f"Fuente {self.osm_id}"
