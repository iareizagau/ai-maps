from typing import ClassVar

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


class SolarPotential(BaseModel):
    """Cached PVGIS v5.3 photovoltaic potential for a Promocion.

    One row per Promocion. Values are per kWp installed under standard
    orientation (south, 30°) with 14% system losses. Raw JSON kept for
    audit and re-parsing if PVGIS schema changes.
    """

    promocion = models.OneToOneField(Promocion, on_delete=models.CASCADE, related_name="solar")
    kwh_kwp_year = models.DecimalField(max_digits=7, decimal_places=2)
    monthly_json = models.JSONField(default=list)
    irradiation_year = models.DecimalField(max_digits=8, decimal_places=2)

    tilt_deg = models.PositiveSmallIntegerField(default=30)
    azimuth_deg = models.SmallIntegerField(default=0)
    system_loss_pct = models.DecimalField(max_digits=4, decimal_places=1, default=14)
    pvgis_version = models.CharField(max_length=20, default="v5_3")
    raw_json = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list] = [models.Index(fields=["kwh_kwp_year"])]

    def __str__(self):
        return f"Solar {self.promocion.slug}: {self.kwh_kwp_year} kWh/kWp·año"


class AemetStation(BaseModel):
    """Cached AEMET station inventory. Refreshed via management command."""

    idema = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=200)
    provincia = models.CharField(max_length=80, blank=True)
    altitud_m = models.IntegerField(null=True, blank=True)
    location = gis_models.PointField(srid=4326)
    raw_json = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list] = [gis_models.Index(fields=["location"])]

    def __str__(self):
        return f"{self.idema} · {self.nombre}"


class PromocionClima(BaseModel):
    """Cached AEMET monthly normals (1991-2020) for a Promocion.

    Three 12-value series: temp_mean (°C), precipitation (mm), sun_hours (h).
    Linked to the nearest AemetStation within AEMET_MAX_STATION_DISTANCE_M.
    """

    promocion = models.OneToOneField(Promocion, on_delete=models.CASCADE, related_name="clima")
    station = models.ForeignKey(AemetStation, on_delete=models.PROTECT, related_name="climas")
    distance_m = models.PositiveIntegerField()

    temp_mean = models.JSONField(default=list)
    precipitation = models.JSONField(default=list)
    sun_hours = models.JSONField(default=list)
    period_label = models.CharField(max_length=40, blank=True)

    raw_json = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list] = [models.Index(fields=["station"])]

    def __str__(self):
        return f"Clima {self.promocion.slug} ← {self.station.idema} ({self.distance_m} m)"


class AirQualityStation(BaseModel):
    """OpenAQ v3 air-quality monitoring station in Spain, cached locally.

    Standalone (no FK to Promocion): this is a global map layer, not a
    per-promocion datum. Readings are the most recent values exposed by the
    OpenAQ /locations endpoint for the four buyer-relevant parameters.
    Units: µg/m³.
    """

    openaq_id = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=2, default="ES")

    location = gis_models.PointField(srid=4326)

    pm25 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    pm10 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    no2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    o3 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    measurements_at = models.DateTimeField(null=True, blank=True)

    raw_json = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list] = [gis_models.Index(fields=["location"])]
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(country="ES"),
                name="aqs_country_es_only",
            ),
        ]

    def __str__(self):
        return f"{self.openaq_id} · {self.name}"
