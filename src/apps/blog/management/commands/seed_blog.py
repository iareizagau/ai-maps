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
            {
                "slug": "celery",
                "name_es": "Celery",
                "name_eu": "Celery",
                "name_en": "Celery",
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

        # Mock GeoJSON representing a low emission zone polygon in Vitoria-Gasteiz (ZBE)
        zbe_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Zona de Bajas Emisiones (ZBE) Centro"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-2.6780, 42.8430],
                                [-2.6640, 42.8430],
                                [-2.6640, 42.8530],
                                [-2.6780, 42.8530],
                                [-2.6780, 42.8430]
                            ]
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
                "summary_es": "Cómo resolver problemas de rutas óptimas (bikepacking y aventura) en Euskadi utilizando pgRouting y PostGIS en la aplicación ai.maps.eus/adventure/.",
                "summary_eu": "Nola ebatzi bikepacking eta abentura ibilbide optimoen arazoak Euskadin, pgRouting eta PostGIS erabiliz ai.maps.eus/adventure/ aplikazioan.",
                "summary_en": "How to solve optimal bikepacking and adventure routing problems in Euskadi using pgRouting and PostGIS at ai.maps.eus/adventure/.",
                "content_es": """
<p>En el desarrollo de aplicaciones <strong>WebGIS</strong> avanzadas, a menudo nos enfrentamos al desafío de calcular rutas óptimas sobre una red de carreteras, senderos o carriles bici. Si bien servicios externos como OSRM, GraphHopper o Google Maps son útiles, delegar esta lógica a la base de datos con <strong>pgRouting</strong> nos proporciona un control absoluto de los costes de ruta y una velocidad de ejecución extraordinaria.</p>

<h3>¿Qué es pgRouting?</h3>
<p>pgRouting es una extensión para PostgreSQL y PostGIS que añade funciones de teoría de grafos y cálculo de rutas. Utiliza algoritmos clásicos como <i>Dijkstra</i>, <i>A*</i> o <i>TSP (Traveling Salesperson Problem)</i> directamente sobre geometrías vectoriales. Al ejecutarse en la propia base de datos, podemos modificar dinámicamente los factores de coste de las vías (pendientes, tipo de superficie, seguridad) mediante simples consultas SQL.</p>

<h3>Caso de éxito: El planificador de aventuras en ai.maps.eus</h3>
<p>Hemos implementado esta tecnología de forma end-to-end en nuestro planificador de rutas de bikepacking y aventura en <a href="https://ai.maps.eus/adventure/" target="_blank">ai.maps.eus/adventure/</a>. Esta aplicación permite a los ciclistas calcular itinerarios a través de una red topológica compleja de caminos en Euskadi.</p>

<p>Para buscar la ruta más corta o de menor esfuerzo entre dos puntos de nuestra red vial, realizamos consultas usando las funciones de pgRouting. Aquí tienes un ejemplo de cómo integramos la llamada a <code>pgr_dijkstra</code> en Django:</p>

<pre><code>from django.db import connection

def get_shortest_path(start_node_id, end_node_id):
    # La consulta SQL llama a pgr_dijkstra sobre la tabla 'ways'
    query = \"\"\"
        SELECT seq, node, edge, cost, agg_cost, ST_AsGeoJSON(geom) as geojson
        FROM pgr_dijkstra(
            'SELECT id, source, target, length_m AS cost, reverse_cost_m AS reverse_cost FROM ways',
            %s, %s, false
        ) AS path
        JOIN ways ON path.edge = ways.id
        ORDER BY seq;
    \"\"\"
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node_id, end_node_id])
        return cursor.fetchall()
</code></pre>

<p>Esta aproximación no solo elimina dependencias externas costosas, sino que nos permite personalizar el trazado en base a filtros de usuario (como evitar carreteras principales o priorizar pistas forestales), calculando la ruta óptima directamente sobre nuestro dataset de OpenStreetMap y mostrándola interactivamente al usuario.</p>
""",
                "content_eu": """
<p><strong>WebGIS</strong> aplikazio aurreratuen garapenean, sarritan errepide, bide edo bidegorri sare baten gainean ibilbide optimoak kalkulatzeko erronkari aurre egin behar diogu. Kanpoko zerbitzuak erabilgarriak badira ere, logika hori <strong>pgRouting</strong> bidez datu-baseari eskuordetzeak erabateko kontrola eta abiadura ematen digu.</p>

<h3>Zer da pgRouting?</h3>
<p>pgRouting PostgreSQL eta PostGISen luzapena da, grafoen teoria eta ibilbideen kalkulua gehitzen dituena. <i>Dijkstra</i> bezalako algoritmo klasikoak erabiltzen ditu zuzenean geometria bektorialen gainean.</p>

<h3>Inplementazio erreal bat: ai.maps.eus/adventure/</h3>
<p>Teknologia hau gure bikepacking eta abentura ibilbideen planifikatzailean inplementatu dugu: <a href="https://ai.maps.eus/adventure/" target="_blank">ai.maps.eus/adventure/</a>. Aplikazio honi esker, txirrindulariek ibilbide optimoak kalkula ditzakete Euskadiko bide-sare konplexu baten gainean, bideen ezaugarri zehatzak kontuan hartuta (zailtasuna, bide mota, etab.) eta emaitza interaktiboki Leaflet bidez bistaratuz.</p>
""",
                "content_en": """
<p>In advanced <strong>WebGIS</strong> application development, we often face the challenge of calculating optimal routes over a road or trail network. While external routing services (like Google Maps or OSRM) are common, delegating routing computations directly to the database with <strong>pgRouting</strong> grants us absolute control over cost functions and exceptional response times.</p>

<h3>What is pgRouting?</h3>
<p>pgRouting is a PostgreSQL extension that extends PostGIS to provide graph-theory routing capabilities. It allows you to run algorithms like <i>Dijkstra</i>, <i>A*</i>, or <i>TSP (Traveling Salesperson Problem)</i> directly on spatial database tables. Since the network data is stored in the database, we can dynamically adjust edge costs based on slopes, surface types, or safety criteria using SQL.</p>

<h3>Production Case: The Adventure Planner at ai.maps.eus</h3>
<p>We put this technology into practice in our custom bikepacking and gravel route planner at <a href="https://ai.maps.eus/adventure/" target="_blank">ai.maps.eus/adventure/</a>. This application enables cyclists to calculate routes across a topological trail network in Euskadi.</p>

<p>To find the path between two coordinate points, the backend finds the nearest network nodes and runs <code>pgr_dijkstra</code>. Here is how we execute the query using Django's raw connection cursor:</p>

<pre><code>from django.db import connection

def get_shortest_path(start_node_id, end_node_id):
    query = \"\"\"
        SELECT seq, node, edge, cost, agg_cost, ST_AsGeoJSON(geom) as geojson
        FROM pgr_dijkstra(
            'SELECT id, source, target, length_m AS cost, reverse_cost_m AS reverse_cost FROM ways',
            %s, %s, false
        ) AS path
        JOIN ways ON path.edge = ways.id
        ORDER BY seq;
    \"\"\"
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node_id, end_node_id])
        return cursor.fetchall()
</code></pre>

<p>This approach completely eliminates dependencies on third-party APIs and allows us to perform real-time routing based on custom criteria (e.g. prioritizing dirt roads over highways) directly on OpenStreetMap datasets.</p>
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
                "summary_es": "Cómo construimos un asistente conversacional de movilidad utilizando pgvector y embeddings de Gemini en la aplicación Mubil.",
                "summary_eu": "Nola eraikitzen dugun mugikortasuneko txat-laguntzaile adimenduna pgvector eta Gemini bektoreak erabiliz Mubil aplikazioan.",
                "summary_en": "How we built a conversational mobility assistant using pgvector and Gemini embeddings in the Mubil application.",
                "content_es": """
<p>El auge de los modelos de lenguaje (LLM) ha popularizado la técnica <strong>RAG</strong> (Retrieval-Augmented Generation), que dota al modelo de contexto local actualizado para responder preguntas sin necesidad de reentrenarlo. En lugar de confiar únicamente en el conocimiento general del modelo, buscamos en nuestra base de datos los textos más relevantes para la pregunta del usuario y se los enviamos al LLM como contexto de fondo.</p>

<h3>¿Por qué pgvector en PostgreSQL?</h3>
<p>La extensión <strong>pgvector</strong> convierte a nuestra base de datos relacional de confianza en una base de datos vectorial de alto rendimiento. En lugar de mantener una base de datos vectorial externa (como Pinecone o Chroma) que añadiría complejidad y latencia a nuestra infraestructura, podemos almacenar los vectores de características (embeddings) directamente en tablas PostgreSQL y ejecutar búsquedas de similitud coseno o distancia euclídea mediante consultas SQL tradicionales.</p>

<pre><code># Ejemplo de búsqueda de similitud coseno en Django con pgvector
from pgvector.django import CosineDistance
from .models import DocumentChunk

def get_relevant_context(query_vector, limit=5):
    return DocumentChunk.objects.annotate(
        distance=CosineDistance("embedding", query_vector)
    ).order_by("distance")[:limit]
</code></pre>

<h3>Caso de éxito real: El asistente "Ask" en la App Mubil</h3>
<p>Hemos aplicado esta arquitectura de forma práctica en el desarrollo de la aplicación <strong>Mubil</strong> dentro de la plataforma. La sección <strong>Mubil Ask</strong> cuenta con un chat inteligente diseñado para resolver dudas sobre movilidad eléctrica, puntos de recarga, tarifas eléctricas (PVPC) y subvenciones gubernamentales (como el Plan Auto+ o MOVES III).</p>

<p>El flujo del sistema funciona de la siguiente manera:</p>
<ol>
    <li><strong>Indexación:</strong> Procesamos documentos oficiales de movilidad y normativas, los dividimos en fragmentos manejables y generamos sus embeddings usando la API de Gemini (modelo <code>text-embedding-004</code>). Estos vectores se guardan en la base de datos PostgreSQL utilizando <code>pgvector</code>.</li>
    <li><strong>Recuperación semántica:</strong> Cuando un usuario hace una pregunta en el chat, convertimos la consulta en un vector y buscamos los fragmentos con menor distancia de coseno en la base de datos.</li>
    <li><strong>Generación:</strong> Enviamos los fragmentos recuperados como contexto a Gemini, que redacta una respuesta coherente, veraz y totalmente personalizada basada en los datos específicos de movilidad de Euskadi.</li>
</ol>

<p>Esta integración reduce a cero las alucinaciones del modelo y nos permite ofrecer respuestas confiables y actualizadas sin añadir costes de infraestructura significativos.</p>
""",
                "content_eu": """
<p>Hizkuntza-eredu handien (LLM) eztandak <strong>RAG</strong> (Retrieval-Augmented Generation) teknika ezagun egin du. Teknika honek testuinguru eguneratua eskaintzen dio ereduari galderak erantzuteko, berriro entrenatu beharrik gabe. Ereduaren ezagutza orokorrean soilik fidatu beharrean, gure datu-basean erabiltzailearen galderarako testu garrantzitsuenak bilatzen ditugu eta LLMari bidaltzen dizkiogu testuinguru gisa.</p>

<h3>Zergatik pgvector PostgreSQL-n?</h3>
<p><strong>pgvector</strong> luzapenak gure PostgreSQL datu-basea errendimendu handiko datu-base bektorial bihurtzen du. Kanpoko datu-base bektorial bat mantendu beharrean (Pinecone edo Chroma adibidez), bektoreak (embeddings) zuzenean gorde ditzakegu PostgreSQL tauletan eta antzekotasun-bilaketak SQL kontsulta tradizionalen bidez exekutatu.</p>

<h3>Adibide praktikoa: Mubil Aplikazioko "Ask" laguntzailea</h3>
<p>Arkitektura hau modu praktikoan aplikatu dugu gure plataformako <strong>Mubil</strong> aplikazioaren garapenean. Zehazki, <strong>Mubil Ask</strong> atalak chat adimendun bat du, mugikortasun elektrikoari, karga-puntuei, argindar tarifei (PVPC) eta gobernuaren dirulaguntzei (Plan Auto+ edo MOVES III kasu) buruzko zalantzak argitzeko.</p>

<p>Sistemaren lan-fluxua honako hau da:</p>
<ol>
    <li><strong>Indexazioa:</strong> Mugikortasuneko dokumentu ofizialak prozesatu, zati txikitan banatu eta haien bektoreak sortzen ditugu Gemini APIa erabiliz. Bektore horiek PostgreSQL-n gordetzen dira <code>pgvector</code> luzapenarekin.</li>
    <li><strong>Bilaketa semantikoa:</strong> Erabiltzaileak galdera bat egiten duenean, galdera hori bektore bihurtu eta datu-basean antzekoen diren zatiak berreskuratzen ditugu.</li>
    <li><strong>Belaunaldia:</strong> Berreskuratutako zatiak testuinguru gisa bidaltzen dizkiogu Geminiri, eta honek erantzun fidagarria sortzen du, Euskadiko mugikortasun datu zehatzetan oinarrituta.</li>
</ol>
""",
                "content_en": """
<p>The rise of Large Language Models (LLMs) has popularized the <strong>RAG</strong> (Retrieval-Augmented Generation) pattern. RAG provides the model with domain-specific, real-time context to answer user queries without the need for model retraining. Instead of relying solely on the LLM's pre-trained knowledge, we fetch the most relevant text chunks from our database and inject them directly into the model's prompt.</p>

<h3>Why pgvector in PostgreSQL?</h3>
<p>The <strong>pgvector</strong> extension elevates our trusted relational database into a high-performance vector store. Instead of introducing external vector databases (such as Pinecone or Chroma) which would increase infrastructure cost and latency, we store vector embeddings directly in PostgreSQL tables and perform cosine similarity searches using clean, standard SQL queries.</p>

<h3>Real-World Implementation: The "Ask" Assistant in Mubil</h3>
<p>We successfully put this architecture into production within the <strong>Mubil</strong> application. The <strong>Mubil Ask</strong> section features a conversational assistant built to answer questions regarding electric vehicle adoption, charger compatibility, electricity rates (PVPC), and regional subsidies (such as Plan Auto+ or MOVES III).</p>

<p>The system workflow is designed as follows:</p>
<ol>
    <li><strong>Ingestion:</strong> Official EV regulations, charging guidelines, and subsidy documents are parsed, chunked, and embedded using Gemini's <code>text-embedding-004</code> model. These embeddings are stored in PostgreSQL using <code>pgvector</code>.</li>
    <li><strong>Semantic Retrieval:</strong> When a user submits a query, it is embedded on-the-fly. We then query PostgreSQL using cosine distance to retrieve the most contextually relevant chunks.</li>
    <li><strong>Generation:</strong> The retrieved context is passed alongside the user's question to the Gemini API, which drafts a highly accurate, grounded response tailored to Basque mobility regulations.</li>
</ol>

<p>This implementation effectively eliminates model hallucinations and delivers reliable, localized answers without adding expensive database systems to our stack.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 6,
                "difficulty": "intermediate",
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
                "summary_es": "Cómo estructurar el pipeline de integración continua para auditar la calidad, seguridad y fiabilidad del código utilizando herramientas como Ruff, pip-audit, Bandit y pytest.",
                "summary_eu": "Nola egituratu integrazio jarraituko pipeline-a kodearen kalitatea, segurtasuna eta fidagarritasuna ikuskatzeko, Ruff, pip-audit, Bandit eta pytest bezalako tresnak erabiliz.",
                "summary_en": "How to structure the continuous integration pipeline to audit code quality, security, and reliability using tools like Ruff, pip-audit, Bandit, and pytest.",
                "content_es": """
<p>El despliegue continuo (CD) no tiene por qué ser solo un canal para llevar código a producción. Cuando incorporamos asistentes de Inteligencia Artificial al flujo de trabajo, el volumen de código producido se acelera de forma masiva. En este nuevo contexto, contar con un pipeline de integración continua (CI) robusto y automatizado se convierte en la única barrera de defensa para auditar y garantizar la calidad, seguridad y fiabilidad del código antes de que llegue a producción.</p>

<h3>El rol de la IA en la evolución de CI/CD</h3>
<p>La IA no solo nos ayuda a escribir vistas o modelos en Django; también actúa como un excelente ingeniero de DevOps. Utilizar la IA nos facilita la creación y el mantenimiento de flujos de trabajo de CI/CD complejos (como los archivos de configuración de GitHub Actions o GitLab CI). Podemos pedirle que añada nuevos pasos (jobs) específicos para revisar la calidad del código, aplicar formateadores automáticos, buscar vulnerabilidades o comprobar la compatibilidad de tipos sin necesidad de pasar horas depurando la sintaxis YAML de las acciones.</p>

<h3>Herramientas clave para la auditoría automática en tu pipeline</h3>
<p>Para construir un pipeline seguro y eficiente, es imprescindible integrar herramientas especializadas que analicen diferentes capas de nuestra aplicación de forma automática en cada Pull Request. Aquí explicamos las herramientas fundamentales y para qué sirve cada una:</p>

<ul>
    <li><strong>Ruff (Linter y Formateador):</strong> Tradicionalmente en Python utilizábamos una combinación de herramientas como Flake8, Black, isort y pyupgrade. Ruff unifica todas ellas en una sola herramienta escrita en Rust que es entre 10 y 100 veces más rápida. En la integración continua, Ruff comprueba en milisegundos que el código cumple con las guías de estilo (PEP 8), detecta variables no utilizadas, importaciones desordenadas y malas prácticas sintácticas, bloqueando la integración de código mal formateado o sucio.</li>
    <li><strong>pip-audit (Auditoría de dependencias):</strong> El código generado por IA a menudo propone instalar nuevos paquetes de terceros o actualizar versiones existentes. <code>pip-audit</code> analiza nuestro entorno de ejecución y archivos de dependencias (como <code>requirements.txt</code> o el lockfile de <code>uv</code>) contrastándolos con la base de datos de vulnerabilidades conocidas (CVEs). Esto garantiza que no despleguemos librerías con fallos de seguridad críticos en producción de manera accidental.</li>
    <li><strong>Bandit (Seguridad del código fuente):</strong> Mientras que pip-audit busca fallos en librerías externas, Bandit se enfoca en auditar nuestro propio código Python. Analiza el Árbol de Sintaxis Abstracta (AST) del código fuente para encontrar fallos de seguridad comunes, tales como el uso de contraseñas guardadas en texto plano, llamadas vulnerables al sistema operativo (shell injections), configuraciones de cifrado débiles o vulnerabilidades de inyección SQL.</li>
    <li><strong>Tests con pytest / manage.py test (Validación funcional):</strong> Las auditorías estáticas son necesarias, pero no aseguran que la lógica de negocio funcione. La ejecución de las pruebas unitarias y de integración del proyecto (mediante <code>pytest</code> o el test runner de Django) es la comprobación definitiva. Garantiza de manera empírica que el nuevo código generado no rompe las funcionalidades existentes del sistema (evitando regresiones).</li>
</ul>

<h3>Estructura eficiente con Docker y uv</h3>
<p>Para que estas comprobaciones no ralenticen nuestro desarrollo, es crucial optimizar la infraestructura de CI. Sustituir <i>pip</i> por <strong>uv</strong> en nuestros pipelines y Dockerfiles acelera radicalmente la instalación de dependencias y asegura un entorno determinista. Configurar la caché de Docker y de las dependencias de Python nos permite pasar de pipelines de 10 minutos a validaciones completas en menos de 2 minutos.</p>
""",
                "content_eu": """
<p>Etengabeko inplementazioa (CD) ez da kodea ekoizpenera eramateko bide soil bat bakarrik. Lan-fluxuan Adimen Artifizialeko laguntzaileak sartzen ditugunean, sortzen den kode bolumena izugarri bizkortzen da. Testuinguru berri honetan, integrazio jarraituko (CI) pipeline sendo eta automatizatu bat izatea da defentsa-hesi bakarra, kodearen kalitatea, segurtasuna eta fidagarritasuna ikuskatu eta bermatzeko ekoizpenera iritsi aurretik.</p>

<h3>AIaren rola CI/CD pipelineen bilakaeran</h3>
<p>AIak ez digu soilik Django modeloak edo ikuspegiak idazten laguntzen; DevOps ingeniari bikain gisa ere jokatzen du. AIa erabiltzeak CI/CD fluxu konplexuak (hala nola GitHub Actions edo GitLab CI konfigurazio fitxategiak) sortzea eta mantentzea errazten digu. Pipelineari kalitatea ikuskatzeko, formateatzaileak aplikatzeko, ahultasunak bilatzeko edo moten bateragarritasuna egiaztatzeko job berriak gehitzea eska diezaiokegu, YAML sintaxia arazten orduak eman beharrik gabe.</p>

<h3>Gako-tresnak zure pipelineko auditoretza automatikorako</h3>
<p>Pipeline seguru eta eraginkor bat eraikitzeko, ezinbestekoa da Pull Request bakoitzean gure aplikazioaren geruza desberdinak automatikoki aztertuko dituzten tresna espezializatuak integratzea. Hemen azaltzen ditugu oinarrizko tresnak eta zertarako balio duen bakoitzak:</p>

<ul>
    <li><strong>Ruff (Linter eta Formateatzailea):</strong> Pythonen tradizionalki Flake8, Black, isort eta pyupgrade bezalako tresnen konbinazioa erabiltzen genuen. Ruffek horiek guztiak Rust-en idatzitako tresna bakar batean bateratzen ditu, 10 eta 100 bider azkarragoa dena. Integrazio jarraituan, Ruffek milisegundotan egiaztatzen du kodeak estilo-gidak (PEP 8) betetzen dituela, eta gaizki formateatutako kodea blokeatzen du.</li>
    <li><strong>pip-audit (Mendekotasunen auditoretza):</strong> AIak sortutako kodeak sarritan hirugarrenen pakete berriak instalatzea edo lehendik daudenak eguneratzea proposatzen du. <code>pip-audit</code>ek gure paketeak eta mendekotasun fitxategiak (adibidez <code>requirements.txt</code> o <code>uv</code> lockfilea) aztertzen ditu ahultasun datu-baseekin alderatuz, ekoizpenean akats kritikoak dituzten liburutegiak ez hedatzeko.</li>
    <li><strong>Bandit (Iturburu-kodearen segurtasuna):</strong> pip-audit-ek kanpoko liburutegietan akatsak bilatzen dituen bitartean, Bandit gure Python kode propioa aztertzera bideratzen da. Sintaxi zuhaitza aztertzen du segurtasun akats arruntak aurkitzeko, hala nola testu lauan gordetako pasahitzak, injezio ahultasunak edo zifratze ahula.</li>
    <li><strong>Testak pytest / manage.py test bidez (Balioztatze funtzionala):</strong> Ebaluazio estatikoak beharrezkoak dira, baina ez dute bermatzen negozioko logikak funtzionatzen duenik. Test unitarioak eta integraziokoak exekutatzea (<code>pytest</code> edo Djangoren test runner-aren bidez) behin-betiko egiaztapena da, AIak sortutako kode berriak lehendik dauden funtzionalitateak hausten ez dituela ziurtatzeko.</li>
</ul>

<h3>Egitura eraginkorra Docker eta uv-ekin</h3>
<p>Egiaztapen horiek gure garapena ez moteltzeko, funtsezkoa da CI azpiegitura optimizatzea. Gure pipelineetan eta Dockerfileetan <i>pip</i>-en ordez <strong>uv</strong> erabiltzeak mendekotasunen instalazioa erabat azkartzen du eta ingurune determinista bermatzen du.</p>
""",
                "content_en": """
<p>Continuous deployment (CD) is not just a delivery channel for shipping code. When incorporating Artificial Intelligence assistants into the workflow, the velocity of code production accelerates exponentially. In this new paradigm, maintaining a robust, automated continuous integration (CI) pipeline becomes the ultimate defense barrier to audit and guarantee code quality, security, and stability before it hits production.</p>

<h3>The Role of AI in Evolving CI/CD Workflows</h3>
<p>AI does not just help us write Django views or database schemas; it also acts as a highly capable DevOps collaborator. Leveraging AI makes configuring and maintaining complex CI/CD scripts (like GitHub Actions or GitLab CI YAML configurations) incredibly straightforward. We can ask the AI to generate new jobs for linting, formatting, vulnerability scanning, or type checking, freeing us from debugging workflow syntax manually.</p>

<h3>Core Auditing Tools in Your CI Pipeline</h3>
<p>To build a secure and fast pipeline, it is essential to run specialized security and quality tools automatically on every Pull Request. Here is a breakdown of the key tools and what they do:</p>

<ul>
    <li><strong>Ruff (Linter and Formatter):</strong> Traditionally, Python developers used a combination of separate tools like Flake8, Black, isort, and pyupgrade. Ruff unifies all of them into a single, lightning-fast linter and formatter written in Rust (10x to 100x faster than traditional tools). In CI, Ruff checks PEP 8 compliance, unused imports, and bad code patterns in milliseconds, blocking messy code from entering the repository.</li>
    <li><strong>pip-audit (Dependency Scanning):</strong> AI-generated suggestions often propose installing new third-party packages or upgrading existing ones. <code>pip-audit</code> scans python packages and lockfiles (such as <code>requirements.txt</code> or the <code>uv</code> lockfile) against known vulnerability databases (CVEs), preventing us from accidentally deploying vulnerable dependencies to production.</li>
    <li><strong>Bandit (Source Code Security):</strong> While pip-audit checks external packages, Bandit focuses on auditing our own Python source code. It analyzes the Abstract Syntax Tree (AST) to identify common security flaws, such as hardcoded credentials, vulnerable subprocess calls (shell injections), weak cryptographic usages, or SQL injections.</li>
    <li><strong>Tests via pytest / manage.py test (Functional Validation):</strong> Static checks are necessary but they cannot guarantee that the business logic behaves as expected. Running automated unit and integration tests (using <code>pytest</code> or Django's default test runner) is the ultimate safeguard. It verifies empirically that the AI-generated code does not break existing application behavior (regression testing).</li>
</ul>

<h3>Speeding up CI/CD with Docker and uv</h3>
<p>To prevent these checks from slowing down your developer feedback loop, optimizing the build infrastructure is key. Replacing <i>pip</i> with <strong>uv</strong> in your Docker builds and CI workflows radically accelerates package installations and guarantees reproducible, deterministic environments.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 7,
                "difficulty": "intermediate",
                "likes": 15,
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
            {
                "category": categories["webgis-postgis"],
                "author": author,
                "title_es": "Validación de Zonas de Bajas Emisiones (ZBE) con Polígonos en PostGIS",
                "title_eu": "Emisio Baxuko Eremuen (EBE) balidazioa poligonoekin PostGISen",
                "title_en": "Validating Low Emission Zones (ZBE) with Polygons in PostGIS",
                "slug_es": "validacion-zbe-poligonos-postgis",
                "slug_eu": "ebe-balidazioa-poligonoak-postgis",
                "slug_en": "validating-zbe-polygons-postgis",
                "summary_es": "Cómo utilizar las consultas de intersección espacial de PostGIS en Django para verificar en tiempo real si un vehículo ingresa a una Zona de Bajas Emisiones.",
                "summary_eu": "Nola erabili PostGISen intersekzio espazialen kontsultak Django-n, ibilgailu bat Emisio Baxuko Eremu batean sartzen den denbora errealean egiaztatzeko.",
                "summary_en": "How to leverage PostGIS spatial intersection queries in Django to verify in real-time if a vehicle enters a Low Emission Zone.",
                "content_es": """
<p>Las <strong>Zonas de Bajas Emisiones (ZBE)</strong> son áreas urbanas delimitadas geográficamente donde se restringe el acceso a los vehículos más contaminantes para mejorar la calidad del aire. Para gestionar estas zonas en plataformas WebGIS modernas, la base de datos geoespacial <strong>PostGIS</strong> es la herramienta definitiva gracias a su potente soporte de operaciones con polígonos complejos.</p>

<h3>¿Cómo modelar una ZBE en Django?</h3>
<p>Utilizando <strong>GeoDjango</strong>, podemos definir las ZBE directamente en nuestro modelo de base de datos relacional asociando un campo geométrico multi-polígono:</p>

<pre><code>from django.contrib.gis.db import models

class LowEmissionZone(models.Model):
    name = models.CharField(max_length=100)
    boundary = models.MultiPolygonField(srid=4326)
    restricted_categories = models.JSONField(default=list)

    def __str__(self):
        return self.name
</code></pre>

<h3>El caso práctico: Verificación en tiempo real en ai.maps.eus/zbe/</h3>
<p>Hemos integrado esta tecnología de forma práctica en nuestro visor interactivo de <a href="https://ai.maps.eus/zbe/" target="_blank">ai.maps.eus/zbe/</a>. Esta herramienta permite a los conductores y gestores de flotas consultar de forma instantánea si una coordenada geográfica específica cae dentro de una zona regulada y qué restricciones le aplican según la etiqueta ambiental del vehículo.</p>

<p>Para determinar si un punto geográfico (latitud, longitud) está dentro del polígono de una ZBE, utilizamos operadores espaciales nativos de PostGIS como <code>ST_Contains</code> a través del ORM de Django:</p>

<pre><code>from django.contrib.gis.geos import Point
from .models import LowEmissionZone

def check_location_restrictions(lon, lat):
    user_location = Point(lon, lat, srid=4326)
    
    # Buscamos la ZBE que contiene espacialmente nuestra ubicación
    active_zbe = LowEmissionZone.objects.filter(
        boundary__contains=user_location
    ).first()
    
    if active_zbe:
        return {
            "inside": True,
            "zbe_name": active_zbe.name,
            "restrictions": active_zbe.restricted_categories
        }
    return {"inside": False}
</code></pre>

<p>Esta consulta espacial se ejecuta en milisegundos gracias a los índices espaciales GIST (Generalized Search Tree). Al integrar esta lógica en el backend de Django, podemos validar itinerarios completos de reparto de mercancías simplemente iterando sobre los puntos de parada del vehículo y alertando instantáneamente al conductor si vulnera alguna normativa local de acceso urbano.</p>
""",
                "content_eu": """
<p><strong>Emisio Baxuko Eremuak (EBE)</strong> muga geografiko zehatzak dituzten hiri-eremuak dira. Bertan, ibilgailu kutsatzaileenentzako sarbidea mugatzen da airearen kalitatea hobetzeko. WebGIS plataforma modernoetan eremu hauek kudeatzeko, <strong>PostGIS</strong> da erreferentziazko datu-base geoespaziala, poligono eta multipoligono konplexuak prozesatzeko duen gaitasunari esker.</p>

<h3>Inplementazio praktikoa: ai.maps.eus/zbe/</h3>
<p>Teknologia hau gure <a href="https://ai.maps.eus/zbe/" target="_blank">ai.maps.eus/zbe/</a> bide-orrian aplikatu dugu. Aplikazio honen bidez, erabiltzaileek puntu geografiko bat eremu mugatu baten barruan dagoen egiaztatu dezakete denbora errealean.</p>

<p>Puntu bat ZBE poligonoaren barruan dagoen egiaztatzeko, PostGISen <code>ST_Contains</code> operadore espaziala erabiltzen dugu Django ORM bidez:</p>

<pre><code>from django.contrib.gis.geos import Point
from .models import LowEmissionZone

user_location = Point(lon, lat, srid=4326)
active_zbe = LowEmissionZone.objects.filter(
    boundary__contains=user_location
).first()
</code></pre>

<p>GIST (Generalized Search Tree) indize espazialei esker, kontsulta hau milisegundotan exekutatzen da, hiri-mugikortasuna kudeatzeko aplikazio azkar eta fidagarriak ahalbidetuz.</p>
""",
                "content_en": """
<p><strong>Low Emission Zones (ZBE)</strong> are geographically restricted urban areas where access by high-emitting vehicles is regulated to improve air quality. To model and query these zones in WebGIS architectures, <strong>PostGIS</strong> is the industry standard database extension, offering robust support for complex geometry types like polygons.</p>

<h3>Modeling a LEZ in Django</h3>
<p>By leveraging <strong>GeoDjango</strong>, we can represent these zones directly in our relational database, utilizing spatial fields to store the zone's geographical boundaries:</p>

<pre><code>from django.contrib.gis.db import models

class LowEmissionZone(models.Model):
    name = models.CharField(max_length=100)
    boundary = models.MultiPolygonField(srid=4326)
    restricted_categories = models.JSONField(default=list)
</code></pre>

<h3>Real-World Use Case: Live Verification at ai.maps.eus/zbe/</h3>
<p>We put this technology to work in our interactive low emission zone lookup tool at <a href="https://ai.maps.eus/zbe/" target="_blank">ai.maps.eus/zbe/</a>. The application lets logistics operators and commuters instantly check whether a specific set of coordinates intersects with active municipal restrictions.</p>

<p>To check if a point is contained inside the ZBE polygon boundary, we perform a spatial query using PostGIS's <code>ST_Contains</code> operator via the Django ORM:</p>

<pre><code>from django.contrib.gis.geos import Point
from .models import LowEmissionZone

def check_location(lon, lat):
    point = Point(lon, lat, srid=4326)
    zbe = LowEmissionZone.objects.filter(boundary__contains=point).first()
    if zbe:
        return {"restricted": True, "zone": zbe.name}
    return {"restricted": False}
</code></pre>

<p>Using spatial indexing (GIST indexes), this lookup takes less than a millisecond. This enables real-time verification of complex multi-stop delivery routes, checking each destination coordinate instantly and warning drivers of compliance issues before they enter the restricted areas.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 6,
                "difficulty": "intermediate",
                "map_geojson": json.dumps(zbe_geojson),
                "map_center_lat": 42.8485,
                "map_center_lng": -2.6705,
                "map_zoom": 13,
                "likes": 18,
                "tag_slugs": ["django", "postgis", "docker"],
            },
            {
                "category": categories["backend-architecture"],
                "author": author,
                "title_es": "Orquestación de Tareas Asíncronas en Django con Celery y Redis",
                "title_eu": "Zeregin asinkronoen orkestrazioa Django-n Celery eta Redis-ekin",
                "title_en": "Orchestrating Asynchronous Tasks in Django with Celery and Redis",
                "slug_es": "django-celery-redis-tareas-asincronas",
                "slug_eu": "django-celery-redis-zeregin-asinkronoak",
                "slug_en": "django-celery-redis-asynchronous-tasks",
                "summary_es": "Cómo integramos Celery y Redis para procesar ingestas periódicas de gran volumen (como eventos culturales desde OpenData Euskadi) y tareas de enriquecimiento geográfico bajo demanda en maps.eus.",
                "summary_eu": "Nola integratzen ditugun Celery eta Redis bolumen handiko datuen ingesta periodikoak prozesatzeko (OpenData Euskadiko kultura-ekitaldiak kasu) eta eskaripeko aberaste geografikoko zereginak maps.eus gunean.",
                "summary_en": "How we integrate Celery and Redis to process high-volume periodic ingestions (such as cultural events from OpenData Euskadi) and on-demand spatial geocoding tasks in maps.eus.",
                "content_es": """
<p>En el desarrollo de aplicaciones web de alto rendimiento, delegar tareas pesadas o de ejecución periódica a procesos en segundo plano es fundamental para mantener una interfaz de usuario ágil y responsiva. En <strong>maps.eus</strong>, utilizamos una combinación de <strong>Celery</strong> como gestor de tareas asíncronas y <strong>Redis</strong> como broker de mensajería para gestionar flujos de datos complejos sin penalizar los tiempos de carga del usuario final.</p>

<h2>La Arquitectura Celery + Redis</h2>
<p>Celery actúa como un distribuidor de trabajo que monitoriza colas de tareas. Cuando un proceso (por ejemplo, una petición HTTP de Django o un comando administrativo) solicita ejecutar una tarea pesada, la empaqueta y la envía a <strong>Redis</strong>, que actúa como cola de mensajería (broker). Uno o varios workers de Celery, que corren de forma independiente en contenedores Docker, consumen estos mensajes y procesan las tareas de manera asíncrona.</p>

<h3>Caso de Uso: Ingesta Periódica de Eventos Culturales</h3>
<p>El módulo <strong>Kultur</strong> centraliza la agenda de eventos culturales en Euskal Herria. Estos eventos se actualizan diariamente a través de APIs de OpenData. Dado que el proceso requiere descargar un volumen importante de registros e indexarlos, delegamos esta carga a una tarea programada:</p>
<ul>
    <li><strong>Carga e Ingesta (<code>kultur.load_events</code>):</strong> Se ejecuta periódicamente mediante <code>django-celery-beat</code>. Descarga el feed oficial de eventos, los normaliza en base de datos y, a continuación, geolocaliza las salas y recintos culturales que carecen de coordenadas espaciales.</li>
</ul>

<p>A continuación se muestra una sección simplificada de nuestro archivo de tareas en <code>apps/kultur/tasks.py</code>:</p>

<pre><code>from celery import shared_task
from django.core.management import call_command

@shared_task(
    name="kultur.load_events",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def load_events(self):
    # Ingesta de eventos culturales
    call_command("load_events")
    # Geocodificación espacial de los recintos
    call_command("geocode_venues")
</code></pre>

<h3>Gestión Inteligente de Reintentos ante Fallos de Red</h3>
<p>Una gran ventaja de usar Celery frente a scripts cron simples es la gestión de fallos. Si la API de OpenData Euskadi está temporalmente inactiva o el servicio de mapas externo falla durante la geocodificación, el decorador <code>@shared_task</code> está configurado con reintentos automáticos progresivos (<code>autoretry_for</code> y <code>retry_backoff</code>).</p>
<p>Esto asegura que la tarea no falle definitivamente al primer contratiempo, sino que vuelva a intentarlo aplicando un retardo exponencial aleatorio (jitter) para evitar saturar el servidor de destino.</p>

<h3>Ventajas clave de esta arquitectura</h3>
<ol>
    <li><strong>Resiliencia:</strong> Si la fuente de datos está caída, la tarea de Celery fallará de manera aislada y se reintentará más tarde sin romper la aplicación para el usuario.</li>
    <li><strong>Experiencia de Usuario (UX):</strong> El portal web sirve los eventos almacenados localmente al instante, mientras las tareas pesadas de geocodificación ocurren silenciosamente por detrás.</li>
    <li><strong>Escalabilidad:</strong> En producción, podemos escalar el número de workers de Celery de forma independiente si el volumen de eventos o recintos a geolocalizar crece drásticamente.</li>
</ol>
""",
                "content_eu": """
<p>Errendimendu handiko web aplikazioen garapenean, zeregin astunak edo aldiro exekutatu beharrekoak atzeko planoan delegatzea funtsezkoa da erabiltzaile-interfaze arina eta sentikorra mantentzeko. Gure plataforman (<strong>maps.eus</strong>), <strong>Celery</strong> (zeregin asinkronoen kudeatzailea) eta <strong>Redis</strong> (mezu-brokerra) erabiltzen ditugu datu-fluxu konplexuak kudeatzeko, erabiltzailearen karga-denborak zigortu gabe.</p>

<h2>Celery + Redis Arkitektura</h2>
<p>Celeryk zereginen ilarak kontrolatzen dituen lan-banatzaile giga funtzionatzen du. Prozesu batek lan astun bat egiteko eskatzen duenean, mezua <strong>Redis</strong>-era bidaltzen du. Docker edukiontzietan modu independentean exekutatzen ari diren Celery workerrek mezu hauek kontsumitzen dituzte eta zereginak modu asinkronoan prozesatzen dituzte.</p>

<h3>Erabilera Kasua: Kultur Ekitaldien Ingesta Periodikoa</h3>
<p><strong>Kultur</strong> moduluak Euskal Herriko kultur ekitaldien agenda zentralizatzen du. Ekitaldi hauek egunero eguneratzen dira OpenData APIen bidez. Deskarga eta indexazio prozesua astuna denez, karga hau programatutako zeregin baten esku uzten dugu:</p>
<ul>
    <li><strong>Karga eta Ingesta (<code>kultur.load_events</code>):</strong> Aldian-aldian exekutatzen da <code>django-celery-beat</code> bidez. Ekitaldien jario ofiziala deskargatzen du, datu-basean normalizatzen ditu eta koordenatu espazialik ez duten aretoak geolokalizatzen ditu.</li>
</ul>

<pre><code>from celery import shared_task
from django.core.management import call_command

@shared_task(
    name="kultur.load_events",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def load_events(self):
    call_command("load_events")
    call_command("geocode_venues")
</code></pre>

<h3>Reintentu Adimendunen Kudeaketa Sareko Hutsegiteen Aurrean</h3>
<p>Celery erabiltzearen abantaila handi bat akatsen kudeaketa da. OpenData Euskadiren APIa aldi baterako erabilgarri ez badago edo kanpoko mapa-zerbitzuak geokodetzean huts egiten badu, <code>@shared_task</code> dekoratzailea berriro saiatze automatiko progresiboekin konfiguratuta dago.</p>
""",
                "content_en": """
<p>In high-performance web development, delegating heavy or periodic tasks to background processes is essential to keeping the user interface fast and responsive. At <strong>maps.eus</strong>, we use <strong>Celery</strong> as our asynchronous task manager and <strong>Redis</strong> as a message broker to handle complex data workflows without penalizing frontend load times.</p>

<h2>The Celery + Redis Architecture</h2>
<p>Celery acts as a work distributor that monitors task queues. When a Django process triggers a resource-intensive operation, it packages the task and posts it to <strong>Redis</strong>, which serves as the message queue. Celery workers running in independent Docker containers consume these tasks and process them asynchronously.</p>

<h3>Use Case: Periodic Culture Events Ingestion</h3>
<p>The <strong>Kultur</strong> module centralizes Euskal Herria's cultural event calendar. These events are updated daily through public OpenData APIs. Since the process requires downloading a large volume of records and indexing them, we delegate this workload to a scheduled task:</p>
<ul>
    <li><strong>Load and Ingest (<code>kultur.load_events</code>):</strong> Runs periodically via <code>django-celery-beat</code>. It fetches the official event feed, normalizes them in the database, and geolocates cultural venues lacking spatial coordinates.</li>
</ul>

<pre><code>from celery import shared_task
from django.core.management import call_command

@shared_task(
    name="kultur.load_events",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=3,
)
def load_events(self):
    # Ingest cultural events
    call_command("load_events")
    # Spatial geocoding of venues
    call_command("geocode_venues")
</code></pre>

<h3>Intelligent Retries on Network Failures</h3>
<p>A major benefit of using Celery over basic cron scripts is error handling. If the OpenData Euskadi API is temporarily down or the external maps geocoding service timeouts, the <code>@shared_task</code> decorator is configured with progressive automatic retries (<code>autoretry_for</code> and <code>retry_backoff</code>).</p>
<p>This guarantees that temporary network hiccups do not completely crash the pipeline, but instead trigger smart retries with exponential backoff and jitter.</p>
""",
                "is_published": True,
                "published_at": timezone.now(),
                "read_time": 5,
                "difficulty": "intermediate",
                "likes": 20,
                "tag_slugs": ["django", "docker", "celery"],
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

                # Clear spatial fields if they are not defined in this post's seed data
                if "map_center_lat" not in pdata:
                    post.map_center_lat = None
                if "map_center_lng" not in pdata:
                    post.map_center_lng = None
                if "map_zoom" not in pdata:
                    post.map_zoom = None
                if "map_geojson" not in pdata:
                    post.map_geojson = None

                for key, val in pdata.items():
                    setattr(post, key, val)

                post.published_at = original_published_at
                post.likes = original_likes
                post.save()
                created = False
            else:
                # Create a new post
                if "map_center_lat" not in pdata:
                    pdata["map_center_lat"] = None
                if "map_center_lng" not in pdata:
                    pdata["map_center_lng"] = None
                if "map_zoom" not in pdata:
                    pdata["map_zoom"] = None
                if "map_geojson" not in pdata:
                    pdata["map_geojson"] = None

                post = Post.objects.create(**pdata)
                created = True

            post.tags.set(ptags)
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} Post: {post.title}")

        self.stdout.write(self.style.SUCCESS("Blog successfully seeded!"))
