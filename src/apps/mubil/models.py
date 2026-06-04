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

from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import VectorField


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ============ CATÁLOGO DE VEHÍCULOS ============


class Vehicle(BaseModel):
    """EV / ICE / hybrid catalog. Authoritative source: IDAE base de datos
    (coches.idae.es) — WLTP homologated + DGT energy label. Manual seed rows
    keep `idae_id=NULL`; the partial unique constraint allows that without
    blocking the natural-key one.
    """

    class Propulsion(models.TextChoices):
        BEV = 'BEV', _('Eléctrico (BEV)')
        PHEV = 'PHEV', _('Híbrido enchufable')
        HEV = 'HEV', _('Híbrido')
        ICE = 'ICE', _('Gasolina')
        DIESEL = 'DIESEL', _('Diésel')
        CNG = 'CNG', _('Gas Natural Comprimido')
        LPG = 'LPG', _('GLP / Autogás')

    class DGTLabel(models.TextChoices):
        CERO = '0', _('Cero emisiones')
        ECO = 'ECO', _('ECO')
        C = 'C', _('C')
        B = 'B', _('B')
        SIN = 'SIN', _('Sin etiqueta')

    class Category(models.TextChoices):
        M1 = 'M1', _('Turismo')
        M2 = 'M2', _('Autobús ligero')
        N1 = 'N1', _('Furgoneta ligera')
        N2 = 'N2', _('Furgón pesado')
        L3e = 'L3e', _('Motocicleta')
        L6e = 'L6e', _('Cuadriciclo ligero')
        L7e = 'L7e', _('Cuadriciclo pesado')

    class EnergyClass(models.TextChoices):
        A = 'A', _('A')
        B = 'B', _('B')
        C = 'C', _('C')
        D = 'D', _('D')
        E = 'E', _('E')
        F = 'F', _('F')
        G = 'G', _('G')
        S = 'S', _('Sin clasificar')

    # Idempotency key for the IDAE ingest. NULL for manual seed rows.
    idae_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    make = models.CharField(max_length=80, db_index=True)
    # IDAE concatenates model + variant + sub-trim into the same Modelo
    # string, so 200 chars is needed to fit edge cases like long
    # "Touareg R eHybrid …" lines.
    model = models.CharField(max_length=200)
    # Distinguishes the dozens of versions a single (make, model, year) hides
    # in IDAE (TFSI 110 / TDI 115 / GTI / R). Empty string for legacy rows.
    variant = models.CharField(max_length=200, blank=True, default='')
    year = models.PositiveSmallIntegerField()
    propulsion = models.CharField(max_length=8, choices=Propulsion.choices, db_index=True)

    # Búsqueda y filtrado por etiqueta DGT / categoría / segmento — los chips
    # que va a tocar el jurado en el pitch.
    dgt_label = models.CharField(
        max_length=4, choices=DGTLabel.choices, blank=True, db_index=True,
    )
    category = models.CharField(
        max_length=4, choices=Category.choices, blank=True, db_index=True,
    )
    energy_class = models.CharField(
        max_length=1, choices=EnergyClass.choices, blank=True,
    )
    segment = models.CharField(max_length=40, blank=True, db_index=True)

    mtma_kg = models.PositiveIntegerField(null=True, blank=True)
    battery_kwh = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    range_wltp_km = models.PositiveIntegerField(null=True, blank=True)
    consumption_kwh_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    consumption_l_100km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # CO₂ WLTP — rango por las 4 fases. Para vehículos eléctricos se reporta 0.
    co2_g_km_min = models.PositiveSmallIntegerField(null=True, blank=True)
    co2_g_km_max = models.PositiveSmallIntegerField(null=True, blank=True)

    # No lo da IDAE; queda nullable. Se rellena via la pipeline de tres
    # capas: seed manual verificado → heurística calibrada → Gemini top-N.
    # El advisor también acepta override puntual en el formulario que no
    # toca esta columna.
    price_eur = models.PositiveIntegerField(null=True, blank=True)

    class PriceSource(models.TextChoices):
        UNKNOWN = 'unknown', _('Desconocido')
        MOCK = 'mock', _('Mock (placeholder)')
        MANUAL = 'manual', _('Verificado manual')
        HEURISTIC = 'heuristic', _('Estimado heurístico')
        GEMINI = 'gemini', _('Estimado Gemini')

    # Trazabilidad del precio para que la UI pueda etiquetar la confianza
    # ("PVP verificado" vs "estimado ±20 %") y los comandos de re-seed
    # sepan qué filas pueden sobrescribir sin perder datos verificados.
    price_source = models.CharField(
        max_length=16, choices=PriceSource.choices,
        default=PriceSource.UNKNOWN, db_index=True,
    )
    price_updated_at = models.DateTimeField(null=True, blank=True)

    source_url = models.URLField(blank=True)

    class Meta:
        ordering = ['make', 'model', '-year']
        constraints = [
            # IDAE id es la clave natural cuando existe (ingesta idempotente).
            models.UniqueConstraint(
                fields=['idae_id'],
                condition=models.Q(idae_id__isnull=False),
                name='vehicle_idae_unique',
            ),
            # Clave natural extendida solo para filas MANUALES (idae_id NULL):
            # IDAE tiene varias versiones del mismo (make, model, variant) con
            # distinto idae_id y year=0, así que no podemos imponer este
            # constraint sobre filas importadas.
            models.UniqueConstraint(
                fields=['make', 'model', 'variant', 'year'],
                condition=models.Q(idae_id__isnull=True),
                name='vehicle_manual_natural_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['propulsion', 'year']),
            models.Index(fields=['propulsion', 'dgt_label']),
            models.Index(fields=['category', 'segment']),
            # Fuzzy text search across make/model/variant — drives the
            # advisor's "type your car" autocomplete. Requires the pg_trgm
            # extension, created in migration 0005.
            GinIndex(
                name='vehicle_text_trgm',
                fields=['make', 'model', 'variant'],
                opclasses=['gin_trgm_ops', 'gin_trgm_ops', 'gin_trgm_ops'],
            ),
        ]

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

    def along_route(self, polyline_lonlat, radius_km=5):
        """Chargers within ``radius_km`` of a route's LineString.

        Args:
            polyline_lonlat: iterable of ``(lon, lat)`` pairs (GeoJSON order).
            radius_km: corridor half-width around the route.

        Returns the queryset annotated with ``distance`` (m from the line,
        spheroidal), ordered by proximity. Uses GIST-indexed ``ST_DWithin``
        with a degrees radius — PostGIS requires numeric degrees, not
        ``Distance``, for ``dwithin`` on geographic (4326) geometry columns.
        """
        from django.contrib.gis.geos import LineString
        from django.contrib.gis.db.models.functions import Distance

        coords = [(float(lon), float(lat)) for lon, lat in polyline_lonlat]
        if len(coords) < 2:
            return self.none()
        line = LineString(coords, srid=4326)
        # 1° ≈ 111 km at the equator. Slightly conservative at our latitudes
        # (~43°N, where 1° lon ≈ 81 km), so the corridor is a bit wider in
        # E-W direction — acceptable for a fast-charger pre-filter.
        radius_deg = float(radius_km) / 111.0
        return self.filter(
            geom__dwithin=(line, radius_deg)
        ).annotate(
            distance=Distance('geom', line, spheroid=True)
        ).order_by('distance')


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
