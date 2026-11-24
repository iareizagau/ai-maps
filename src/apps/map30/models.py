from datetime import date

from django.db import models


class MapEntry(models.Model):
    """Una entrada del #30DayMapChallenge 2026.

    Cada día es un mapa publicado como página propia. El template vive en
    `templates/map30/days/{day:02}_{slug}.html` y se descubre por convención
    desde `template_name` (o se calcula a partir de `day` + `slug` si se omite).
    """

    class Library(models.TextChoices):
        MAPLIBRE = "maplibre", "MapLibre GL JS"
        LEAFLET = "leaflet", "Leaflet"
        STATIC = "static", "Static (imagen / no interactivo)"

    class Basemap(models.TextChoices):
        VOYAGER = "voyager", "CARTO Voyager"
        POSITRON = "positron", "CARTO Positron (light)"
        DARK_MATTER = "dark_matter", "CARTO Dark Matter"
        OSM = "osm", "OSM raster"
        NONE = "none", "Sin basemap"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicado"

    day = models.PositiveSmallIntegerField(unique=True)  # 1..30
    date = models.DateField()  # 2026-11-DD
    category_slug = models.SlugField(max_length=40)  # "points", "lines"…
    category_name = models.CharField(max_length=80)  # "Points", "Lines"…
    title = models.CharField(max_length=160)
    blurb = models.TextField(blank=True)  # 1-3 frases, se renderiza como texto plano

    library = models.CharField(max_length=20, choices=Library.choices, default=Library.MAPLIBRE)
    basemap = models.CharField(max_length=20, choices=Basemap.choices, default=Basemap.VOYAGER)
    template_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Deja vacío para usar map30/days/{day:02}_{category_slug}.html",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day"]
        verbose_name = "Map30 entry"
        verbose_name_plural = "Map30 entries"

    def __str__(self) -> str:
        return f"Día {self.day:02} — {self.category_name}"

    @property
    def template_path(self) -> str:
        if self.template_name:
            return self.template_name
        return f"map30/days/{self.day:02d}_{self.category_slug}.html"

    @property
    def is_past(self) -> bool:
        return self.date <= date.today()

    @property
    def prev_day(self) -> int | None:
        return self.day - 1 if self.day > 1 else None

    @property
    def next_day(self) -> int | None:
        return self.day + 1 if self.day < 30 else None
