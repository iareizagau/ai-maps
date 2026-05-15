# OSM Buildings y Ecosistema Geoespacial

Este documento resume las herramientas y recursos para la visualización 3D de edificios y la integración con el ecosistema de datos de OpenStreetMap (OSM), junto con propuestas de aplicaciones avanzadas.

## 1. Herramientas y Documentación

### [OSM Buildings Viewer JS API](https://osmbuildings.org/documentation/viewer/)
*   **Qué es**: Un motor 3D independiente basado en WebGL para renderizar edificios.
*   **Capacidades**:
    *   Control total de cámara (giro, inclinación, zoom).
    *   Cálculo dinámico de **sombras** según la posición del sol (`.setDate(new Date())`).
    *   Interacción: Selección y resaltado de edificios por ID (`.highlight(id, color)`).
    *   Basado en etiquetas de OSM: `height`, `min_height`, `building:levels`, `building:color`, `roof:shape`.

### [OSM Buildings - Integración con Leaflet](https://osmbuildings.org/documentation/leaflet/)
*   **Qué es**: Una capa específica (`OSMBuildings-Leaflet.js`) para añadir edificios 3D (perspectiva 2.5D) sobre mapas de Leaflet.
*   **Uso**: Se sincroniza perfectamente con el zoom y paneo de Leaflet.
*   **Datos**: Utiliza principalmente **GeoJSON Tiles**, cargando solo lo necesario para el viewport actual.

### [Geofabrik (Descargas OSM)](https://download.geofabrik.de/)
*   **Qué es**: Repositorio principal de extractos de datos de OSM por regiones (países, ciudades).
*   **Formatos para PostGIS**:
    *   `.osm.pbf`: Ideal para importar con `osm2pgsql`.
    *   `.gpkg.zip` (GeoPackage): Formato moderno compatible directamente con PostGIS y QGIS. Es la forma más limpia de obtener capas de edificios ya procesadas.

### [Overpass Turbo](https://overpass-turbo.eu/)
*   **Qué es**: Herramienta de minería de datos web para consultas precisas en la base de datos de OSM.
*   **Uso**: Permite filtrar edificios por atributos específicos (ej: `building:levels > 10`) y exportar a GeoJSON para su uso inmediato en Leaflet o importación a PostGIS.

---

## 2. Propuestas de Aplicaciones

A continuación se presentan 4 propuestas que integran **Leaflet**, **OSM Buildings**, **PostGIS**, **pgVector** y **pgRouting**:

### [A. Mapa de Potencial Solar 3D](solar_potential_map.md)
*   **Visualización**: Leaflet + OSM Buildings para mostrar los edificios en 3D con sus sombras reales según la hora del día.
*   **Lógica (PostGIS)**: Cálculo de áreas de cubiertas (roofs) y orientación (azimuth) mediante funciones espaciales.
*   **Inteligencia (pgVector)**: Almacenamiento de "perfiles de eficiencia" de edificios para recomendar instalaciones similares mediante búsqueda de vecindad.
*   **Logística (pgRouting)**: Optimización de rutas de inspección técnica para visitar los edificios con mayor potencial en una zona determinada.

### B. Navegador Urbano Semántico con Perspectiva 3D
*   **Visualización**: Interfaz 3D que ayuda al usuario a orientarse mediante puntos de referencia visuales (edificios icónicos).
*   **Búsqueda (pgVector)**: Permite búsquedas en lenguaje natural ("edificios modernos de cristal cerca de un parque") convirtiendo las descripciones de las etiquetas de OSM en embeddings.
*   **Navegación (pgRouting)**: Rutas peatonales que consideran la sombra (calculada con OSM Buildings) o la inclinación de las calles.

### C. Plataforma de Análisis Inmobiliario Premium
*   **Visualización**: Modelo 3D del entorno para evaluar el impacto visual y las vistas desde alturas específicas de un edificio.
*   **Análisis (PostGIS)**: Cálculos de "Line of Sight" (línea de visión) 3D para determinar qué se ve desde cada planta.
*   **Similitud (pgVector)**: Encontrar propiedades con entornos urbanos similares (densidad, altura media, servicios cercanos) basándose en vectores de características.
*   **Accesibilidad (pgRouting)**: Cálculo de isocronas de acceso a servicios (POIs) desde el portal.

### D. Planificación de Seguridad y Flujos en Eventos
*   **Visualización**: Simulación de grandes concentraciones de personas en entornos 3D.
*   **Seguridad (PostGIS)**: Identificación de puntos ciegos para cámaras de seguridad basándose en la geometría de los edificios.
*   **Evacuación (pgRouting)**: Cálculo de las rutas de evacuación más rápidas hacia zonas seguras, considerando la capacidad de las vías.
*   **Análisis (pgVector)**: Comparación del layout del evento con configuraciones históricas de éxito/fracaso en entornos urbanos similares.

---

## 3. Workflow de Implementación Sugerido

1.  **Ingesta de Datos**: 
    *   Descargar `.osm.pbf` de **Geofabrik**.
    *   Importar a **PostGIS** usando `osm2pgsql` (esquema `flex` para edificios).
    *   Importar red de carreteras para **pgRouting** con `osm2pgrouting`.
2.  **Enriquecimiento**:
    *   Generar embeddings de las etiquetas de los edificios (tags) y guardarlos en **pgVector**.
3.  **Frontend**:
    *   Capa base con Leaflet.
    *   Capa 3D con `OSMBuildings-Leaflet`.
    *   API en el backend (Python/Django o Node.js) para ejecutar las consultas espaciales y de vectores.