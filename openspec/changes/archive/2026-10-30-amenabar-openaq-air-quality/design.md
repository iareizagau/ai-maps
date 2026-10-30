## Context

Ver `proposal.md — Why` para la motivación. Estado técnico de partida:

- Las capacidades `amenabar/solar-potential` y `amenabar/climate-normals` ya están promovidas al main spec; ambas comparten patrón de **dato por promoción** (modelo 1:1, service, backfill, extensión de `promocion_pois`, tarjeta Cotton + gemelo JS en el panel). Este change rompe deliberadamente ese patrón: OpenAQ es una **capa global** del mapa, no un dato por promoción.
- Pila: Django 6, PostGIS, pytest-django. Leaflet con Alpine-free vanilla en `promociones.html` ya tiene control de capas (`.amb-ctl`) con 3 secciones (Estado / Radios / Ver todos) construidas por `_controlHTML()` y una toggle-handler que mapea `kind:code` a `_getLayer(kind, code)`.
- Fuente externa: **OpenAQ v3** (`https://api.openaq.org/v3/`). Requiere cabecera `X-API-Key` desde 2024. Free tier: 60 req/min. Endpoints relevantes:
  - `GET /v3/locations?bbox=minLon,minLat,maxLon,maxLat&limit=1000&page=N` — devuelve estaciones con sus sensores. Cada `location` incluye `id`, `name`, `locality` (ciudad), `country.code` (ISO2), `coordinates.latitude`, `coordinates.longitude`, y una lista de `sensors` con `parameter.name` y `latest.value`/`datetime`.
  - El endpoint `locations` ya trae `latest` por sensor; no hace falta un segundo GET por estación salvo que queramos valores históricos. **Decisión** (ver abajo): usar sólo lo que viene en `/locations` y ahorrar llamadas.
- Convenciones (ver `.claude/CLAUDE.md`): mobile-first 375 px, `gettext_lazy`, autoreload off (restart `web_maps`), imagen BD inmutable, `pyproject.toml` ya incluye `src/apps/amenabar/tests` en `testpaths`. Ya existen patrones probados de fallo silencioso (`services_pvgis.py`, `services_aemet.py`).

## Goals / Non-Goals

**Goals:**

- Capa de contexto ambiental **toggleable** sobre el mapa, cargable bajo demanda (fetch perezoso).
- Reutilizar el control de capas ya existente (`_controlHTML()`, `_getLayer()`) con una sección nueva y un `kind` nuevo.
- Blindar el mapa frente a cualquier fallo de OpenAQ: el toggle vuelve a off y el resto del mapa sigue vivo.
- Volumen bajo (~500 estaciones España): servir todas en un único JSON evita paginación en el cliente.

**Non-Goals:**

- Interpolación "aquí hay esta calidad" para una promoción. OpenAQ es contexto, no dato por-promoción.
- Capa WMS de ruido MITECO (opción B del spike): aparcada.
- Celery beat: por ahora el `sync_openaq` se corre a mano.
- Histórico de lecturas (series temporales): sólo la lectura más reciente por parámetro.
- Panel admin más allá de `ModelAdmin` básico.

## Decisions

### Un único modelo, sin FK a `Promocion`

**Decisión:** `AirQualityStation` como entidad independiente. Las columnas de lectura (`pm25`, `pm10`, `no2`, `o3`) se mantienen denormalizadas en la propia fila como DecimalField nullable; también `measurements_at` para el timestamp más reciente de **la estación** (max de los sensores).

**Por qué:**
- Es una **capa global**, no un atributo de la promoción. Mantenerlas separadas evita ensuciar `Promocion` y no obliga a recomputar nada por promoción cuando cambian las lecturas.
- Denormalizar las 4 columnas en la fila (en vez de una tabla hija de `Measurement`) hace trivial el endpoint y evita joins. OpenAQ tiene decenas de parámetros pero PM2.5/PM10/NO₂/O₃ son los que un buyer entiende; filtramos a esos cuatro en el service.
- Mantiene coherencia con `AemetStation` (otra "estación" independiente) para que un revisor del repo detecte el patrón sin esfuerzo.

**Alternativa descartada:** tabla hija `AirQualityMeasurement(station, parameter, value, measured_at)`. Más limpia a largo plazo pero overkill para "última lectura" y añadiría un join por estación en el endpoint.

### Un check-constraint que fuerza `country == "ES"`

**Decisión:** `models.CheckConstraint(check=Q(country="ES"), name="aqs_country_es_only")`.

**Por qué:**
- La capacidad es España-only por diseño; el constraint convierte la decisión en invariante y evita que un bug futuro (bbox mal configurado) meta estaciones de Portugal o Francia en el cache.
- Coste cero y falla ruidosa en el `update_or_create` si pasa.

**Alternativa descartada:** validar sólo en el service. Menos fuerte; un script ad-hoc que escriba directo saltaría la validación.

### Usar lo que trae `/v3/locations` sin segundo GET

**Decisión:** `fetch_openaq_locations_page()` pagina `/v3/locations?bbox=…&limit=1000` y toma los `latest.value`/`datetime` que ya trae cada sensor. No se llama a `/v3/sensors/{id}/measurements` por estación.

**Por qué:**
- Un sync completo España cabe en una decena de páginas, dentro del free tier (60 req/min) sin estrés.
- Un segundo GET por estación serían ~500 req extra por sync. Innecesario para el MVP.
- Si en el futuro queremos series históricas, abrimos propuesta aparte.

### Rate-limit por cortesía + fallo silencioso

**Decisión:** `OPENAQ_RATE_S = 0.5` entre páginas, timeout 30 s, `try/except → logger.warning + continue`. Clave vacía → el comando aborta con mensaje humano.

**Por qué:** mismo patrón que `services_aemet.py`. Zero crash en el frontend.

### Endpoint separado `/amenabar/airquality.json`

**Decisión:** nueva vista `airquality` montada en `urls.py` con nombre `amenabar:airquality`. Devuelve `{"stations": [...]}` sin paginación.

**Por qué:**
- Separa concerns: `promocion_pois` ya se usa por promoción; mezclar aquí ~500 estaciones hincha cada respuesta en ~10× sin razón.
- Permite cachearlo con `Cache-Control: max-age=600` más adelante sin afectar a la ficha.
- Shape más simple en el JS: fetch una vez por sesión y cachear en `this.aqStations`.

**Alternativa descartada:** meterlo en `promociones_data` embebido en la plantilla. Infla el `json_script` inicial con datos que la mayoría de visitas no activa.

### Toggle en el control existente con `kind` nuevo

**Decisión:** nueva sección "Capas globales" en `_controlHTML()`, con un `kind=global`. En `_getLayer('global', 'air')` devuelve `this.airQualityLayer`. Al checkear, si `aqStations` aún no está cargado → fetch, luego paint; si falla, el checkbox vuelve a off programáticamente y se loggea.

**Por qué:**
- Reusa el handler de cambios existente (`panel.addEventListener('change', ...)`) sin romperlo.
- Fetch perezoso: el 99 % de visitas no activa el toggle y no pagamos la red innecesariamente.

### Breakpoints WHO 2021 para PM2.5

**Decisión:** colores verde ≤ 12 / amarillo ≤ 35 / naranja ≤ 55 / rojo > 55 µg/m³ (24h). Estación sin PM2.5 → gris neutro.

**Por qué:**
- WHO 2021 es la referencia internacional actual y es más estricta que el AQI americano, lo que refuerza la honestidad del dato.
- PM2.5 es el parámetro con mayor impacto sanitario documentado y el más comparable entre países.
- No usamos `aqicn` ni similar: añadiría un cálculo compuesto y una dependencia conceptual más.

### Legenda inline en el control, no overlay flotante

**Decisión:** 4 cuadritos de color + label textual bajo el toggle, dentro del propio `.amb-ctl`. Mobile-first: ≤ 220 px de ancho total.

**Por qué:**
- Un overlay flotante en una esquina compite con el popup y con la tarjeta de nearest. Dentro del control, el usuario lo descubre cuando activa la capa.
- Reutiliza el estilo `.amb-dot` ya existente.

## Risks / Trade-offs

- **Riesgo:** OpenAQ v3 cambia el shape de `/locations` o la estructura `sensors[].latest`.
  **Mitigación:** `raw_json` persistido por estación + parseo defensivo (si falta un campo, la lectura queda `None`).
- **Riesgo:** 500 estaciones es más de lo que Leaflet renderiza fluido como `circleMarker` individuales en móvil antiguo.
  **Mitigación:** `circleMarker` (vector, no DOM nodes) suele aguantar 1-2k sin problema. Si vemos lag, pasamos a `L.canvas()` como renderer dedicado en una propuesta posterior; no cambia ni spec ni modelo.
- **Riesgo:** la fetch inicial de ~100 KB bloquea al activar la capa en 3G.
  **Mitigación:** pintamos conforme llega (resp.json() es síncrono tras recibir el payload; es aceptable). Si fuera un problema real, se añadiría `Cache-Control` + spinner. Hoy no.
- **Riesgo:** usuarios asumen que el valor OpenAQ es el valor "exacto donde está la promoción".
  **Mitigación:** popup y leyenda hablan de "estación", no de "aquí". El toggle se llama "Calidad del aire".
- **Trade-off:** sin Celery beat, los valores no se refrescan solos; dependemos de ejecutar el `sync_openaq` manual o desde `bootstrap.sh`. Aceptable para MVP; se cubre en propuesta aparte si Amenabar quiere "en tiempo real".
- **Trade-off:** parámetros fijos (PM2.5/PM10/NO₂/O₃). Si una estación mide, p. ej., SO₂, lo guardamos sólo en `raw_json`. Resuelto por diseño; el modelo cubre lo que el buyer entiende.

## Migration Plan

1. **Dev:**
   - `docker compose exec web_maps python manage.py makemigrations amenabar` → `0005_airqualitystation.py`.
   - `migrate amenabar`.
   - Dar de alta `OPENAQ_API_KEY` en `.env` (si aún no está).
   - `docker compose exec web_maps python manage.py sync_openaq` (una vez; luego a demanda).
   - `docker compose restart web_maps`.
2. **Prod:** mismo orden en `scripts/deploy.sh`.
3. **Rollback:** `migrate amenabar 0004` revierte la tabla; revertir commit del código. Cero impacto sobre tablas existentes.

## Open Questions

- ¿Qué timestamp consideramos "demasiado viejo" para colorear una estación? Hipótesis MVP: cualquier lectura PM2.5, aunque sea de hace semanas, cuenta — es dato oficial, y si una estación lleva meses sin reportar seguramente OpenAQ ya no la devuelve. Si al correr `sync_openaq` real vemos lecturas de hace > 7 días en volumen, podemos añadir `is_stale` client-side. No cambia specs ni tareas.
