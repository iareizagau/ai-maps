## Why

Las dos capacidades ya promovidas en `amenabar/*` (solar + clima) responden a "cómo es el **edificio** y cómo es el **lugar**" a nivel macro. Falta un dato de contexto ambiental **presente y medible** que un comprador consciente valora: la **calidad del aire que respira**. OpenAQ consolida estaciones oficiales de monitoreo (PM2.5, PM10, NO₂, O₃) en toda España con lecturas en tiempo real; mostrar esa capa opcional sobre el mapa cierra la narrativa ambiental sin invadir la ficha de la promoción.

## What Changes

- Nuevo modelo `AirQualityStation` **sin relación a `Promocion`**: `openaq_id`, `name`, `city`, `country` (hardcoded `"ES"`, un check-constraint lo garantiza), `location` (PointField), 4 columnas de lecturas más recientes (`pm25`, `pm10`, `no2`, `o3` como DecimalField nullable), `measurements_at` (DateTime nullable) y `raw_json` auditable. GIST sobre `location`.
- Nuevo módulo de servicio `services_openaq.py` con:
  - `fetch_openaq_locations_page(bbox, page)` — una página de la API v3 OpenAQ con rate-limit por cortesía.
  - `fetch_latest_for_location(openaq_id)` — lectura más reciente por sensor (parámetro).
  - `sync_openaq_spain()` — pagina sobre el bbox España (lon `[-10, 5]`, lat `[35, 44]`), `update_or_create` por `openaq_id`.
  - Fallo silencioso (`None` + `logger.warning`) ante clave vacía, red o parseo.
- Management command `sync_openaq` idempotente, flag `--force`. Aborta con mensaje claro si `OPENAQ_API_KEY` está vacía (mismo patrón que `backfill_aemet_stations`).
- Nuevo endpoint `GET /amenabar/airquality.json` que devuelve TODAS las estaciones España cacheadas (~500 filas) con sus últimas lecturas, **separado** de `promocion_pois` (no inflamos la respuesta por-promoción con datos globales).
- Capa Leaflet nueva en `src/templates/amenabar/promociones.html`:
  - Nueva sección "Capas globales" en el panel `.amb-ctl`, debajo de "Ver todos", con un toggle "Calidad del aire".
  - Al activarla la primera vez: fetch único a `/amenabar/airquality.json`, pinta `L.circleMarker` por estación coloreado según el índice PM2.5 (breakpoints WHO 2021: verde ≤ 12, amarillo ≤ 35, naranja ≤ 55, rojo > 55 µg/m³).
  - Popup con nombre de estación, parámetro + lectura, y timestamp relativo ("hace 3 h").
  - Degradación: si la fetch falla o no hay estaciones, log + toggle vuelve a off; no rompe el resto del mapa.
- Nueva variable `OPENAQ_API_KEY` en `src/config/settings/base.py` (mismo patrón que `AEMET_API_KEY`).
- Tests pytest sobre fixtures: `fetch_openaq_locations_page` parsea el response, `sync_openaq_spain` idempotente y filtra `country == "ES"`, endpoint devuelve features con el shape esperado, modelo rechaza país distinto de ES vía check-constraint.

Fuera de alcance (futuras propuestas separadas):
- Interpolación IDW u otra para servir un valor "aquí" por promoción. OpenAQ queda como **capa de contexto**, no dato por promoción.
- Capa raster WMS de ruido del MITECO (opción B del spike) — descartada tras ver la densidad actual de la ficha.
- Celery beat para refrescar automáticamente la cache (hoy se ejecuta `sync_openaq` a mano o en bootstrap).
- Panel admin más allá de un `ModelAdmin` básico.

## Capabilities

### New Capabilities
- `amenabar/air-quality`: exponer sobre el mapa de Amenabar una capa toggleable con las estaciones OpenAQ España y sus lecturas más recientes de PM2.5/PM10/NO₂/O₃, cacheadas localmente.

### Modified Capabilities
<!-- Ninguna. Las capacidades existentes (`amenabar/solar-potential`, `amenabar/climate-normals`) no se alteran. -->

## Impact

- **Código**:
  - `src/apps/amenabar/models.py` (añade `AirQualityStation`).
  - `src/apps/amenabar/services_openaq.py` (nuevo).
  - `src/apps/amenabar/management/commands/sync_openaq.py` (nuevo).
  - `src/apps/amenabar/views.py` (nueva vista JSON `airquality`).
  - `src/apps/amenabar/urls.py` (nueva ruta `airquality.json`).
  - `src/apps/amenabar/admin.py` (registro `AirQualityStation` read-only).
  - `src/apps/amenabar/tests/test_openaq.py` + `tests/fixtures/openaq_locations_sample.json` + `tests/fixtures/openaq_latest_sample.json`.
  - `src/apps/amenabar/migrations/0005_airqualitystation.py`.
  - `src/templates/amenabar/promociones.html` (toggle en control + layer Leaflet + CSS leyenda PM2.5).
  - `src/config/settings/base.py` (añade `OPENAQ_API_KEY`).
- **APIs externas**: OpenAQ v3 (`https://api.openaq.org/v3/`), requiere `X-API-Key` gratuita (60 req/min free tier).
- **BD**: una tabla nueva sin FK. Volumen esperado: ~500 filas. No afecta a tablas existentes.
- **Infra**: ninguna. No se añade TiTiler ni servicio Docker (descartados en el spike). Imagen de BD intacta.
- **Despliegue**: tras merge → `migrate` + `sync_openaq` manual la primera vez.
- **Rollback**: `migrate amenabar 0004` revierte la tabla; revertir commit. Cero impacto sobre `Promocion`, `POI`, `SolarPotential`, `AemetStation`, `PromocionClima`.
- **Riesgo**: bajo. Degradación silenciosa si OpenAQ falla; el usuario puede seguir sin la capa. Única superficie nueva de red es la lectura del endpoint `/amenabar/airquality.json`, cacheable con `Cache-Control` corto si en el futuro vemos tráfico.
