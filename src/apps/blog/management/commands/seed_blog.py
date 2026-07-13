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
                "tag_slugs": ["django", "postgis", "pgrouting"],
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
                "tag_slugs": ["django", "pgvector", "gemini"],
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
                "tag_slugs": ["django", "docker", "cicd"],
            },
            {
                "category": categories["ai-workflows"],
                "author": author,
                "title_es": "La evolución del desarrollador de software: de picar código a orquestar arquitecturas con IA",
                "title_eu": "Software garatzailearen bilakaera: kodea idaztetik AI bidezko arkitekturak antolatzera",
                "title_en": "The Evolution of the Software Developer: From Writing Code to Orchestrating Architectures with AI",
                "slug_es": "evolucion-desarrollador-software-arquitecto-ia",
                "slug_eu": "software-garatzailearen-bilakaera-arkitekto-ia",
                "slug_en": "evolution-software-developer-architect-ai",
                "summary_es": "Un análisis profundo sobre la transición de escribir código de forma manual en maps.eus a orquestar con agentes de IA en ai.maps.eus, redefiniendo la ingeniería en torno al diseño, auditoría y robustez del pipeline de integración.",
                "summary_eu": "maps.eus gunean kodea eskuz idaztetik ai.maps.eus gunean AI agenteekin orkestratzera izandako trantsizioari buruzko azterketa sakona, ingeniaritza diseinuaren, ikuskaritzaren eta integrazio-hodiaren sendotasunaren inguruan birdefinituz.",
                "summary_en": "An in-depth analysis of transitioning from manual coding in maps.eus to orchestrating with AI agents in ai.maps.eus, redefining engineering around design, auditing, and pipeline robustness.",
                "content_es": """
<p>El rol de los que nos dedicamos a programar está cambiando a una velocidad increíble. Al menos a mí me ha dado un vuelco total en el último año. Y no hablo de teorías sobre el futuro del trabajo; hablo de algo real que he vivido en mis carnes al comparar cómo desarrollé mis proyectos personales: <strong>maps.eus</strong> y <strong>ai.maps.eus</strong>.</p>

<h2>El punto de partida: de Kulturmaps a la infraestructura real</h2>
<p>Cuando empecé con la primera versión de <strong>maps.eus</strong>, mi objetivo era modesto: quería montar <i>Kulturmaps</i> para presentar un proyecto al concurso de <strong>Open Data Euskadi</strong>. Por aquel entonces, yo no tenía ni idea de la existencia de <strong>PostGIS</strong> ni de bases de datos espaciales. Todo el desarrollo fue súper artesanal, picando cada vista y cada modelo a mano.</p>

<p>En ese momento, la IA era poco más que un buscador rápido en una pestaña del navegador para consultar dudas puntuales de sintaxis, como quien busca en StackOverflow. Yo escribía cada línea y sabía exactamente dónde iba cada coma. Al final, lo que me limitaba era el tiempo físico de teclear cada línea de código.</p>

<h2>El salto de calidad: reconstruir desde cero con la IA en el IDE</h2>
<p>El gran cambio empezó a finales del año pasado, cuando decidí reconstruir el proyecto desde cero utilizando Gemini directamente en mi entorno de desarrollo (IDE). La IA pasó de ser un simple buscador a convertirse en un compañero de aprendizaje activo. De hecho, fue la IA la que me propuso utilizar una mejor infraestructura para el proyecto (como PostGIS) y me ayudó paso a paso a implementarla.</p>

<p>La IA me está ayudando a ampliar mis horizontes, a aprender nuevas herramientas y a entender cómo funcionan por dentro las aplicaciones que utilizo habitualmente en mis rutas de viaje en bici. Juntos pudimos:</p>
<ul>
    <li>Montar toda la base de datos espacial, descubriendo cómo modelar redes viales para calcular rutas.</li>
    <li>Procesar e importar datos complejos de <strong>OpenStreetMap</strong>.</li>
    <li>Configurar toda la infraestructura con contenedores Docker (con Celery para tareas en segundo plano y Redis para la caché), algo que antes me habría llevado días de prueba y error.</li>
</ul>
<p>El resultado es que he levantado el motor completo de generación y visualización de rutas de bikepacking prácticamente sin teclear código a mano.</p>

<h2>El nuevo reto: que el código no se nos vaya de las manos</h2>
<p>Generar código rápido está muy bien, pero el peligro real ahora es perder el control y acabar con una "caja negra" que nadie entienda ni pueda mantener. Por eso, mi forma de trabajar ha cambiado por completo:</p>
<ol>
    <li><strong>Diseñar y modularizar mejor la arquitectura:</strong> Para que la generación de código no se descontrole, es vital tener claro el diseño a alto nivel y cómo estructurar el proyecto en módulos antes de pedirle nada a la IA. No es una tarea fácil, sobre todo cuando la IA propone un montón de cambios en muchos archivos a la vez. Cada día nos topamos con dificultades nuevas y vamos buscando la forma de mejorar.</li>
    <li><strong>El aprendizaje de la auditoría y revisión (Code Review):</strong> Si antes revisábamos pequeños cambios manuales, ahora un agente de IA puede modificar decenas de archivos en un instante. Todavía no somos capaces de leer de forma crítica y con total seguridad todo lo que se genera. Estamos aprendiendo a trabajar con la IA y buscando métodos para que el código generado sea confiable: probamos <strong>Specs-Driven Development</strong>, generamos tests sobre el código resultante, utilizamos la IA para documentar el código de forma interactiva y aprendemos nuevas herramientas como <strong>OpenSpec</strong>.</li>
    <li><strong>Automatizar tests y CI/CD:</strong> Confiar a ciegas en el código generado por una IA es jugar con fuego. Para mantener la calma, la clave es apoyar al máximo nuestro pipeline de integración continua (CI/CD). La IA también nos ayuda a mejorar en la generación de tests y en preparar scripts de auditoría automática que comprueben en segundos que nada se ha roto.</li>
</ol>

<h2>Proyectos personales frente a entornos reales</h2>
<p>Los proyectos personales y los laboratorios son el sitio ideal para trastear y ver qué pueden hacer estos modelos (como Claude, que ahora mismo me parece que da soluciones de código más sólidas y coherentes que Gemini). Ahí, meter la pata es parte del juego.</p>

<p>Pero en el mundo real, trabajando en equipo, con datos sensibles y con exigencias serias de rendimiento y seguridad, la película es muy distinta. No basta con hacer las cosas rápido; hay que hacerlas bien. La IA nos ayuda a programar, pero hace más falta que nunca tener ingenieros que entiendan la arquitectura, aseguren el código y controlen la infraestructura de verdad.</p>
""",
                "content_eu": """
<p>Garatzaileon rola abiadura sinestezinean aldatzen ari da. Niri behintzat, azken urtean bizitza aldatu dit nire lan egiteko moduak. Eta ez naiz lanaren etorkizunari buruzko teoria abstraktuez ari; nire haragian bizi izan dudan errealitate bat da, nire proiektu pertsonalak nola garatu nituen alderatzean: <strong>maps.eus</strong> eta <strong>ai.maps.eus</strong>.</p>

<h2>Hasierako puntua: Kulturmapsetik benetako azpiegiturara</h2>
<p><strong>maps.eus</strong>-en lehen bertsioarekin hasi nintzenean, helburua xumea zen: <i>Kulturmaps</i> atala sortu nahi nuen <strong>Open Data Euskadi</strong> lehiaketara aurkezteko. Garai hartan, ez nekien <strong>PostGIS</strong> edo datu-base espazialak existitzen zirenik ere. Garapen guztia super artisaua izan zen, ikuspegi eta modelo bakoitza eskuz idatziz.</p>

<p>Une horretan, AIa bilatzaile azkar bat baino ez zen nabigatzaileko fitxa batean, sintaxi zalantza zehatzat argitzeko, StackOverflow-ra jotzea bezala. Nik idazten nuen lerro bakoitza eta banekien zehazki koma bakoitza nora zihoan. Azkenean, nire muga fisikoa kode lerro bakoitza idazteko abiadura zen.</p>

<h2>Jauzi kualitatiboa: proiektua hutsetik berreraikitzea AIarekin IDEan</h2>
<p>Aldaketa handia iazko urte amaieran hasi zen, proiektua hutsetik berreraikitzea erabaki nuenean, Gemini zuzenean nire garapen ingurunean (IDE) erabiliz. AIa bilatzaile soil bat izatetik ikaskuntza kide aktibo izatera igaro zen. Izan ere, AIak berak proposatu zidan azpiegitura hobe bat erabiltzea (PostGIS bezala) eta urratsez urrats inplementatzen lagundu zidan.</p>

<p>AIa nire mugak zabaltzen, tresna berriak ikasten eta nire bizikleta ibilaldietan erabiltzen ditudan aplikazioak barnetik nola funtzionatzen duten ulertzen laguntzen ari zait. Elkarrekin hau egiteko gai izan ginen:</p>
<ul>
    <li>Datu-base espazial osoa muntatu, ibilbideak kalkulatzeko errepide-sareak nola modelatu daitezkeen ikasiz.</li>
    <li><strong>OpenStreetMap</strong>eko datu konplexuak prozesatu eta inportatu.</li>
    <li>Azpiegitura guztia Docker edukiontziekin konfiguratu (Celery atzeko lanetarako eta Redis katxerako), lehen saiakuntza-errore bidez egunak edo asteak eramango zizkidan zerbait.</li>
</ul>
<p>Ondorioz, bikepacking ibilbideak sortzeko eta bistaratzeko motor osoa altxatu dut, ia kode lerrorik eskuz idatzi gabe.</p>

<h2>Erronka berria: kodea kontrolpetik ez ihes egitea</h2>
<p>Kodea azkar sortzea oso ondo dago, pero benetako arriskua kontrola galtzea eta inork ulertzen edo mantentzen ez duen "kutxa beltz" batekin amaitzea da. Hori dela eta, nire lan egiteko modua erabat aldatu da:</p>
<ol>
    <li><strong>Arkitektura hobeto diseinatu eta modularizatu:</strong> Kode sorkuntza desantolatu ez dadin, funtsezkoa da goi-mailako diseinua eta proiektua modulutan nola egituratu argi izatea AIari ezer eskatu aurretik. Ez da lan erraza, batez ere AIak fitxategi askotan aldaketa pila bat proposatzen dituenean aldi berean. Egunero topatzen ditugu zailtasun berriak eta hobetzeko moduak bilatzen ari gara.</li>
    <li><strong>Ikuskaritza eta berrikuspenaren ikasketa (Code Review):</strong> Lehen eskuz egindako aldaketa txikiak berrikusten bagenituen, orain AI agente batek dozenaka fitxategi alda ditzake une batean. Oraindik ez gara gai sortzen den guztia modu kritikoan eta segurtasun osoz irakurtzeko. AIarekin elkarlanean ikasen ari gara eta sortutako kodea fidagarria izateko metodoak bilatzen ditugu: <strong>Specs-Driven Development</strong> probatzen ari gara, sortutako kodearen gainean testak definitzen, AI bera kodea modu interaktiboan dokumentatzeko erabiltzen eta tresna berriak ikasten, hala nola <strong>OpenSpec</strong>.</li>
    <li><strong>Testak eta CI/CD automatizatu:</strong> AIak sortutako kodean itsu-itsuan fidatzea suarekin jolastea da. Lasai egoteko, gakoa gure integrazio jarraituko (CI/CD) pipelinea ahalik ahalik eta gehien indartzea da. AIak testak sortzen laguntzen digu, baita segundotan ezer hautsi ez dela egiaztatuko duten auditoretza automatikoko gidoiak prestatzen ere.</li>
</ol>

<h2>Proiektu pertsonalak vs. benetako inguruneak</h2>
<p>Proiektu pertsonalak eta laborategiak leku bikainak dira eredu hauekin jolasteko eta zer egiteko gai diren ikusteko (Claude adibidez, nire ustez Gemini baino kode irtenbide sendoagoak eta koherenteagoak ematen dituena). Hor, hanka sartzea jokoaren parte da.</p>
""",
                "content_en": """
<p>The role of developers is changing at an incredible speed. At least for me, it has completely turned around in the past year. And I'm not talking about abstract theories about the future of work; I'm talking about a tangible reality I've experienced firsthand comparing how I built my personal projects: <strong>maps.eus</strong> and <strong>ai.maps.eus</strong>.</p>

<h2>The Starting Point: From Kulturmaps to Real Infrastructure</h2>
<p>When I first started developing <strong>maps.eus</strong>, my goal was modest: I wanted to build the <i>Kulturmaps</i> section for a competition by <strong>Open Data Euskadi</strong>. Back then, I had no idea PostGIS or spatial databases even existed. The whole development was super handcrafted, coding every view and model manually.</p>

<p>At that time, AI was little more than a quick search tool in a browser tab to resolve syntax doubts, similar to using StackOverflow. I wrote every line and knew exactly where every comma went. In the end, my main bottleneck was the physical limit of typing each line of code.</p>

<h2>The Qualitative Leap: Rebuilding From Scratch with AI in the IDE</h2>
<p>The big shift started late last year when I decided to rebuild the project from scratch using Gemini directly in my IDE (development environment). The AI evolved from a simple search tool into an active learning partner. In fact, it was the AI that suggested using a better infrastructure (like PostGIS) and helped me implement it step by step.</p>

<p>AI is helping me broaden my horizons, learn new tools, and understand how the applications I use on my bike trips actually work under the hood. Together we were able to:</p>
<ul>
    <li>Set up the entire spatial database, discovering how to model road networks for routing.</li>
    <li>Process and import complex datasets from <strong>OpenStreetMap</strong>.</li>
    <li>Configure the entire containerized infrastructure using Docker (with Celery for background tasks and Redis for caching), which previously would have taken me days of trial and error.</li>
</ul>
<p>The result is that I built the complete engine for route generation and visualization for bikepacking without manually writing almost any code.</p>

<h2>The New Challenge: Keeping Code from Spinning Out of Control</h2>
<p>Generating code quickly is great, but the real danger now is losing control and ending up with a "black box" that nobody understands or can maintain. Because of this, my way of working has completely changed:</p>
<ol>
    <li><strong>Designing and Modularizing Architecture Better:</strong> To keep code generation from getting out of hand, it is vital to have a clear high-level design and structure the project into modules before asking the AI for anything. It is not an easy task, especially when the AI proposes a lot of changes across many files at once. Every day we face new difficulties and implement new improvements.</li>
    <li><strong>The learning curve of code reviews and auditing (Code Review):</strong> If we previously reviewed small manual changes, now an AI agent can modify dozens of files in an instant. We are not yet capable of critically reading and verifying everything that is generated. Instead, we are learning to collaborate with the AI, searching for methods to make the generated code trustworthy: we are experimenting with <strong>Specs-Driven Development</strong>, writing targeted tests for the generated output, utilizing the AI itself to interactively document the code, and learning new tools like <strong>OpenSpec</strong>.</li>
    <li><strong>Automating Tests and CI/CD:</strong> Blindly trusting AI-generated code is playing with fire. To keep our sanity, the key is to strengthen our continuous integration (CI/CD) pipelines. AI also helps us improve test generation and set up automated audit scripts that verify in seconds that nothing is broken.</li>
</ol>

<h2>Side Projects vs. Real-World Environments</h2>
<p>Personal projects and labs are the perfect sandbox to play around and see what these models can do (like Claude, which currently feels like it provides more robust and coherent code solutions than Gemini). Here, making mistakes is part of the game.</p>

<p>However, in the real world—working in a team, with sensitive data, under strict security and performance requirements—it is a completely different story. It is not just about building fast; it is about building reliably. AI changes how we program, but it makes engineers who understand architecture, secure the code, and truly control the infrastructure more necessary than ever.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 5,
                "difficulty": "intermediate",
                "likes": 42,
                "tag_slugs": ["django", "gemini", "cicd"],
            },
        ]

        for pdata in posts_data:
            tag_slugs = pdata.pop("tag_slugs", ["django"])
            ptags = [tags[slug] for slug in tag_slugs if slug in tags]

            slug_es = pdata["slug_es"]
            title_es = pdata["title_es"]

            # Try to find existing post by slug_es or title_es
            post = Post.objects.filter(slug_es=slug_es).first()
            if not post:
                post = Post.objects.filter(title_es=title_es).first()

            if post:
                # Update existing post, preserving likes and original published_at if already set
                original_published_at = post.published_at or pdata.get("published_at")
                original_likes = max(post.likes, pdata.get("likes", 0))

                for key, val in pdata.items():
                    setattr(post, key, val)

                post.published_at = original_published_at
                post.likes = original_likes
                post.save()
                created = False
            else:
                # Create a new post
                post = Post.objects.create(**pdata)
                created = True

            post.tags.set(ptags)
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} Post: {post.title}")

        self.stdout.write(self.style.SUCCESS("Blog successfully seeded!"))
