# 🗺️ Adventure Lab - Routing System

Este módulo es el "corazón aventurero" de la plataforma. Proporciona herramientas avanzadas de enrutamiento geoespacial, planificación de itinerarios y análisis de terreno para actividades outdoor como bikepacking, senderismo y trekking.

## 🚀 Características Principales (Actuales y en Desarrollo)

### Planificación y Enrutamiento Avanzado
- **Motor de Enrutamiento Inteligente**: Basado en `pgRouting` (Dijkstra), optimizado para diferentes perfiles:
  - 🚲 **Bikepacking**: Prioriza carriles bici y pistas transitables, evitando autopistas.
  - 🥾 **Hiking**: Prioriza senderos y caminos peatonales, ignorando restricciones de tráfico.
- **Planificador Interactivo**:
  - Waypoints arrastrables en tiempo real y enrutamiento multipunto.
  - Inserción dinámica de puntos haciendo clic en cualquier tramo de la ruta.
  - Cierre de ruta automático (Circular).

### Análisis de Terreno y Contexto
- **Desglose de Superficies**: Análisis visual e interactivo de los tipos de terreno (Asfalto, Tierra, Carril Bici).
- **Perfil de Elevación**: Gráfico en tiempo real sincronizado con la posición en el mapa.
- **Red de Hidratación y POIs**: Integración de fuentes de agua potable (`drinking_water`), refugios, cafeterías y estaciones con ### Reconstrucción Forense y Journaling Fotográfico
- **Forensic Route Reconstruction**: Sistema innovador que permite generar rutas completas simplemente subiendo fotografías de la galería.
  - Extrae metadatos EXIF (GPS + Timestamp) directamente en el navegador del usuario para proteger la privacidad y ahorrar datos.
  - Ordena cronológicamente las capturas para trazar el rastro de la expedición sin haber activado el GPS del móvil, ahorrando un 100% de batería durante la actividad.
- **Cinematic Flashbacks**: Las fotos subidas se convierten automáticamente en **Intel Drops** vinculados a la ruta. Durante el *3D Flyover*, la cámara detecta estos puntos y muestra la fotografía en una tarjeta cinemática inmersiva, creando un recuerdo documental del viaje.

### Navegación y Seguimiento
- **Tactical HUD (AMOLED Optimized)**: Interfaz de seguimiento en vivo diseñada para alta visibilidad y bajo consumo.
  - Visualización en tiempo real de la posición sobre el mapa.
  - Telemetría básica y control de misión.

### Interacción y Visualización 3D (Premium Experience)
- **3D Cinematic Flyover**: Animación 3D del recorrido (estilo Relive evolucionado), implementado nativamente. Ahora con soporte para **pausas cinemáticas en puntos de interés fotográfico**.
- **UI/UX Moderna**: Interfaces inmersivas utilizando patrones "glassmorphism", diseñadas para sentirse premium y fluidas.

### Reportes Tácticos e Inteligencia Colaborativa
- **Intel Drops**: Sistema de reportes tácticos en ruta (estilo Waze para montaña).
  - Alertas de peligro, fuentes secas, barro excesivo, nieve, o estado de refugios.
  - **Cinematic Journaling**: Posibilidad de añadir fotos geolocalizadas ("Lugares Épicos") a lo largo del recorrido.

### Ecosistema e Integración
- **Importación/Exportación**: 
  - Descarga nativa de rutas en formato **GPX**.
  - Sistema robusto de importación de GPX e integración de datos de fitness externos (Komoot, Strava, Wikiloc).
- **Dashboard y Gestión**: Panel personal de rutas guardadas, vistas detalladas de rutas, y sección de exploración comunitaria.

---

## 📊 Análisis de Competencia y Posicionamiento

Para construir la mejor experiencia, hemos analizado a los líderes del sector, identificando sus puntos fuertes y débiles para definir nuestra ventaja competitiva. El objetivo es entender qué funcionalidades ofrecen para inspirarnos y superarlos en nuestro nicho.

### 1. Komoot
- **Puntos Fuertes**: Excelente motor de rutas (turn-by-turn), desglose detallado de superficies y tipos de vía. Su función de "Highlights" (recomendaciones de la comunidad con fotos y tips) es la mejor del mercado para descubrir lugares. Fuerte enfoque en cicloturismo y bikepacking.
- **Puntos Débiles**: Modelo de pago por regiones confuso/caro. A veces el algoritmo fuerza rutas por caminos en mal estado o intransitables si los datos de OpenStreetMap son erróneos o están desactualizados.
- **Nuestra Mejora (Adventure App)**: Incorporamos el análisis detallado de superficies de Komoot, pero le añadimos nuestros **Intel Drops** en tiempo real. Si un camino está cortado o hay barro excesivo, nuestros usuarios lo reportan y se refleja al instante, dándole una capa de "frescura" vital que Komoot no posee.

### 2. Strava
- **Puntos Fuertes**: La red social definitiva para deportistas. Segmentos, leaderboards y **Heatmaps** (mapas de calor) insuperables gracias a su masiva base de usuarios activos. Gran análisis de rendimiento físico.
- **Puntos Débiles**: El enrutamiento se basa casi exclusivamente en popularidad ("por dónde va más gente"), lo que dificulta descubrir rutas alternativas o "caminos ocultos". Pobre integración de POIs vitales para aventureros (fuentes, refugios). Plan de suscripción cada vez más caro.
- **Nuestra Mejora (Adventure App)**: Nos alejamos de la competitividad de los tiempos y segmentos para centrarnos puramente en la **aventura, exploración y supervivencia**. Ofrecemos POIs críticos hiper-detallados (estado de las fuentes de agua) y permitimos importar rutas desde Strava para enriquecerlas con nuestro análisis de terreno y visualización 3D.

### 3. Wikiloc
- **Puntos Fuertes**: Base de datos gigantesca de rutas grabadas y subidas por usuarios (dominante en España y Latam). Cubre casi cualquier actividad outdoor. Muy buena funcionalidad de seguimiento y mapas offline en la app móvil.
- **Puntos Débiles**: Cero control de calidad (cualquiera sube cualquier cosa, resultando en rutas duplicadas, con errores, o cruzando fincas privadas). El planificador web es muy rudimentario. Interfaz algo anticuada.
- **Nuestra Mejora (Adventure App)**: Ofrecemos un **planificador de rutas interactivo, dinámico y de calidad profesional**. En lugar de depender del "ruido" masivo de tracks no curados, usamos herramientas algorítmicas (pgRouting) sobre una red vial consolidada para asegurar que los trazados planificados sean lógicos, legales y seguros.

### 4. Relive
- **Puntos Fuertes**: Generación de vídeos 3D cinemáticos del recorrido mezclados con fotografías.
- **Nuestra Mejora (Adventure App)**: En Relive, el video es un archivo estático. En Adventure, el **Flyover es interactivo**. Puedes pausar, mover la cámara, ver los detalles técnicos del terreno y, lo más importante, no necesitas una app externa para generar el recuerdo; ocurre instantáneamente al reconstruir tu ruta forense.

---

## 🛑 Estado Actual e Innovaciones Recientes

**Estado Actual (Implementado):**
- **Motor Forense**: Implementada la lógica cliente-servidor para reconstruir rutas desde EXIF.
- **API Multi-part**: Endpoint `/api/adventure/routes/forensic` que procesa geometría y archivos de imagen simultáneamente para crear una base de datos de "evidencias" (IntelDrops).
- **Cinematic Sync**: El reproductor 3D ahora sincroniza la posición de la cámara con los IntelDrops de tipo `photo_epic`.
- **Tactical HUD**: Primera versión funcional de la interfaz de seguimiento AMOLED.

**Siguientes Pasos:**
1. **Compresión en Cliente**: Implementar `canvas` o `pica` para redimensionar las fotos antes de la subida forense, optimizando el almacenamiento.
2. **Offline Maps**: Cacheo de tiles de mapa para el Tactical HUD en zonas de zero cobertura.
3. **Validación de Terreno Forense**: Cruzar los puntos de las fotos con `pgRouting` para "ajustar" la línea recta entre fotos a los senderos reales existentes en la base de datos.

---

## 🛠️ Stack Tecnológico

- **Backend**: Django + Django Ninja (API multipart).
- **Base de Datos**: PostgreSQL + PostGIS (Geometrías y Proximidad).
- **Frontend**: MapLibre GL JS + exifr (Extracción de metadatos) + turf.js (Cálculos geoespeciales).
- **Diseño**: Tailwind CSS + Glassmorphism Custom Patterns + AMOLED optimized UI.

---
*Desarrollado con ❤️ para aventureros que valoran su batería y sus recuerdos.*

## 📂 Estructura del Módulo

- `api.py`: Endpoints para enrutamiento, POIs, Intel Drops y sincronización.
- `selectors.py`: Lógica de consulta SQL pura para pgRouting.
- `models.py`: Modelos de base de datos (`TrailEdge`, `Fountain`, `Route`, `PointOfInterest`, `IntelDrop`).
- `urls.py` & `views.py`: Vistas del frontend (Dashboard, Explorador, Detalle de ruta y Mapa).
- `management/commands/`: Scripts de importación y procesamiento de datos geográficos.
- `src/templates/adventure/`: Vistas de usuario interactivas (map, dashboard, route_detail). Siguiendo las convenciones del proyecto, los templates residen en la carpeta global `src/templates`.
- `src/templates/cotton/adventure/`: Arquitectura "Domain-Driven UI" usando `django-cotton`. Aquí se encapsulan los componentes reutilizables y atómicos específicos del dominio de aventura (ej. `<c-adventure.expedition_card />`, `<c-adventure.flight_deck />`), mejorando la escalabilidad y limpieza del código (estilo React/Vue renderizado en servidor).
## 📥 Ingesta de Datos

Para poblar la base de datos con fuentes de agua:
```bash
python manage.py import_fountains
```

Para recalcular los costes de la red vial (bikepacking/hiking):
```bash
# Ejecutar el script SQL definido en scripts/define_costs.sql
```

---
*Desarrollado con ❤️ para aventureros.*
