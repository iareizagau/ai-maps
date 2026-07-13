from django.conf import settings
from django.db import models
from django.utils.translation import get_language


class Category(models.Model):
    """Category of blog posts (e.g. Backend, WebGIS, AI, Ecosystem)"""

    name_es = models.CharField(max_length=100, verbose_name="Nombre (ES)")
    name_eu = models.CharField(max_length=100, verbose_name="Izena (EU)")
    name_en = models.CharField(max_length=100, verbose_name="Name (EN)")
    slug = models.SlugField(unique=True, help_text="Universal slug used in URLs")

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    @property
    def name(self):
        lang = get_language()
        if lang == "eu" and self.name_eu:
            return self.name_eu
        if lang == "en" and self.name_en:
            return self.name_en
        return self.name_es or self.name_eu or self.name_en or self.slug


class Tag(models.Model):
    """Tags for filtering blog posts (e.g. django, postgis, docker)"""

    name_es = models.CharField(max_length=100, verbose_name="Nombre (ES)")
    name_eu = models.CharField(max_length=100, verbose_name="Izena (EU)")
    name_en = models.CharField(max_length=100, verbose_name="Name (EN)")
    slug = models.SlugField(unique=True, help_text="Universal slug used in URLs")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name

    @property
    def name(self):
        lang = get_language()
        if lang == "eu" and self.name_eu:
            return self.name_eu
        if lang == "en" and self.name_en:
            return self.name_en
        return self.name_es or self.name_eu or self.name_en or self.slug


class Post(models.Model):
    """Blog post model with trilingual content and WebGIS / Leaflet coordinates"""

    DIFFICULTY_CHOICES = [
        ("beginner", "Introductory"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    tags = models.ManyToManyField(Tag, related_name="posts", blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
    )

    # Titles
    title_es = models.CharField(max_length=255, verbose_name="Título (ES)")
    title_eu = models.CharField(
        max_length=255, verbose_name="Izenburua (EU)", blank=True
    )
    title_en = models.CharField(max_length=255, verbose_name="Title (EN)", blank=True)

    # Slugs
    slug_es = models.SlugField(
        max_length=255, unique=True, verbose_name="Slug (ES)", blank=True, null=True
    )
    slug_eu = models.SlugField(
        max_length=255, unique=True, verbose_name="Slug (EU)", blank=True, null=True
    )
    slug_en = models.SlugField(
        max_length=255, unique=True, verbose_name="Slug (EN)", blank=True, null=True
    )

    # Summaries
    summary_es = models.TextField(verbose_name="Resumen (ES)", blank=True)
    summary_eu = models.TextField(verbose_name="Laburpena (EU)", blank=True)
    summary_en = models.TextField(verbose_name="Summary (EN)", blank=True)

    # Contents
    content_es = models.TextField(verbose_name="Contenido (ES)", blank=True)
    content_eu = models.TextField(verbose_name="Edukia (EU)", blank=True)
    content_en = models.TextField(verbose_name="Content (EN)", blank=True)

    # Editorial metadata
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    read_time = models.PositiveIntegerField(
        default=5, help_text="Estimated reading time in minutes"
    )
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="beginner",
    )
    featured_image = models.ImageField(upload_to="blog/images/", blank=True, null=True)

    # WebGIS features
    map_geojson = models.TextField(
        blank=True,
        null=True,
        help_text="Optional raw GeoJSON to overlay on the Leaflet map widget",
    )
    map_center_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=43.0,
        help_text="Latitude for Leaflet center",
    )
    map_center_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=-2.5,
        help_text="Longitude for Leaflet center",
    )
    map_zoom = models.IntegerField(default=9, help_text="Zoom level for Leaflet map")

    # Metrics
    likes = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def _resolve_field(self, field_base):
        lang = get_language()
        val = getattr(self, f"{field_base}_{lang}", None)
        if val:
            return val
        # Fallbacks
        for fallback_lang in ["eu", "es", "en"]:
            val = getattr(self, f"{field_base}_{fallback_lang}", None)
            if val:
                return val
        return ""

    @property
    def title(self):
        return self._resolve_field("title")

    @property
    def slug(self):
        return self._resolve_field("slug")

    @property
    def summary(self):
        return self._resolve_field("summary")

    @property
    def content(self):
        return self._resolve_field("content")
