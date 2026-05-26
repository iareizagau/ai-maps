"""
Models for the mubil domain — sustainable-mobility intelligence for Euskal Herria.

Scope and rationale: see .claude/knowledge/mubil/PROPUESTA.md §3, §5, §17.
4 sub-modules share these models: advisor, ask, route, plan.

Migrations: pgvector requires `CREATE EXTENSION IF NOT EXISTS vector` and TimescaleDB
hypertables (EnergyPricePVPC, MobilityTrip) are created with a raw SQL `SELECT
create_hypertable(...)` step. Add these as separate RunSQL operations when first
running `makemigrations mubil` — do NOT auto-generate.
"""

from decimal import Decimal

from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ============ CATÁLOGO DE VEHÍCULOS ============


class Vehicle(BaseModel):
    """EV / ICE / hybrid catalog. Seed from DGT + investigacoches.es (atribuir)."""

    class Propulsion(models.TextChoices):
        BEV = 'BEV', _('Eléctrico (BEV)')
        PHEV = 'PHEV', _('Híbrido enchufable')
        HEV = 'HEV', _('Híbrido')
        ICE = 'ICE', _('Gasolina')
        DIESEL = 'DIESEL', _('Diésel')

    make = models.CharField(max_length=80)
    model = models.CharField(max_length=120)
    year = models.PositiveSmallIntegerField()
    propulsion = models.CharField(max_length=8, choices=Propulsion.choices, db_index=True)

    battery_kwh = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    range_wltp_km = models.PositiveIntegerField(null=True, blank=True)
    consumption_kwh_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    consumption_l_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    price_eur = models.PositiveIntegerField(null=True, blank=True)

    source_url = models.URLField(blank=True)

    class Meta:
        unique_together = ('make', 'model', 'year')
        ordering = ['make', 'model', '-year']
        indexes = [models.Index(fields=['propulsion', 'year'])]

    def __str__(self):
        return f"{self.make} {self.model} ({self.year})"


# ============ INFRAESTRUCTURA ESTÁTICA ============


class FuelStationQuerySet(models.QuerySet):
    def nearby(self, longitude, latitude, radius_km=5):
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import D
        from django.contrib.gis.db.models.functions import Distance

        point = Point(float(longitude), float(latitude))
        return self.filter(
            geom__distance_lte=(point, D(km=radius_km))
        ).annotate(distance=Distance('geom', point)).order_by('distance')


class FuelStation(models.Model):
    """Snapshot diario MINCOTUR `FiltroProvincia/20` (Gipuzkoa) — ~280 estaciones.

    Note: MINCOTUR returns decimal prices as strings with commas ("1,659"). Parser
    must normalise to Decimal before saving. See PROPUESTA.md §14.
    """

    objects = FuelStationQuerySet.as_manager()

    ideess = models.IntegerField(unique=True)  # MINCOTUR station id
    brand = models.CharField(max_length=80, blank=True)  # "Rótulo"
    address = models.CharField(max_length=300, blank=True)
    municipality_name = models.CharField(max_length=120, blank=True, db_index=True)
    postal_code = models.CharField(max_length=10, blank=True)

    geom = gis_models.PointField(srid=4326, spatial_index=True)

    prices = models.JSONField(default=dict, blank=True)
    # {"gasolina_95_e5": "1.659", "gasoleo_a": "1.499", ...}

    schedule = models.CharField(max_length=120, blank=True)  # "Horario"
    sale_type = models.CharField(max_length=4, blank=True)   # "P" public / "R" restricted

    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['municipality_name', 'brand']

    def __str__(self):
        return f"{self.brand} @ {self.municipality_name}"


class ChargingStationQuerySet(models.QuerySet):
    def nearby(self, longitude, latitude, radius_km=5):
        from django.contrib.gis.geos import Point
        from django.contrib.gis.measure import D
        from django.contrib.gis.db.models.functions import Distance

        point = Point(float(longitude), float(latitude))
        return self.filter(
            geom__distance_lte=(point, D(km=radius_km))
        ).annotate(distance=Distance('geom', point)).order_by('distance')

    def fast(self):
        return self.filter(power_kw__gte=50)


class ChargingStation(models.Model):
    """Puntos de recarga EV.

    Fuentes (con prioridad):
      1. OpenData Euskadi — dataset oficial CAV.
      2. MITECO / NAP DGT — puntos recarga estatales.
      3. OpenChargeMap — fallback global, crowdsourced.

    Deduplicación: clave compuesta (operator, geom dentro de 25 m).
    """

    objects = ChargingStationQuerySet.as_manager()

    external_id = models.CharField(max_length=80, blank=True)  # id fuente original
    source = models.CharField(max_length=40, blank=True)        # opendata_euskadi / miteco / ocm
    operator = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=300, blank=True)

    geom = gis_models.PointField(srid=4326, spatial_index=True)

    power_kw = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    connectors = models.JSONField(default=list, blank=True)
    # [{"type": "CCS2", "kw": 150}, ...]

    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-power_kw', 'operator']
        indexes = [models.Index(fields=['source', 'external_id'])]

    def __str__(self):
        return f"{self.operator or 'Cargador'} ({self.power_kw}kW)"


# ============ SERIES TEMPORALES (TimescaleDB hypertables) ============


class EnergyPricePVPC(models.Model):
    """PVPC horario (ESIOS indicator 1001).

    TimescaleDB hypertable on `timestamp`. Migración manual:
        SELECT create_hypertable('mubil_energypricepvpc', 'timestamp', if_not_exists => TRUE);
    """

    class Tariff(models.TextChoices):
        P1 = '2.0TD_P1', _('2.0TD P1 (punta)')
        P2 = '2.0TD_P2', _('2.0TD P2 (llano)')
        P3 = '2.0TD_P3', _('2.0TD P3 (valle)')

    timestamp = models.DateTimeField(db_index=True)
    tariff = models.CharField(max_length=12, choices=Tariff.choices, default=Tariff.P1)
    price_eur_mwh = models.DecimalField(max_digits=8, decimal_places=3)

    class Meta:
        unique_together = ('timestamp', 'tariff')
        ordering = ['-timestamp']

    def __str__(self):
        return f"PVPC {self.tariff} @ {self.timestamp:%Y-%m-%d %H:%M} = {self.price_eur_mwh}€/MWh"

    @property
    def price_eur_kwh(self) -> Decimal:
        return (self.price_eur_mwh / Decimal('1000')).quantize(Decimal('0.0001'))


class EVRegistration(models.Model):
    """Serie histórica matriculaciones DGT por municipio + propulsión.

    Fuente: notebook Laboratorio-Datos (datos.gob.es) — ingesta one-shot CSV.
    """

    municipality_naia = models.CharField(max_length=12, db_index=True)
    municipality_name = models.CharField(max_length=120, blank=True)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    propulsion = models.CharField(max_length=8, choices=Vehicle.Propulsion.choices)
    count = models.PositiveIntegerField()

    class Meta:
        unique_together = ('municipality_naia', 'year', 'month', 'propulsion')
        ordering = ['-year', '-month']
        indexes = [models.Index(fields=['propulsion', 'year', 'month'])]

    def __str__(self):
        return f"{self.municipality_name} {self.year}/{self.month} {self.propulsion}={self.count}"


class MobilityTrip(models.Model):
    """Orígenes-destinos MITMA Big Data (vía `pyspainmobility`).

    TimescaleDB hypertable on `date`. K-anonimato MITMA ≥ 15.
    """

    class Mode(models.TextChoices):
        WALK = 'walk', _('A pie')
        BIKE = 'bike', _('Bici')
        CAR = 'car', _('Coche')
        BUS = 'bus', _('Autobús')
        TRAIN = 'train', _('Tren')

    class Motive(models.TextChoices):
        HOME = 'home', _('Casa')
        WORK = 'work', _('Trabajo')
        STUDY = 'study', _('Estudio')
        OTHER = 'other', _('Otros')

    origin_naia = models.CharField(max_length=16, db_index=True)
    dest_naia = models.CharField(max_length=16, db_index=True)
    date = models.DateField(db_index=True)
    hour = models.PositiveSmallIntegerField()  # 0-23
    mode = models.CharField(max_length=8, choices=Mode.choices)
    motive = models.CharField(max_length=8, choices=Motive.choices, blank=True)
    n_trips = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=['date', 'origin_naia', 'dest_naia']),
            models.Index(fields=['date', 'mode']),
        ]
        ordering = ['-date', 'hour']


# ============ RAG / ASK (pgvector) ============


class MobilityDocument(models.Model):
    """Corpus para el módulo `ask` — metadatos de datasets, blogs y normativa.

    Embeddings 768d con Gemini `text-embedding-004`. Índice ivfflat.
    Migración manual:
        CREATE INDEX mubil_mobdoc_emb_ivf
          ON mubil_mobilitydocument USING ivfflat (embedding vector_cosine_ops)
          WITH (lists = 100);
    """

    class SourceType(models.TextChoices):
        DATASET = 'dataset', _('Dataset')
        BLOG = 'blog', _('Blog/article')
        NORMA = 'norma', _('Normativa')
        GTFS = 'gtfs_summary', _('GTFS resumen')

    title = models.CharField(max_length=300)
    source_url = models.URLField(blank=True)
    source_type = models.CharField(max_length=16, choices=SourceType.choices, db_index=True)
    municipality_naia = models.CharField(max_length=16, blank=True, db_index=True)

    content = models.TextField()
    content_hash = models.CharField(max_length=64, db_index=True)

    embedding = VectorField(dimensions=768, null=True, blank=True)

    ingested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ingested_at']

    def __str__(self):
        return f"[{self.source_type}] {self.title[:60]}"


# ============ PLAN — demanda heatmap ============


class DemandHex(models.Model):
    """Hex H3 de demanda predicha. Score precomputado por
    `manage.py compute_demand_scores` (no recalcula en vivo).
    """

    h3_index = models.CharField(max_length=15, primary_key=True)
    geom = gis_models.PolygonField(srid=4326, spatial_index=True)

    municipality_naia = models.CharField(max_length=16, blank=True, db_index=True)

    score_now = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    score_y3 = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    score_y5 = models.DecimalField(max_digits=6, decimal_places=3, default=0)

    components = models.JSONField(default=dict, blank=True)
    # {"registrations": 0.4, "od_density": 0.4, "current_chargers": -0.2}

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-score_now']

    def __str__(self):
        return f"{self.h3_index} ({self.municipality_naia}) → {self.score_now}"


# ============ ROUTE — cache de planes EV ============


class EVRoutePlan(models.Model):
    """Cache de las 5 rutas O-D precomputadas para la demo (MOCK).

    Producción posterior: pgRouting topology + SOC dinámico (fuera de MVP, §3 PROPUESTA).
    """

    origin = gis_models.PointField(srid=4326)
    dest = gis_models.PointField(srid=4326)

    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True)
    soc_start = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    geojson = models.JSONField(default=dict)
    # {"polyline": [...], "segments": [{"kind": "drive", ...}, {"kind": "charge_stop", ...}]}

    distance_km = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    duration_min = models.PositiveIntegerField(null=True, blank=True)
    energy_kwh = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    estimated_cost_eur = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-computed_at']

    def __str__(self):
        return f"EV route → {self.distance_km}km / {self.duration_min}min"
