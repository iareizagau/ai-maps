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
<p>El rol del desarrollador de software, tal y como lo conocíamos, ha cambiado para siempre. Al menos el mío lo ha hecho en solo doce meses. Esta transformación no es una teoría sobre el futuro del trabajo; es una realidad tangible que he vivido al contrastar la construcción de dos de mis proyectos personales: <strong>maps.eus</strong> y <strong>ai.maps.eus</strong>.</p>

<h3>El punto de partida: maps.eus y la artesanía del código</h3>
<p>Cuando comencé a desarrollar <strong>maps.eus</strong>, el objetivo inicial era humilde: quería crear la sección <i>Kulturmaps</i> para participar en el concurso de <strong>Open Data Euskadi</strong>. El desarrollo fue un proceso puramente artesanal. Cada vista de Django, cada modelo, y cada línea de lógica geoespacial en PostGIS fue picada a mano en mi teclado.</p>

<p>En aquella época, mi uso de la Inteligencia Artificial se limitaba a asistentes externos ejecutándose en una pestaña del navegador. Realizaba consultas concretas sobre sintaxis o APIs, de la misma manera que antes recurría a StackOverflow. Yo era el creador de cada línea de código; conocía cada coma y cada función. La IA actuaba como un diccionario rápido, pero el verdadero cuello de botella de la productividad era físico: la velocidad de mis dedos sobre el teclado.</p>

<h3>El salto cualitativo: ai.maps.eus y los agentes en el IDE</h3>
<p>El cambio radical llegó con el desarrollo de mi segundo laboratorio WebGIS, <strong>ai.maps.eus</strong>. Aquí decidí dar un paso adelante e integrar asistentes de IA autónomos y basados en agentes directamente dentro de mi entorno de desarrollo (IDE).</p>

<p>La IA dejó de ser una herramienta de consulta aislada para convertirse en un <strong>mentor y colaborador activo</strong>. Gracias a tener acceso al contexto completo del espacio de trabajo y a la capacidad de proponer cambios estructurados, la IA me ayudó a entender y desplegar tecnologías complejas que antes me daban un respeto enorme. Juntos pudimos:</p>
<ul>
    <li>Integrar bases de datos espaciales y dominar el uso de <strong>pgRouting</strong> para modelar redes viales.</li>
    <li>Procesar e importar datos complejos de <strong>OpenStreetMap</strong>.</li>
    <li>Montar toda la infraestructura de contenedores necesaria, automatizando la configuración de <code>Dockerfile</code> y <code>docker-compose</code> para bases de datos, workers de Celery, y cachés de Redis.</li>
</ul>
<p>El resultado es que he levantado el motor completo de generación y visualización de rutas de bikepacking prácticamente sin teclear código a mano.</p>

<h3>El nuevo cuello de botella: La Caja Negra y la Deuda Técnica</h3>
<p>Este nivel de automatización nos sitúa ante un nuevo dilema. Si la IA es capaz de generar cientos de líneas de código válidas en segundos, la velocidad de escritura deja de ser una métrica útil. El riesgo real ahora es la pérdida de control técnico, creando sistemas que se conviertan en "cajas negras" incomprensibles e imposibles de mantener.</p>

<p>Para evitarlo, mi día a día como ingeniero de software ha cambiado de enfoque:</p>
<ol>
    <li><strong>Diseño de Arquitectura a Alto Nivel:</strong> Dedico mucho más tiempo a planificar la estructura, la modularidad y las relaciones entre componentes antes de interactuar con la IA. Si el diseño general es sólido, la IA produce código mucho más limpio y acotado.</li>
    <li><strong>El Arte de la Auditoría y Revisión:</strong> Antes revisábamos confirmaciones (commits) que contenían unos pocos archivos modificados a mano. Hoy, una sola iteración con un agente puede alterar docenas de archivos en segundos. Aprender a leer, evaluar y cuestionar críticamente este código masivo generado por la IA es la habilidad clave del desarrollador actual.</li>
    <li><strong>Validación mediante CI/CD:</strong> Confiar ciegamente en el código de la IA es una receta para el desastre. La única forma de mantener la cordura es fortaleciendo nuestros procesos de integración continua. Contar con suites de tests automáticos robustas en el servidor es imprescindible para comprobar que ningún cambio de la IA rompe las funcionalidades existentes en cuestión de segundos.</li>
</ol>

<h3>Side Projects vs. Entornos Corporativos</h3>
<p>Los proyectos personales y los laboratorios son el sandbox ideal para probar el potencial de los nuevos modelos (como Claude, que en mi experiencia actual destaca por una solidez y coherencia técnica superior a Gemini en generación de código). Aquí, equivocarse es parte del juego.</p>

<p>Sin embargo, en el mundo real (trabajando en equipo, con datos sensibles, bajo estrictas regulaciones de seguridad y rendimiento), el desafío es mucho mayor. No se trata solo de construir rápido, sino de colaborar de forma confiable. La IA cambia la forma en que programamos, pero eleva la necesidad de tener ingenieros que entiendan la arquitectura, garanticen la seguridad y controlen la infraestructura.</p>
""",
                "content_eu": """
<p>Software garatzailearen rola, ezagutzen genuen bezala, betiko aldatu da. Nirea behintzat urte bakar batean aldatu da. Eraldaketa hau ez da lanaren etorkizunari buruzko teoria bat; nire bi proiektu pertsonalen eraikuntzan bizi izan dudan errealitate argia da: <strong>maps.eus</strong> eta <strong>ai.maps.eus</strong>.</p>

<h3>Hasierako puntua: maps.eus eta kodearen artisautza</h3>
<p><strong>maps.eus</strong> garatzen hasi nintzenean, helburua xumea zen: <i>Kulturmaps</i> atala sortu nahi nuen <strong>Open Data Euskadi</strong> lehiaketan parte hartzeko. Garapena artisau-prozesu bat izan zen. Django ikuspegi bakoitza, modelo bakoitza eta PostGISen logika geoespazialeko lerro bakoitza eskuz idatzi nuen nire teklatuan.</p>

<p>Garai hartan, Adimen Artifiziala kanpotik erabiltzen nuen, arakatzaileko fitxa batean. Sintaxiari edo APIei buruzko kontsulta zehatzak egiten nituen, lehen StackOverflow-ra jotzen nuen modu berean. Ni nintzen kode lerro bakoitzaren sortzailea; koma bakoitza eta funtzio bakoitza ezagutzen nuen. AIak hiztegi azkar gisa funtzionatzen zuen, baina produktibitatearen botila-lepoa fisikoa zen: nire hatzen abiadura teklatuaren gainean.</p>

<h3>Jauzi kualitatiboa: ai.maps.eus eta agenteak IDEan</h3>
<p>Aldaketa sakona nire bigarren WebGIS laborategiaren garapenarekin etorri zen: <strong>ai.maps.eus</strong>. Hemen urrats bat gehiago ematea erabaki nuen, eta AI agente autonomoak zuzenean nire garapen ingurunean (IDE) integratu nituen.</p>

<p>AIak kontsulta-tresna izateari utzi zion, <strong>kolaboratzaile aktibo eta mentor</strong> bihurtzeko. Lan-eremuaren testuinguru osorako sarbidea izateari eta aldaketa egituratuak proposatzeko gaitasunari esker, AIak lehen beldur handia ematen zidaten teknologia konplexuak ulertzen eta hedatzen lagundu zidan:</p>
<ul>
    <li>Baza-datu espazialak integratzen eta errepide-sareak modelatzeko <strong>pgRouting</strong> erabiltzen.</li>
    <li><strong>OpenStreetMap</strong>eko datu konplexuak prozesatzen eta inportatzen.</li>
    <li>Edukiontzien azpiegitura osoa prestatzen, datu-baseetarako, Celery workerretarako eta Redis katxeetarako <code>Dockerfile</code> eta <code>docker-compose</code> konfigurazioak automatizatuz.</li>
</ul>
<p>Ondorioz, bikepacking ibilbideak sortzeko eta bistaratzeko motor osoa altxatu dut, ia kode lerrorik eskuz idatzi gabe.</p>

<h3>Botila-lepo berria: Kutxa Beltza eta Zor Teknikoa</h3>
<p>Automatizazio maila honek dilema berri baten aurrean jartzen gaitu. AIak segundotan ehunka kode lerro sendo sor ditzakeenez, idazteko abiadura jada ez da baliozko neurria. Orain, benetako arriskua kontrol teknikoa galtzea da, ulertezinak eta mantentzen ezinezkoak diren "kutxa beltzak" sortuz.</p>

<p>Hori saihesteko, software ingeniari bezala nire eguneroko lanak fokua aldatu du:</p>
<ol>
    <li><strong>Goi Mailako Arkitektura Diseinua:</strong> Denbora askoz gehiago dedikatzen dut proiektuaren egitura, modulartasuna eta osagaien arteko harremanak planifikatzera AIari kodea eskatu aurretik. Diseinu orokorra sendoa bada, AIak kode garbiagoa eta zehatzagoa sortzen du.</li>
    <li><strong>Ikuskaritza eta Berrikuspen Artea:</strong> Lehen, eskuz aldatutako fitxategi gutxi batzuk zituzten commiteak berrikusten genituen. Gaur egun, agente batekin egindako iterazio bakar batek dozenaka fitxategi alda ditzake segundotan. AIak sortutako kode masibo hori irakurtzen, ebaluatzen eta kritikatzen ikastea da egungo garatzailearen funtsezko trebetasuna.</li>
    <li><strong>CI/CD Bidezko Balioztatzea:</strong> AIaren kodean itsu-itsuan fidatzea hondamendira joateko bidea da. Integrazio etengabeko prozesuak indartzea da kontrola mantentzeko modu bakarra. Zerbitzarian test automatizatuen suite sendoak izatea ezinbestekoa da AIaren aldaketek lehendik zeuden funtzionalitateak hausten ez dituztela ziurtatzeko.</li>
</ol>

<h3>Side Projects vs. Enpresa Inguruneak</h3>
<p>Proiektu pertsonalak eremu bikainak dira eredu berrien potentziala probatzeko (adibidez Claude, nire esperientzian Gemini baino sendoagoa kode-sorkuntzan). Hemen, huts egitea jokoaren parte da.</p>
<p>Hala ere, enpresa-munduan (taldean lanean, datu sentikorrekin, segurtasun eta errendimendu arau zorrotzpean), erronka askoz handiagoa da. Kontua ez da azkar eraikitzea soilik, konfiantzaz elkarlanean aritzea baizik. AIak programatzeko modua aldatzen du, baina arkitektura ulertzen duten, segurtasuna bermatzen duten eta azpiegitura kontrolatzen duten ingeniarien beharra areagotzen du.</p>
""",
                "content_en": """
<p>The role of the software developer, as we knew it, has changed forever. At least mine has in just twelve months. This transformation is not a theory about the future of work; it is a tangible reality I experienced while building two of my personal projects: <strong>maps.eus</strong> and <strong>ai.maps.eus</strong>.</p>

<h3>The Starting Point: maps.eus and Handcrafted Code</h3>
<p>When I first started developing <strong>maps.eus</strong>, the initial goal was humble: I wanted to build the <i>Kulturmaps</i> section to participate in the <strong>Open Data Euskadi</strong> competition. The development was a purely manual, handcrafted process. Every Django view, every model, and every line of spatial logic in PostGIS was written by hand on my keyboard.</p>

<p>Back then, my use of Artificial Intelligence was limited to external assistants running in a browser tab. I asked specific questions about syntax or APIs, much like I used to consult StackOverflow. I was the author of every single line of code; I knew every comma and every function. The AI acted as a quick reference, but the bottleneck of productivity was physical: the speed of my fingers on the keyboard.</p>

<h3>The Qualitative Leap: ai.maps.eus and IDE-integrated Agents</h3>
<p>The radical shift occurred with the development of my second WebGIS lab, <strong>ai.maps.eus</strong>. Here, I decided to take a step forward and integrate autonomous agentic AI assistants directly into my development environment (IDE).</p>

<p>The AI transitioned from an isolated search tool into a <strong>mentor and active collaborator</strong>. With access to the complete workspace context and the ability to propose structured file modifications, the AI helped me understand and implement complex technologies that previously felt intimidating:</p>
<ul>
    <li>Integrating spatial databases and mastering <strong>pgRouting</strong> to model road networks.</li>
    <li>Processing and importing complex datasets from <strong>OpenStreetMap</strong>.</li>
    <li>Setting up the entire containerized infrastructure, automating <code>Dockerfile</code> and <code>docker-compose</code> configurations for databases, Celery workers, and Redis caches.</li>
</ul>
<p>The result is that I built a complete bikepacking route optimizer and visualizer almost without typing a single line of code manually.</p>

<h3>The New Bottleneck: The Black Box and Technical Debt</h3>
<p>This level of automation presents a new dilemma. If AI can generate hundreds of lines of valid code in seconds, typing speed ceases to be a useful engineering metric. The real danger now is the loss of technical ownership, producing systems that turn into unmaintainable "black boxes."</p>

<p>To prevent this, my daily routine as a software engineer has shifted focus:</p>
<ol>
    <li><strong>High-Level Architecture Design:</strong> I spend significantly more time planning the project structure, modularity, and interfaces between components before asking the AI for code. If the design is clean, the AI produces far better, targeted code.</li>
    <li><strong>The Art of Auditing and Review:</strong> We used to review commits containing just a few manually edited files. Today, a single iteration with an agent can modify dozens of files in seconds. Learning to read, evaluate, and critically question this mass of AI-generated code is the developer's core skill.</li>
    <li><strong>Validation via CI/CD:</strong> Blindly trusting AI output is a recipe for disaster. The only way to maintain control is by strengthening our continuous integration pipelines. Robust automated test suites are essential to verify in seconds that massive AI changes do not break existing logic.</li>
</ol>

<h3>Side Projects vs. Enterprise Environments</h3>
<p>Personal projects are the perfect sandbox to experiment with new models (like Claude, which in my experience currently stands out for its technical coherence and code generation quality compared to Gemini). Here, making mistakes is part of the learning process.</p>

<p>However, in the real corporate world—working in teams, with sensitive data, under strict security and performance requirements—the stakes are much higher. It is not just about building fast; it is about building reliably. AI changes how we write code, but it heightens the need for engineers who understand architecture, ensure security, and control the infrastructure.</p>
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

            post, created = Post.objects.update_or_create(
                slug_es=pdata["slug_es"], defaults=pdata
            )
            post.tags.set(ptags)
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} Post: {post.title}")

        self.stdout.write(self.style.SUCCESS("Blog successfully seeded!"))
