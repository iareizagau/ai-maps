from django.contrib import admin
from .models import Category, Tag, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_es", "name_eu", "name_en", "slug")
    search_fields = ("name_es", "name_eu", "name_en", "slug")
    prepopulated_fields = {"slug": ("name_es",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name_es", "name_eu", "name_en", "slug")
    search_fields = ("name_es", "name_eu", "name_en", "slug")
    prepopulated_fields = {"slug": ("name_es",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title_es",
        "category",
        "is_published",
        "published_at",
        "difficulty",
        "read_time",
        "likes",
    )
    list_filter = ("is_published", "category", "difficulty", "tags")
    search_fields = (
        "title_es",
        "title_eu",
        "title_en",
        "summary_es",
        "summary_eu",
        "summary_en",
    )
    date_hierarchy = "published_at"

    prepopulated_fields = {
        "slug_es": ("title_es",),
        "slug_eu": ("title_eu",),
        "slug_en": ("title_en",),
    }

    fieldsets = (
        (
            "Categorización y Taxonomía",
            {"fields": ("category", "tags", "author")},
        ),
        (
            "Contenido en Español",
            {
                "fields": (
                    "title_es",
                    "slug_es",
                    "summary_es",
                    "content_es",
                )
            },
        ),
        (
            "Contenido en Euskara",
            {
                "fields": (
                    "title_eu",
                    "slug_eu",
                    "summary_eu",
                    "content_eu",
                )
            },
        ),
        (
            "Contenido en Inglés",
            {
                "fields": (
                    "title_en",
                    "slug_en",
                    "summary_en",
                    "content_en",
                )
            },
        ),
        (
            "Metadata Editorial",
            {
                "fields": (
                    "is_published",
                    "published_at",
                    "read_time",
                    "difficulty",
                    "featured_image",
                    "likes",
                )
            },
        ),
        (
            "Configuración de Mapa (WebGIS)",
            {
                "fields": (
                    "map_geojson",
                    "map_center_lat",
                    "map_center_lng",
                    "map_zoom",
                ),
                "description": "Si se proporciona GeoJSON o coordenadas, se renderizará un mapa interactivo de Leaflet en el post.",
            },
        ),
    )
