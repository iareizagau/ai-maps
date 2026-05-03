from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _, get_language

User = get_user_model()

class BaseModel(models.Model):
    """Base model with timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Club(BaseModel):
    """Club de monte"""
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='clubs/', blank=True, null=True)
    location = gis_models.PointField(null=True, blank=True)

    def __str__(self):
        return self.name

class Outing(BaseModel):
    """Salida de monte organizada por un club"""
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='outings')
    title = models.CharField(max_length=255)
    date = models.DateField()
    description = models.TextField(blank=True)
    location = gis_models.PointField(null=True, blank=True)
    difficulty = models.CharField(max_length=100, blank=True)
    gpx_file = models.FileField(upload_to='outings/gpx/', blank=True, null=True)
    image = models.ImageField(upload_to='outings/images/', blank=True, null=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.date} - {self.title}"

class Crag(BaseModel):
    """Zona de escalada (e.g. Egino, Atxarte)"""
    name_es = models.CharField(max_length=255, blank=True)
    name_eu = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(unique=True)
    location = gis_models.PointField()
    description_es = models.TextField(blank=True)
    description_eu = models.TextField(blank=True)
    access_info_es = models.TextField(blank=True)
    access_info_eu = models.TextField(blank=True)

    @property
    def name(self):
        lang = get_language()
        if lang == 'eu' and self.name_eu:
            return self.name_eu
        return self.name_es or self.name_eu or self.slug

    @property
    def description(self):
        lang = get_language()
        if lang == 'eu' and self.description_eu:
            return self.description_eu
        return self.description_es or self.description_eu

    def __str__(self):
        return self.name

class Sector(BaseModel):
    """Sector dentro de una zona de escalada"""
    crag = models.ForeignKey(Crag, on_delete=models.CASCADE, related_name='sectors')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    orientation = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.crag.name} - {self.name}"

class Route(BaseModel):
    """Vía de escalada"""
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='routes')
    name_es = models.CharField(max_length=255, blank=True)
    name_eu = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(unique=True, max_length=255)
    grade = models.CharField(max_length=20, blank=True)
    description_es = models.TextField(blank=True)
    description_eu = models.TextField(blank=True)
    is_bolted = models.BooleanField(default=True)

    @property
    def name(self):
        lang = get_language()
        if lang == 'eu' and self.name_eu:
            return self.name_eu
        return self.name_es or self.name_eu

    @property
    def description(self):
        lang = get_language()
        if lang == 'eu' and self.description_eu:
            return self.description_eu
        return self.description_es or self.description_eu

    @property
    def get_croquis(self):
        """Extracts image URLs from HTML content using regex"""
        import re
        content = (self.description_es or "") + (self.description_eu or "")
        return re.findall(r'<img [^>]*src="([^"]+)"', content)

    def __str__(self):
        return f"{self.name} ({self.grade})"

class Topo(BaseModel):
    """Croquis / Imágenes de las vías"""
    sector = models.ForeignKey(Sector, on_delete=models.SET_NULL, null=True, blank=True, related_name='topos')
    outing = models.ForeignKey(Outing, on_delete=models.SET_NULL, null=True, blank=True, related_name='images')
    image = models.ImageField(upload_to='gailur/topos/')
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title or f"Image {self.id}"
