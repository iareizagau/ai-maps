from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Promocion(BaseModel):
    """A real-estate development scraped from amenabarpromociones.com."""

    class Estado(models.TextChoices):
        EN_VENTA = "EN_VENTA", _("En venta")
        EN_CURSO = "EN_CURSO", _("En curso")
        PROXIMA = "PROXIMA", _("Próxima")
        VENDIDA = "VENDIDA", _("Vendida")
        FINALIZADA = "FINALIZADA", _("Finalizada")

    slug = models.SlugField(max_length=120, unique=True)
    nombre = models.CharField(max_length=200)
    ciudad = models.CharField(max_length=120)
    provincia = models.CharField(max_length=80, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.EN_VENTA, db_index=True)
    porcentaje_vendido = models.PositiveSmallIntegerField(null=True, blank=True)
    nota = models.CharField(max_length=200, blank=True)

    source_url = models.URLField()
    detail_url = models.URLField(blank=True)
    image_url = models.URLField(blank=True)

    location = gis_models.PointField(srid=4326, null=True, blank=True)

    class Meta:
        ordering = ["estado", "nombre"]
        indexes = [
            gis_models.Index(fields=["estado"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.ciudad})"


class POI(BaseModel):
    """OpenStreetMap POI cached around a Promocion.

    Fetched via Overpass once per promocion with a radius covering the max
    display circle; the frontend filters client-side by category and distance.
    """

    class Categoria(models.TextChoices):
        # Order = display order in the neighbourhood card: buyer essentials first.
        COMPRAS = "COMPRAS", _("Supermercados")
        EDUCACION = "EDUCACION", _("Colegios")
        TRANSPORTE = "TRANSPORTE", _("Transporte público")
        VEHICULOS = "VEHICULOS", _("Vehículos")
        COMIDA = "COMIDA", _("Comida")
        BEBIDA = "BEBIDA", _("Bebida")
        ATRACTIVOS = "ATRACTIVOS", _("Atractivos")
        INFORMACION = "INFORMACION", _("Información")
        SALUD = "SALUD", _("Salud")
        FINANZAS = "FINANZAS", _("Finanzas")
        ADMINISTRACION = "ADMINISTRACION", _("Administración")
        RELIGION = "RELIGION", _("Religión")
        VERDES = "VERDES", _("Espacios verdes")
        DEPORTE = "DEPORTE", _("Deporte")
        CULTURA = "CULTURA", _("Cultura y ocio")
        HISTORICO = "HISTORICO", _("Histórico")
        NATURAL = "NATURAL", _("Elementos naturales")

    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="pois")
    osm_type = models.CharField(max_length=10)  # node / way / relation
    osm_id = models.BigIntegerField()
    nombre = models.CharField(max_length=200, blank=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, db_index=True)
    subtipo = models.CharField(max_length=80, blank=True)  # p.ej. bus_stop, pharmacy
    tags = models.JSONField(default=dict, blank=True)
    location = gis_models.PointField(srid=4326)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["promocion", "osm_type", "osm_id"],
                name="uniq_poi_per_promocion",
            ),
        ]
        indexes = [
            models.Index(fields=["promocion", "categoria"]),
        ]

    def __str__(self):
        return f"{self.nombre or self.subtipo} [{self.categoria}]"
