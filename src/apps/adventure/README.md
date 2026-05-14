# 🗺️ Adventure Lab - Routing System

Este módulo es el "corazón aventurero" de la plataforma. Proporciona herramientas avanzadas de enrutamiento geoespacial, planificación de itinerarios y análisis de terreno para actividades outdoor como bikepacking, senderismo y trekking.

## 🚀 Características Principales

- **Motor de Enrutamiento Inteligente**: Basado en `pgRouting` (Dijkstra), optimizado para diferentes perfiles:
  - 🚲 **Bikepacking**: Prioriza carriles bici y pistas transitables, evitando autopistas.
  - 🥾 **Hiking**: Prioriza senderos y caminos peatonales, ignorando restricciones de tráfico.
- **Planificador Interactivo**:
  - Waypoints arrastrables en tiempo real.
  - Inserción dinámica de puntos haciendo clic en cualquier tramo de la ruta.
  - Cierre de ruta automático (Circular).
- **Análisis de Terreno**:
  - Desglose visual de superficies (Asfalto, Tierra, Carril Bici).
  - Perfil de elevación interactivo sincronizado con la posición en el mapa.
- **Hidratación y POIs**:
  - Integración de fuentes de agua potable (OSM `drinking_water`) con carga por proximidad.
- **Exportación**:
  - Descarga nativa de rutas en formato **GPX** para dispositivos GPS.

## 🛠️ Stack Tecnológico

- **Backend**: Django + Django Ninja (API ultra-rápida).
- **Base de Datos**: PostgreSQL + PostGIS + pgRouting + PostGIS Raster.
- **Frontend**: MapLibre GL JS + Chart.js.
- **Datos**: OpenStreetMap (via Geofabrik y Overpass API).

## 📂 Estructura del Módulo

- `api.py`: Endpoints para enrutamiento y puntos de interés.
- `selectors.py`: Lógica de consulta SQL pura para pgRouting.
- `models.py`: Definición de tramos (`TrailEdge`) y fuentes (`Fountain`).
- `management/commands/`: Scripts de ingesta de datos (OSM).
- `templates/adventure/map.html`: Interfaz de usuario del planificador.

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
*Desarrollado con ❤️ para aventureros del País Vasco.*
