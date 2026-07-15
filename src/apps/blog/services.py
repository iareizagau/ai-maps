import json
import logging
from datetime import UTC, datetime
import feedparser
import requests
from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from apps.blog.models import Category, Tag, Post
from apps.mubil.ask.services import _call_gemini_generate

log = logging.getLogger(__name__)

User = get_user_model()

NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_QUERY = '("software development" OR "inteligencia artificial" OR "WebGIS" OR "PostGIS" OR "pgrouting" OR "pgvector")'

FALLBACK_RSS_FEEDS = [
    ("xataka", "https://feeds.weblogssl.com/xataka2"),
    ("genbeta", "https://www.genbeta.com/rss2.xml"),
    ("slashdot", "https://slashdot.org/slashdot.rss"),
]

SYSTEM_DOSSIER = """
Eres el redactor técnico principal y arquitecto de software de ai.maps.eus.
ai.maps.eus es un ecosistema avanzado de WebGIS e Inteligencia Artificial para Euskal Herria.
Tecnologías utilizadas en ai.maps.eus:
- Django 6.0 (Python) para el backend.
- PostgreSQL con la extensión PostGIS para almacenar y consultar datos geoespaciales.
- pgrouting para resolver problemas de redes y calcular rutas óptimas (ej. rutas de bikepacking en Euskadi).
- pgvector para almacenamiento de embeddings y búsqueda semántica (RAG).
- Gemini API (google-genai) como LLM para asistentes virtuales y agentes conversacionales.
- Celery con Redis para colas de tareas asíncronas y tareas periódicas (Celery Beat).
- Docker y Docker Compose para contenedores, optimizados usando 'uv' para instalaciones ultrarrápidas.
- Frontend ágil e interactivo construido con HTML, TailwindCSS, Alpine.js y HTMX.
"""

PROMPT_TEMPLATE = """
{system_dossier}

Recibes una noticia tecnológica reciente. Tu objetivo es redactar un post diario de blog técnico trilingüe (Español, Euskera, Inglés).
El post debe ser de alta calidad y conectar la temática de la noticia con las tecnologías y aplicaciones del ecosistema de ai.maps.eus.

=== Noticia de Origen ===
Título: {news_title}
Descripción: {news_snippet}
URL original: {news_url}

=== Historial de Posts Recientes (Evita Duplicaciones) ===
{history}

Instrucciones de deduplicación y redacción:
1. Compara la noticia de origen con el historial de posts recientes. Si la temática ya ha sido tratada, no repitas conceptos básicos. En su lugar:
   - Redacta una continuación (ej. "Parte 2").
   - Enfócate en un caso de uso diferente, optimizaciones más complejas o mejoras en el pipeline de ai.maps.eus.
2. Genera contenido para todos los campos indicados en el JSON.
3. El contenido de cada idioma debe ser estructurado usando HTML limpio y profesional (párrafos con `<p>`, subtítulos con `<h3>`, bloques de código con `<pre><code>`, etc.). No incluyas bloques markdown (```html) dentro de los strings HTML.
4. Campo `map_geojson`: Si el post tiene alguna relación geográfica (ej. rutas, zonas reguladas ZBE en ciudades vascas, localización de sensores, etc.), autogenera un GeoJSON FeatureCollection válido centrado en Euskal Herria (Bizkaia, Gipuzkoa, Araba, Nafarroa o Iparralde). En caso contrario, pon null. Si pones un GeoJSON, también debes rellenar `map_center_lat`, `map_center_lng` y `map_zoom` con valores válidos y coherentes en el País Vasco.

Devuelve EXCLUSIVAMENTE un objeto JSON válido (sin texto explicativo antes o después, sin bloques ```json) con la siguiente estructura exacta:

{{
  "title_es": "Título en castellano",
  "title_eu": "Izenburua euskaraz",
  "title_en": "Title in English",
  "slug_es": "slug-en-castellano",
  "slug_eu": "slug-en-euskera",
  "slug_en": "slug-en-ingles",
  "summary_es": "Resumen de 2 frases en castellano",
  "summary_eu": "Laburpena euskaraz (2 esaldi)",
  "summary_en": "Summary in English (2 sentences)",
  "content_es": "Contenido HTML del post en castellano",
  "content_eu": "Contenido HTML del post en euskera",
  "content_en": "Contenido HTML del post en inglés",
  "category_slug": "slug-de-categoria-existente (elige uno de: backend-architecture | webgis-postgis | ai-workflows | platform-updates)",
  "tag_slugs": ["lista", "de", "slugs-de-tags-existentes-o-nuevos", "ej: django, postgis, gemini, docker, celery, cicd"],
  "difficulty": "beginner | intermediate | advanced",
  "read_time": 5,
  "map_geojson": "string_geojson_valido_o_null",
  "map_center_lat": 42.8485 (o null),
  "map_center_lng": -2.6705 (o null),
  "map_zoom": 13 (o null)
}}
"""

def fetch_latest_tech_news() -> dict | None:
    """Fetch the latest relevant technical article. Falls back to RSS feeds."""
    key = (settings.NEWS_API_KEY or "").strip()
    if key:
        params = {
            "q": NEWSAPI_QUERY,
            "language": "es",
            "sortBy": "publishedAt",
            "pageSize": 10,
        }
        headers = {"X-Api-Key": key}
        try:
            resp = requests.get(NEWSAPI_URL, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("status") == "ok" and payload.get("articles"):
                    # Pick the first article with sufficient content
                    for art in payload["articles"]:
                        title = (art.get("title") or "").strip()
                        snippet = (art.get("description") or art.get("content") or "").strip()
                        url = art.get("url") or ""
                        if title and snippet and url:
                            return {"title": title, "snippet": snippet, "url": url}
        except Exception as e:
            log.warning("NewsAPI fetch failed in blog services: %s. Falling back to RSS.", e)

    # Fallback to RSS Feeds
    for source, url in FALLBACK_RSS_FEEDS:
        try:
            parsed = feedparser.parse(url)
            if not parsed.bozo and parsed.entries:
                for entry in parsed.entries[:5]:
                    title = (entry.get("title") or "").strip()
                    snippet = (entry.get("summary") or entry.get("description") or "").strip()
                    link = entry.get("link") or ""
                    if title and snippet and link:
                        return {"title": title, "snippet": snippet, "url": link}
        except Exception as e:
            log.warning("RSS fallback feed %s failed: %s", source, e)
            continue

    return None

def get_recent_posts_history() -> str:
    """Compile titles and summaries of recent posts for context."""
    posts = Post.objects.all().order_by("-created_at")[:10]
    if not posts.exists():
        return "(No hay posts previos en el blog)"
    
    lines = []
    for p in posts:
        lines.append(f"- Título (ES): {p.title_es} / Título (EU): {p.title_eu}\n  Resumen (ES): {p.summary_es}")
    return "\n".join(lines)

def validate_and_clean_geojson(geojson_str: str | None) -> tuple[str | None, bool]:
    """Parse geojson string to ensure it is valid JSON and GeoJSON structure."""
    if not geojson_str:
        return None, True
    try:
        data = json.loads(geojson_str)
        if isinstance(data, dict) and "type" in data:
            return json.dumps(data), True
    except Exception as e:
        log.warning("GeoJSON parsing or validation failed: %s", e)
    return None, False

def create_daily_post() -> Post | None:
    """Orchestrate fetching, deduplication, Gemini generation, and database save in draft mode."""
    # 1. Fetch news article
    news = fetch_latest_tech_news()
    if not news:
        log.error("Could not fetch any news or RSS articles to start daily blog generation.")
        return None

    # 2. Get history
    history = get_recent_posts_history()

    # 3. Format prompt
    prompt = PROMPT_TEMPLATE.format(
        system_dossier=SYSTEM_DOSSIER,
        news_title=news["title"],
        news_snippet=news["snippet"],
        news_url=news["url"],
        history=history,
    )

    # 4. Call Gemini
    try:
        raw_response = _call_gemini_generate(prompt)
    except Exception as e:
        log.exception("Failed calling Gemini to write the blog post: %s", e)
        return None

    # Strip optional fences
    clean_txt = raw_response.strip()
    if clean_txt.startswith("```"):
        clean_txt = clean_txt.split("\n", 1)[1] if "\n" in clean_txt else clean_txt
        if clean_txt.endswith("```"):
            clean_txt = clean_txt[:-3]
        clean_txt = clean_txt.strip()

    try:
        data = json.loads(clean_txt)
    except Exception as e:
        log.error("Gemini returned invalid JSON for blog post. raw=%r, error=%s", raw_response[:500], e)
        return None

    # Validate Category
    cat_slug = data.get("category_slug", "backend-architecture")
    category = Category.objects.filter(slug=cat_slug).first()
    if not category:
        category = Category.objects.first()

    # Find author (preferably superuser, else staff, else first user)
    author = User.objects.filter(is_superuser=True).first()
    if not author:
        author = User.objects.filter(is_staff=True).first()
    if not author:
        author = User.objects.first()

    if not author:
        log.error("No user found in the database to assign as author of the automated blog post.")
        return None

    # Clean and validate GeoJSON
    geojson_data, is_valid_geojson = validate_and_clean_geojson(data.get("map_geojson"))
    map_center_lat = data.get("map_center_lat") if is_valid_geojson else None
    map_center_lng = data.get("map_center_lng") if is_valid_geojson else None
    map_zoom = data.get("map_zoom") if is_valid_geojson else None

    # Slugs fallback
    slug_es = data.get("slug_es") or slugify(data.get("title_es") or "automatic-post")
    slug_eu = data.get("slug_eu") or slugify(data.get("title_eu") or "automatic-post-eu")
    slug_en = data.get("slug_en") or slugify(data.get("title_en") or "automatic-post-en")

    # Read time fallback
    try:
        read_time = int(data.get("read_time", 5))
    except (ValueError, TypeError):
        read_time = 5

    # Create the post in Draft mode
    post = Post.objects.create(
        category=category,
        author=author,
        title_es=data.get("title_es") or news["title"],
        title_eu=data.get("title_eu") or "",
        title_en=data.get("title_en") or "",
        slug_es=slug_es[:255],
        slug_eu=slug_eu[:255],
        slug_en=slug_en[:255],
        summary_es=data.get("summary_es") or "",
        summary_eu=data.get("summary_eu") or "",
        summary_en=data.get("summary_en") or "",
        content_es=data.get("content_es") or "",
        content_eu=data.get("content_eu") or "",
        content_en=data.get("content_en") or "",
        is_published=False,
        published_at=None,
        read_time=read_time,
        difficulty=data.get("difficulty", "beginner"),
        map_geojson=geojson_data,
        map_center_lat=map_center_lat,
        map_center_lng=map_center_lng,
        map_zoom=map_zoom,
    )

    # Resolve Tags
    tag_slugs = data.get("tag_slugs", [])
    if isinstance(tag_slugs, list):
        for tslug in tag_slugs:
            tslug_clean = slugify(tslug)[:100]
            if not tslug_clean:
                continue
            tag, _ = Tag.objects.get_or_create(
                slug=tslug_clean,
                defaults={
                    "name_es": tslug,
                    "name_eu": tslug,
                    "name_en": tslug,
                }
            )
            post.tags.add(tag)

    log.info("Successfully created daily blog post: %s (ID: %d)", post.title_es, post.id)
    return post
