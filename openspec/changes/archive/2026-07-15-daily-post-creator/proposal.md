# Proposal - Daily Post Creator

## Why

El blog técnico de `maps.eus` y `ai.maps.eus` es un escaparate de la madurez tecnológica del proyecto (WebGIS, Django, PostGIS, pgvector, Celery, Gemini). La propuesta inicial de automatizar un post diario combinando NewsAPI y Gemini tiene un gran potencial, pero tras analizar la base de código actual y los riesgos asociados, identificamos áreas críticas de mejora:

1. **Riesgo de Ruido y Pérdida de Enfoque:** NewsAPI devuelve noticias de tecnología muy generales. Un blog técnico de calidad no debe ser un simple agregador de noticias; debe mostrar la aplicación práctica de esas tecnologías en nuestro propio ecosistema.
2. **Desaprovechamiento de las capacidades WebGIS:** Los posts actuales del blog (`Post` model) permiten incrustar mapas interactivos con GeoJSON y coordenadas. Generar posts de puro texto plano ignora el valor principal de la plataforma.
3. **Publicación Directa Sin Revisión (Caja Negra):** Confiar la publicación automática e inmediata a un LLM puede introducir imprecisiones técnicas o errores de formato HTML/Markdown que devalúen el sitio.
4. **Deduplicación Básica:** Evitar repetir temáticas requiere que el modelo conozca el histórico reciente y sepa cómo enfocar un tema ya tratado (ej. añadiendo casos de éxito específicos, optimizaciones de rendimiento o segundas partes).

### Propuesta Superadora (Valor Añadido)

* **Agente Redactor Conectado (Grounded Writer):** La noticia externa actuará como catalizador, pero Gemini redactará el post conectándolo directamente con la infraestructura de `ai.maps.eus` (ej. vinculando noticias de IA con la búsqueda semántica de Mubil, u optimizaciones espaciales con PostGIS/pgRouting).
* **Generación de Mapas Interactivos:** Gemini diseñará un componente espacial interactivo autogenerado (GeoJSON válido dentro de Euskal Herria) para visualizarlo en el mapa Leaflet del post.
* **Flujo Draft-First (Borradores):** El proceso diario en segundo plano guardará los posts con `is_published=False` para revisión humana antes de ser publicados, con un switch en settings para habilitar publicación directa.
* **Redacción Trilingüe Sincronizada:** Generación concurrente en español (`es`), euskera (`eu`) e inglés (`en`) garantizando coherencia en estructuras de código, enlaces y etiquetas.

---

## What Changes

* **Nuevo Módulo de Tareas (`src/apps/blog/tasks.py`)**: Tareas Celery para ejecutar el flujo diario de forma segura con reintentos exponenciales.
* **Servicios de Generación (`src/apps/blog/services.py`)**: Lógica pura para consumir NewsAPI, consultar la base de datos de posts previos para deduplicación semántica y llamar a la API de Gemini con prompts estructurados.
* **Configuración en Settings (`src/config/settings/base.py`)**: Definición del cronogramador de Celery Beat para la ejecución periódica y configuración de las APIs.
* **Mejoras en Admin (`src/apps/blog/admin.py`)**: Panel intuitivo para revisar borradores y publicarlos.

---

## Capabilities

### New Capabilities

* `blog-automated-generation`: Descarga periódica y automática de noticias del sector tecnológico (desarrollo, IA, nuevos roles), deduplicación inteligente y generación en borrador de un artículo técnico de alta calidad en español, euskera e inglés.
* `blog-grounded-writing`: Ajuste dinámico del prompt para obligar al LLM a relacionar los artículos con la arquitectura, retos y soluciones reales implementadas en `ai.maps.eus`.
* `blog-gis-autogeneration`: Autogeneración de coordenadas de centrado y GeoJSON interactivo de Leaflet en el cuerpo del post para demostrar conceptos geoespaciales aplicados.

### Modified Capabilities

* `blog-administration`: Permitir filtrar posts en borrador autogenerados por IA y agilizar su revisión y publicación desde el Django Admin.

---

## Impact

* `src/apps/blog/tasks.py` (nuevo)
* `src/apps/blog/services.py` (nuevo)
* `src/apps/blog/admin.py` (modificado)
* `src/config/settings/base.py` (modificado)
* `src/apps/blog/tests/test_daily_post.py` (nuevo)
