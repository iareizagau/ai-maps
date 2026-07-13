import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.blog.models import Category, Tag, Post

User = get_user_model()


class Command(BaseCommand):
    help = "Seed initial blog categories, tags, and technical articles"

    def handle(self, *args, **options):
        # 1. Get or create author (preferably superuser)
        author = User.objects.filter(is_superuser=True).first()
        if not author:
            author = User.objects.first()
        if not author:
            author = User.objects.create_user(
                username="admin",
                email="admin@maps.eus",
                password="adminpassword",
                is_staff=True,
                is_superuser=True,
            )
            self.stdout.write("Created admin superuser.")

        # 2. Seed Categories
        categories_data = [
            {
                "slug": "backend-architecture",
                "name_es": "Backend y Arquitectura",
                "name_eu": "Backend eta Arkitektura",
                "name_en": "Backend & Architecture",
            },
            {
                "slug": "webgis-postgis",
                "name_es": "Geo-Desarrollo y WebGIS",
                "name_eu": "Geo-Garapena eta WebGIS",
                "name_en": "Geo-Development & WebGIS",
            },
            {
                "slug": "ai-workflows",
                "name_es": "IA y Flujos de Trabajo",
                "name_eu": "AI eta Lan-Fluxuak",
                "name_en": "AI & Workflows",
            },
            {
                "slug": "platform-updates",
                "name_es": "Novedades de la Plataforma",
                "name_eu": "Plataformako Berriak",
                "name_en": "Platform Updates",
            },
        ]

        categories = {}
        for cdata in categories_data:
            cat, created = Category.objects.update_or_create(
                slug=cdata["slug"], defaults=cdata
            )
            categories[cdata["slug"]] = cat
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} Category: {cat.name}")

        # 3. Seed Tags
        tags_data = [
            {
                "slug": "django",
                "name_es": "Django",
                "name_eu": "Django",
                "name_en": "Django",
            },
            {
                "slug": "postgis",
                "name_es": "PostGIS",
                "name_eu": "PostGIS",
                "name_en": "PostGIS",
            },
            {
                "slug": "pgrouting",
                "name_es": "pgRouting",
                "name_eu": "pgRouting",
                "name_en": "pgRouting",
            },
            {
                "slug": "pgvector",
                "name_es": "pgvector",
                "name_eu": "pgvector",
                "name_en": "pgvector",
            },
            {
                "slug": "docker",
                "name_es": "Docker",
                "name_eu": "Docker",
                "name_en": "Docker",
            },
            {
                "slug": "gemini",
                "name_es": "Gemini AI",
                "name_eu": "Gemini AI",
                "name_en": "Gemini AI",
            },
            {
                "slug": "cicd",
                "name_es": "CI/CD",
                "name_eu": "CI/CD",
                "name_en": "CI/CD",
            },
        ]

        tags = {}
        for tdata in tags_data:
            tag, created = Tag.objects.update_or_create(
                slug=tdata["slug"], defaults=tdata
            )
            tags[tdata["slug"]] = tag
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} Tag: {tag.name}")

        # Mock GeoJSON path representing a route around Vitoria-Gasteiz
        vitoria_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Ruta de prueba"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-2.6725, 42.8465],
                            [-2.6705, 42.8485],
                            [-2.6685, 42.8505],
                            [-2.6720, 42.8530],
                        ],
                    },
                }
            ],
        }

        # 4. Seed Posts
        posts_data = [
            {
                "category": categories["webgis-postgis"],
                "author": author,
                "title_es": "Optimización Geográfica con PostGIS y pgRouting en Django",
                "title_eu": "Geografia optimizazioa PostGIS eta pgRouting-ekin Django-n",
                "title_en": "Geographical Optimization with PostGIS and pgRouting in Django",
                "slug_es": "optimizacion-geografica-postgis-pgrouting-django",
                "slug_eu": "geografia-optimizazioa-postgis-pgrouting-django",
                "slug_en": "geographical-optimization-postgis-pgrouting-django",
                "summary_es": "Cómo resolver problemas de rutas óptimas (bikepacking, rutas ciclistas o de vehículos) utilizando las capacidades espaciales del motor PostgreSQL.",
                "summary_eu": "Nola ebatzi ibilbide optimoen arazoak (bikepacking-a, txirrindularitza edo ibilgailuen ibilbideak) PostgreSQL motorraren gaitasun espazialak erabiliz.",
                "summary_en": "How to solve optimal routing problems (bikepacking, cycling paths, or vehicle routing) utilizing the spatial capabilities of the PostgreSQL engine.",
                "content_es": """
<p>En el desarrollo de aplicaciones <strong>WebGIS</strong> avanzadas, a menudo nos enfrentamos al desafío de calcular rutas óptimas sobre una red de carreteras, senderos o carriles bici. Si bien servicios externos como OSRM o Google Maps son útiles, delegar esta lógica a la base de datos con <strong>pgRouting</strong> nos da control absoluto y velocidad.</p>

<h3>¿Qué es pgRouting?</h3>
<p>pgRouting es una extensión de PostgreSQL y PostGIS que añade funcionalidades de teoría de grafos y cálculo de rutas. Utiliza algoritmos clásicos como <i>Dijkstra</i>, <i>A*</i> y <i>Shooting Star</i> directamente sobre geometrías vectoriales.</p>

<h3>Un ejemplo práctico en Django</h3>
<p>Para buscar la ruta más corta entre dos puntos en una red vial estructurada, podemos realizar una consulta directa SQL usando cursores nativos en Django:</p>

<pre><code>from django.db import connection

def get_shortest_path(start_lon, start_lat, end_lon, end_lat):
    query = \"\"\"
        SELECT seq, node, edge, cost, agg_cost, geom
        FROM pgr_dijkstra(
            'SELECT id, source, target, cost_s AS cost, reverse_cost_s AS reverse_cost FROM ways',
            %s, %s, false
        ) AS path
        JOIN ways ON path.edge = ways.id
    \"\"\"
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node, end_node])
        return cursor.fetchall()
</code></pre>

<p>Esta integración nos permite combinar la lógica de bases de datos relacionales con cartografía interactiva en el navegador, logrando aplicaciones eficientes que no dependen de APIs de terceros.</p>
""",
                "content_eu": """
<p><strong>WebGIS</strong> aplikazio aurreratuen garapenean, sarritan errepide, bide edo bidegorri sare baten gainean ibilbide optimoak kalkulatzeko erronkari aurre egin behar diogu. Kanpoko zerbitzuak erabilgarriak badira ere, logika hori <strong>pgRouting</strong> bidez datu-baseari eskuordetzeak erabateko kontrola eta abiadura ematen digu.</p>

<h3>Zer da pgRouting?</h3>
<p>pgRouting PostgreSQL eta PostGISen luzapena da, grafoen teoria eta ibilbideen kalkulua gehitzen dituena. <i>Dijkstra</i> bezalako algoritmo klasikoak erabiltzen ditu zuzenean geometria bektorialen gainean.</p>
""",
                "content_en": """
<p>In advanced <strong>WebGIS</strong> application development, we often face the challenge of calculating optimal routes over a road network. While external services are useful, delegating this logic to the database with <strong>pgRouting</strong> gives us absolute control and speed.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 6,
                "difficulty": "intermediate",
                "map_geojson": json.dumps(vitoria_geojson),
                "map_center_lat": 42.8485,
                "map_center_lng": -2.6705,
                "map_zoom": 14,
                "likes": 12,
            },
            {
                "category": categories["ai-workflows"],
                "author": author,
                "title_es": "Búsqueda Semántica RAG con pgvector y la API de Gemini",
                "title_eu": "RAG Bilaketa Semantikoa pgvector eta Gemini API-rekin",
                "title_en": "Semantic RAG Search with pgvector and Gemini API",
                "slug_es": "busqueda-semantica-rag-pgvector-gemini",
                "slug_eu": "rag-bilaketa-semantikoa-pgvector-gemini",
                "slug_en": "semantic-rag-search-pgvector-gemini",
                "summary_es": "Implementación de un sistema de generación aumentada por recuperación (RAG) en Django usando embeddings de Gemini y almacenamiento vectorial en Postgres.",
                "summary_eu": "Berreskuratze bidez areagotutako belaunaldi (RAG) sistema baten inplementazioa Django-n, Gemini txertaketak (embeddings) eta Postgres-en bektore biltegiratzea erabiliz.",
                "summary_en": "Implementing a Retrieval-Augmented Generation (RAG) system in Django using Gemini embeddings and vector storage in PostgreSQL.",
                "content_es": """
<p>El auge de los modelos de lenguaje (LLM) ha popularizado la técnica <strong>RAG</strong> (Retrieval-Augmented Generation), que dota al modelo de contexto local actualizado para responder preguntas sin necesidad de reentrenarlo.</p>

<h3>¿Por qué pgvector?</h3>
<p>PostgreSQL nos permite almacenar representaciones vectoriales (embeddings) de nuestros datos gracias a la extensión <strong>pgvector</strong>. Esto significa que podemos realizar búsquedas por similitud de coseno en la misma base de datos relacional donde guardamos los usuarios o mapas.</p>

<pre><code># Ejemplo de consulta con pgvector en Django
from pgvector.django import CosineDistance
from .models import Document

def search_documents(query_vector, limit=5):
    return Document.objects.annotate(
        distance=CosineDistance("embedding", query_vector)
    ).order_by("distance")[:limit]
</code></pre>

<p>Al pasar estos fragmentos recuperados a la API de Gemini, el modelo formula respuestas altamente precisas y fundamentadas en nuestros propios textos.</p>
""",
                "content_eu": """
<p>LLM ereduen eztandak <strong>RAG</strong> (Retrieval-Augmented Generation) teknika ezagun egin du. Teknika honek testuinguru eguneratua eskaintzen dio ereduari galderak erantzuteko, berriro entrenatu beharrik gabe.</p>
""",
                "content_en": """
<p>The rise of LLMs has popularized the <strong>RAG</strong> technique, which provides the model with updated local context to answer questions without retraining.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 8,
                "difficulty": "advanced",
                "map_center_lat": 43.2630,
                "map_center_lng": -2.9350,
                "map_zoom": 12,
                "likes": 24,
            },
            {
                "category": categories["backend-architecture"],
                "author": author,
                "title_es": "Pipelines CI/CD Eficientes para Django en Contenedores",
                "title_eu": "CI/CD Pipeline Eraginkorrak Django-rentzat Edukiontzietan",
                "title_en": "Efficient CI/CD Pipelines for Containerized Django",
                "slug_es": "pipelines-cicd-django-contenedores",
                "slug_eu": "cicd-pipeline-django-edukiontzietan",
                "slug_en": "cicd-pipelines-django-containers",
                "summary_es": "Cómo estructurar el Dockerfile y las acciones de GitHub para lograr despliegues rápidos, seguros y deterministas utilizando uv.",
                "summary_eu": "Nola egituratu Dockerfile eta GitHub Actions inplementazio azkar, seguru eta deterministak lortzeko uv erabiliz.",
                "summary_en": "How to structure the Dockerfile and GitHub Actions to achieve fast, secure, and deterministic deployments using uv.",
                "content_es": """
<p>El despliegue continuo (CD) no tiene por qué ser lento. Al optimizar nuestras imágenes Docker y centralizar las comprobaciones en pipelines automáticos, reducimos la fricción en el desarrollo técnico diario.</p>

<h3>Optimización con uv</h3>
<p>Sustituir <i>pip</i> por <strong>uv</strong> en el proceso de compilación de Docker acelera radicalmente la instalación de dependencias y asegura un entorno determinista mediante la validación estricta de lockfiles.</p>
""",
                "content_eu": """
<p>Inplementazio jarraitua ez da zertan motela izan. Gure Docker irudiak optimizatuz, garapenaren marruskadura murrizten dugu.</p>
""",
                "content_en": """
<p>Continuous deployment doesn't have to be slow. By optimizing our Docker images, we reduce daily development friction.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 4,
                "difficulty": "beginner",
                "likes": 7,
            },
        ]

        for pdata in posts_data:
            ptags = [tags["django"]]
            if "postgis" in pdata["slug_es"]:
                ptags.extend([tags["postgis"], tags["pgrouting"]])
            elif "vector" in pdata["slug_es"]:
                ptags.extend([tags["pgvector"], tags["gemini"]])
            else:
                ptags.extend([tags["docker"], tags["cicd"]])

            post, created = Post.objects.update_or_create(
                slug_es=pdata["slug_es"], defaults=pdata
            )
            post.tags.set(ptags)
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} Post: {post.title}")

        self.stdout.write(self.style.SUCCESS("Blog successfully seeded!"))
