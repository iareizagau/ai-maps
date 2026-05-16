from django.contrib.gis.db import models
from django.conf import settings

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

class Route(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='adventure_routes')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    
    # Datos de Enrutamiento
    profile = models.CharField(max_length=50) # ej: 'bikepacking', 'hiking'
    waypoints = models.JSONField(help_text="Array de coordenadas [lng, lat] para permitir edición posterior")
    geom = models.MultiLineStringField(srid=4326, help_text="La línea trazada por PgRouting")
    
    location_city = models.CharField(max_length=100, blank=True, null=True)
    location_province = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadatos cacheados (para no recalcular en el dashboard)
    distance_meters = models.FloatField()
    elevation_gain = models.FloatField()
    elevation_loss = models.FloatField()
    surface_stats = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'adventure_routes'
        verbose_name = 'Ruta Guardada'
        verbose_name_plural = 'Rutas Guardadas'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def distance_km(self):
        return self.distance_meters / 1000.0

    @property
    def svg_path(self):
        """Generates an SVG path normalized to a 0-100 viewBox"""
        if not self.waypoints or len(self.waypoints) < 2:
            return ""
        
        lngs = [p[0] for p in self.waypoints]
        lats = [p[1] for p in self.waypoints]
        
        min_lng, max_lng = min(lngs), max(lngs)
        min_lat, max_lat = min(lats), max(lats)
        
        lng_diff = max_lng - min_lng
        lat_diff = max_lat - min_lat
        
        if lng_diff == 0: lng_diff = 0.0001
        if lat_diff == 0: lat_diff = 0.0001
        
        # Scale to 0-100 keeping aspect ratio within a 100x100 box
        scale = 90 / max(lng_diff, lat_diff) 
        
        x_offset = (100 - (lng_diff * scale)) / 2
        y_offset = (100 - (lat_diff * scale)) / 2
        
        path = []
        for i, p in enumerate(self.waypoints):
            x = x_offset + (p[0] - min_lng) * scale
            y = 100 - (y_offset + (p[1] - min_lat) * scale) # Invert Y
            prefix = "M" if i == 0 else "L"
            path.append(f"{prefix} {x:.1f} {y:.1f}")
            
        return " ".join(path)

    @property
    def difficulty_badge(self):
        dist = self.distance_km
        elev = self.elevation_gain
        if dist > 80 or elev > 2000:
            return "💀 Épica"
        elif dist > 40 or elev > 1000:
            return "🔥 Desafiante"
        elif dist > 20 or elev > 500:
            return "⚡ Activa"
        else:
            return "🍃 Paseo"
            
    @property
    def surface_percentages(self):
        """Devuelve asfalto vs tierra simplificado"""
        stats = self.surface_stats or {}
        asphalt_keys = ['asphalt', 'paved', 'concrete']
        asphalt_pct = sum([v for k, v in stats.items() if any(ak in k.lower() for ak in asphalt_keys)])
        dirt_pct = 100 - asphalt_pct
        if dirt_pct < 0: dirt_pct = 0
        
        return {
            "asphalt": round(asphalt_pct),
            "dirt": round(dirt_pct)
        }

class PointOfInterest(models.Model):
    """Puntos de interés genéricos importados de OSM"""
    POI_TYPES = (
        ('water', 'Agua / Fuente'),
        ('shelter', 'Refugio / Cabaña'),
        ('cafe', 'Cafetería / Bar'),
        ('station', 'Estación de Transporte'),
        ('other', 'Otro')
    )
    
    osm_id = models.BigIntegerField(unique=True)
    poi_type = models.CharField(max_length=50, choices=POI_TYPES, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    location = models.PointField(srid=4326, spatial_index=True)
    tags = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'adventure_pois'
        verbose_name = 'Punto de Interés'
        verbose_name_plural = 'Puntos de Interés'

    def __str__(self):
        return f"{self.get_poi_type_display()}: {self.name or self.osm_id}"

class IntelDrop(models.Model):
    """Reportes Tácticos y Cinematic Journaling (Fotos Geolocalizadas)"""
    INTEL_TYPES = (
        ('warning', '⚠️ Peligro / Obstáculo'),
        ('water_dry', '🏜️ Fuente sin agua'),
        ('water_ok', '💧 Fuente funcionando'),
        ('shelter_ok', '⛺ Refugio perfecto'),
        ('shelter_bad', '🏚️ Refugio en mal estado'),
        ('surface_mud', '💩 Mucho barro'),
        ('surface_snow', '❄️ Nieve bloqueando'),
        ('photo_epic', '📸 Lugar Épico (Journal)'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    route = models.ForeignKey('Route', on_delete=models.SET_NULL, null=True, blank=True, related_name='intel_drops')
    
    intel_type = models.CharField(max_length=50, choices=INTEL_TYPES)
    location = models.PointField(srid=4326, spatial_index=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='adventure_intel/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'adventure_intel'
        verbose_name = 'Intel Drop'
        verbose_name_plural = 'Intel Drops'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_intel_type_display()} por {self.user.username}"

    @property
    def is_fresh(self):
        from django.utils import timezone
        import datetime
        return self.created_at >= timezone.now() - datetime.timedelta(days=14)

class ExplorationRecord(models.Model):
    """
    Representa un 'Sector' del mundo descubierto por un usuario.
    Usamos una rejilla de ~100m x 100m (0.001 grados).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='discovered_sectors')
    sector_key = models.CharField(max_length=50, db_index=True) # Formato "lat_idx:lng_idx"
    geom = models.PolygonField(srid=4326)
    
    is_pioneer = models.BooleanField(default=False, help_text="¿Fue el primero en el mundo en descubrirlo?")
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'adventure_exploration'
        unique_together = ('user', 'sector_key')
        verbose_name = 'Sector Descubierto'
        verbose_name_plural = 'Sectores Descubiertos'

    def __str__(self):
        return f"{self.user.username} en {self.sector_key}"
