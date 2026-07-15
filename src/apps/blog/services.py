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
NEWSAPI_QUERY = '("desarrollo de software" OR "desarrollo software" OR "arquitectura de software" OR "WebGIS" OR "PostGIS" OR "pgrouting" OR "pgvector")'

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

Recibes una noticia tecnológica reciente seleccionada por su relevancia. Tu objetivo es redactar un post diario de blog técnico trilingüe (Español, Euskera, Inglés).
El post debe ser de alta calidad, profundo y conectar la temática de la noticia con las tecnologías y aplicaciones del ecosistema de ai.maps.eus.

=== Noticia de Origen ===
Título: {news_title}
Descripción: {news_snippet}
URL original: {news_url}
Razón de selección: {selection_reason}

=== Artículos Relacionados (Lecturas Recomendadas) ===
{related_articles_str}

=== Historial de Posts Recientes (Evita Duplicaciones) ===
{history}

Instrucciones de deduplicación y redacción:
1. Compara la noticia de origen con el historial de posts recientes. Si la temática ya ha sido tratada, no repitas conceptos básicos. En su lugar:
   - Redacta una continuación (ej. "Parte 2").
   - Enfócate en un caso de uso diferente, optimizaciones más complejas o mejoras en el pipeline de ai.maps.eus.
2. Genera contenido para todos los campos indicados en el JSON.
3. El contenido de cada idioma debe ser estructurado usando HTML limpio y profesional (párrafos con `<p>`, subtítulos con `<h3>`, bloques de código con `<pre><code>`, etc.). No incluyas bloques markdown (```html) dentro de los strings HTML.
4. Al final del campo `content_es`, `content_eu` y `content_en`, debes agregar una sección de Lecturas Recomendadas/Artículos Relacionados en HTML limpio. Por ejemplo:
   `<h3>Lecturas recomendadas</h3><ul><li><a href="URL_ORIGINAL">TÍTULO</a></li>...</ul>` usando las URLs y títulos provistos en la sección "Artículos Relacionados".
5. Campo `map_geojson`: Si el post tiene alguna relación geográfica (ej. rutas, zonas reguladas ZBE en ciudades vascas, localización de sensores, etc.), autogenera un GeoJSON FeatureCollection válido centrado en Euskal Herria (Bizkaia, Gipuzkoa, Araba, Nafarroa o Iparralde). En caso contrario, pon null. Si pones un GeoJSON, también debes rellenar `map_center_lat`, `map_center_lng` y `map_zoom` con valores válidos y coherentes en el País Vasco.

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
  "content_es": "Contenido HTML completo (incluyendo el código y al final la sección de lecturas recomendadas) en castellano",
  "content_eu": "Contenido HTML completo (incluyendo el código y al final la sección de lecturas recomendadas) en euskera",
  "content_en": "Contenido HTML completo (incluyendo el código y al final la sección de lecturas recomendadas) en inglés",
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

def fetch_latest_tech_news() -> list[dict]:
    """Fetch the latest relevant technical articles. Falls back to RSS feeds.
    
    Skips articles that have already been processed into blog posts.
    Returns a list of candidate news items.
    """
    # Fetch existing post titles and contents to search for URLs and titles
    existing_posts = list(Post.objects.values("title_es", "content_es"))
    existing_titles_lower = [p["title_es"].lower() for p in existing_posts if p.get("title_es")]
    existing_contents = [p["content_es"] for p in existing_posts if p.get("content_es")]

    def is_already_processed(title: str, url: str) -> bool:
        # 1. Check if URL is in any existing post content
        for content in existing_contents:
            if url in content:
                return True
        # 2. Check if title has significant word overlap with any post title
        title_lower = title.lower()
        for et in existing_titles_lower:
            if title_lower in et or et in title_lower:
                return True
            words_art = set(w for w in title_lower.split() if len(w) > 3)
            words_exist = set(w for w in et.split() if len(w) > 3)
            if words_art and words_exist:
                overlap = words_art.intersection(words_exist)
                if len(overlap) / min(len(words_art), len(words_exist)) > 0.5:
                    return True
        return False

    candidates = []
    key = (settings.NEWS_API_KEY or "").strip()
    if key:
        params = {
            "q": NEWSAPI_QUERY,
            "language": "es",
            "sortBy": "publishedAt",
            "pageSize": 30,
        }
        headers = {"X-Api-Key": key}
        try:
            resp = requests.get(NEWSAPI_URL, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("status") == "ok" and payload.get("articles"):
                    for art in payload["articles"]:
                        title = (art.get("title") or "").strip()
                        snippet = (art.get("description") or art.get("content") or "").strip()
                        url = art.get("url") or ""
                        if title and snippet and url:
                            if not is_already_processed(title, url):
                                candidates.append({"title": title, "snippet": snippet, "url": url})
                                if len(candidates) >= 8:
                                    break
        except Exception as e:
            log.warning("NewsAPI fetch failed in blog services: %s. Falling back to RSS.", e)

    # Fallback/complements from RSS Feeds
    if len(candidates) < 5:
        for source, url in FALLBACK_RSS_FEEDS:
            try:
                parsed = feedparser.parse(url)
                if not parsed.bozo and parsed.entries:
                    for entry in parsed.entries[:10]:
                        title = (entry.get("title") or "").strip()
                        snippet = (entry.get("summary") or entry.get("description") or "").strip()
                        link = entry.get("link") or ""
                        if title and snippet and link:
                            if not is_already_processed(title, link):
                                if not any(c["url"] == link for c in candidates):
                                    candidates.append({"title": title, "snippet": snippet, "url": link})
                                    if len(candidates) >= 12:
                                        break
            except Exception as e:
                log.warning("RSS fallback feed %s failed: %s", source, e)
                continue
            if len(candidates) >= 12:
                break

    return candidates


def select_best_article_with_gemini(candidates: list[dict]) -> dict | None:
    """Use Gemini to evaluate candidate news items against our system dossier and select the best one."""
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
        
    candidates_list = []
    for idx, c in enumerate(candidates):
        candidates_list.append(
            f"[{idx}] Título: {c['title']}\nSnippet: {c['snippet']}\nURL: {c['url']}"
        )
    candidates_str = "\n\n".join(candidates_list)

    prompt = f"""
{SYSTEM_DOSSIER}

Recibes una lista de noticias tecnológicas recientes. Tu tarea es seleccionar la noticia más relevante y de mayor valor para escribir un artículo técnico en el blog de ai.maps.eus.

El blog está dirigido a desarrolladores e ingenieros de software interesados en WebGIS, PostGIS, pgrouting, pgvector, Django, bases de datos y desarrollo de software con IA.

=== Lista de Noticias Candidatas ===
{candidates_str}

Instrucciones:
1. Analiza cada noticia y evalúa qué tan relevante y útil es para nuestra audiencia y nuestro stack tecnológico (especialmente Django, PostgreSQL/PostGIS/pgvector, WebGIS, Python).
2. Selecciona el índice de la mejor noticia para realizar un tutorial técnico, explicación arquitectónica o caso de uso. Evita noticias demasiado genéricas o no técnicas (como noticias corporativas sencillas, resultados deportivos/loterías que mencionen la palabra IA).
3. Selecciona también hasta 3 índices de otras noticias de la lista que estén de alguna forma relacionadas con la principal (o que aporten valor complementario) para citarlas como lecturas recomendadas al final.

Devuelve estrictamente un objeto JSON con la siguiente estructura (sin bloques markdown ```json ni texto explicativo):
{{
  "selected_index": <int_indice_seleccionado>,
  "reason": "Explicación corta de 1 frase en castellano de por qué es la mejor opción",
  "related_indices": [<lista_de_indices_relacionados>]
}}
"""

    try:
        raw_response = _call_gemini_generate(prompt, max_output_tokens=500)
        clean_txt = raw_response.strip()
        if clean_txt.startswith("```"):
            clean_txt = clean_txt.split("\n", 1)[1] if "\n" in clean_txt else clean_txt
            if clean_txt.endswith("```"):
                clean_txt = clean_txt[:-3]
            clean_txt = clean_txt.strip()
            
        data = json.loads(clean_txt)
        sel_idx = int(data.get("selected_index", 0))
        if 0 <= sel_idx < len(candidates):
            selected = candidates[sel_idx].copy()
            related = []
            for r_idx in data.get("related_indices", []):
                try:
                    r_idx = int(r_idx)
                    if 0 <= r_idx < len(candidates) and r_idx != sel_idx:
                        related.append(candidates[r_idx])
                except (ValueError, TypeError):
                    continue
            selected["related_articles"] = related
            selected["selection_reason"] = data.get("reason", "")
            return selected
    except Exception as e:
        log.warning("Gemini article selection failed: %s. Falling back to the first candidate.", e)
        
    return candidates[0]

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
    # 1. Fetch news candidates
    candidates = fetch_latest_tech_news()
    if not candidates:
        log.error("Could not fetch any news or RSS articles to start daily blog generation.")
        return None

    # 2. Select the best article
    news = select_best_article_with_gemini(candidates)
    if not news:
        log.error("Could not select a news article to write the daily post.")
        return None

    # 3. Compile related articles string
    related_articles = news.get("related_articles", [])
    related_lines = []
    for r in related_articles:
        related_lines.append(f"- Título: {r['title']}\n  URL: {r['url']}")
    related_articles_str = "\n".join(related_lines) if related_lines else "(No hay artículos relacionados)"

    # 4. Get history
    history = get_recent_posts_history()

    # 5. Format prompt
    prompt = PROMPT_TEMPLATE.format(
        system_dossier=SYSTEM_DOSSIER,
        news_title=news["title"],
        news_snippet=news["snippet"],
        news_url=news["url"],
        selection_reason=news.get("selection_reason", "Relevancia técnica general"),
        related_articles_str=related_articles_str,
        history=history,
    )

    # 4. Call Gemini
    try:
        raw_response = _call_gemini_generate(prompt, max_output_tokens=6000)
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

    # Append news URL as a hidden comment for robust future deduplication
    content_es = data.get("content_es") or ""
    if news.get("url"):
        content_es += f"\n\n<!-- news_url: {news['url']} -->"

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
        content_es=content_es,
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
