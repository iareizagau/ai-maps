## Context

Ver `proposal.md — Why` para la motivación. Estado técnico de partida:

- La capacidad `amenabar/solar-potential` ya existe (promovida al main spec al archivar el change `amenabar-pvgis-solar`). El patrón de ingesta usado ahí es la referencia: modelo cacheado 1:1 con `Promocion`, service en módulo propio, management command idempotente con `--force`/`--slug`, endpoint `promocion_pois` extendido con un bloque retrocompatible, Cotton molecule + gemelo JS en el panel Leaflet.
- Pila ya probada: Django 6, PostGIS (`ST_Distance`, GIST indexes), pytest-django, Celery disponible pero no usado por decisión explícita del MVP previo.
- Fuente externa: **AEMET OpenData** (`https://opendata.aemet.es/opendata/api`). Peculiaridad: la primera llamada no devuelve los datos sino un sobre `{estado: 200, datos: "https://opendata.aemet.es/opendata/sh/…json", metadatos: "…"}`; hay que hacer un segundo GET a `datos` para recibir el JSON real. Requiere clave gratuita por email.
- Convenciones (ver `.claude/CLAUDE.md`): mobile-first base 375 px, `gettext_lazy`, `|unlocalize` para floats en URLs, autoreload off (restart `web_maps`), imagen BD inmutable, `pyproject.toml` ya incluye `src/apps/amenabar/tests` en `testpaths`.

## Goals / Non-Goals

**Goals:**

- Entregar tres series mensuales (Tª media, precipitación, horas de sol) **cacheadas** por promoción, consumibles sin latencia por la ficha pública.
- Separar la responsabilidad del inventario de estaciones (dataset estable, ≈850 filas) de la de cálculo por promoción (más dinámico).
- Blindar la ficha ante fallos de AEMET y ante zonas donde no haya una estación suficientemente cerca.
- Reusar el patrón visual de `solar_card.html` para que la ficha se perciba como una unidad.

**Non-Goals:**

- Datos diarios, históricos, pronóstico, radar o avisos meteorológicos.
- Interpolación entre estaciones. Si la más cercana está > 50 km, no se interpola — se omite.
- Fallback a OpenWeatherMap, Euskalmet, u otras fuentes si AEMET falla.
- Signal/task Celery para recomputar automáticamente al scrapear nuevas promociones (se dejará para otra propuesta tras validar demanda).
- Pantallas de administración más allá del `ModelAdmin` básico de solo-lectura.
- Caché HTTP del segundo GET (la URL `datos` caduca en 1h según AEMET, no hay valor cacheándola).

## Decisions

### Dos modelos separados: inventario y hecho por promoción

**Decisión:** `AemetStation` (inventario) + `PromocionClima` (1:1 con `Promocion`, FK a estación).

**Por qué:**
- El inventario es un dataset de referencia que apenas cambia; separado permite sincronizarlo con un comando propio (`backfill_aemet_stations`) y revisar su cobertura sin tocar los datos por promoción.
- Guardar la FK a la estación permite auditar por qué una promoción tiene los datos que tiene (incluyendo la distancia resuelta en el momento del cálculo), y recomputar sólo las promociones afectadas si la red de estaciones cambia.
- Reusa exactamente el mismo patrón 1:1 que `SolarPotential`, lo que simplifica revisión y mantiene coherencia.

**Alternativa descartada:** sólo `PromocionClima` con `station_name` denormalizado. Más rápido en el momento pero pierde la trazabilidad y complica recomputar por cambios de la red.

### Umbral de 50 km con nearest spatial query

**Decisión:** `AemetStation.objects.annotate(d=Distance("location", point)).order_by("d").first()` filtrado por `d <= 50 km`. Fuera → `None` → tarjeta oculta.

**Por qué:**
- 50 km es un corte razonable para que las normales sigan siendo representativas en zonas con relieve suave; en Euskadi/Navarra, las promociones en interior pueden caer a > 20 km de la estación costera más cercana — queremos aceptarlas; a > 50 km, prefiero omitir que mentir.
- `ST_Distance` sobre `geography` da el resultado correcto en metros; se guarda en `distance_m` para auditoría y UI.

**Alternativa descartada:** usar la estación de la misma provincia aunque esté más lejos. Añade un criterio administrativo irrelevante para el clima.

### Indirección 2-step de AEMET aislada en un helper único

**Decisión:** una función interna `_aemet_get(path) -> dict | list` que hace los dos GETs encadenados (primero `{api_base}{path}?api_key=…`, luego la URL devuelta en `datos`). El resto del service llama sólo a este helper.

**Por qué:**
- El patrón 2-step es una peculiaridad de **AEMET**, no del dominio. Encapsularlo evita que fugue a cada función de alto nivel.
- Facilita el testing: un fixture simula ambas respuestas sin que las funciones de dominio lo sepan.
- Facilita añadir reintentos específicos a la segunda llamada si AEMET se pone pesado (hoy no se añaden; la degradación silenciosa cubre el caso).

**Alternativa descartada:** llamada única y gestionar la indirección en cada función. Duplicaría parsing y oscurecería los flujos.

### Dos management commands separados

**Decisión:** `backfill_aemet_stations` y `backfill_aemet_clima` como entradas CLI independientes.

**Por qué:**
- Diferente cadencia: el inventario cambia cada muchos meses; el clima por promoción se recomputa cuando se incorporan nuevas promociones o se fuerza por cambios de criterio.
- Operacionalmente, en producción el primero se ejecuta una vez al desplegar; el segundo es parte del pipeline recurrente de ingesta.
- `backfill_aemet_clima` SHALL depender implícitamente de que el inventario exista: si está vacío, cada promoción quedará sin estación. Esto se documenta en el `help` del comando, no se fuerza por código (coste bajo, suficiente para MVP).

### Fallo silencioso + `raw_json` persistido (reuso del patrón PVGIS)

**Decisión:** fallos de red, parseo o AEMET sin clave → `logger.warning(...)` y `None`. `raw_json` conservado por fila (en estación y clima) para auditoría y reingesta sin repetir la llamada.

**Por qué:**
- Mantiene la ficha pública viva frente a cualquier incidencia externa.
- Mismo patrón que `services_pvgis.py` → cero sorpresas al revisar.

### Endpoint retrocompatible con nuevo bloque opcional `clima`

**Decisión:** extender la respuesta de `promocion_pois` con una clave `clima` que será un objeto con `station`, `distance_m`, `temp_mean`, `precipitation`, `sun_hours`, `period` o `null`.

**Por qué:**
- Mismo patrón que `solar`: el frontend sólo pinta la sección si existe.
- Cero riesgo para clientes externos (si los hubiera).

### Componente Cotton + gemelo JS

**Decisión:** `cotton/molecules/climate_card.html` como referencia canónica (prop estructurado) + implementación JS `_climateBlock(clima)` dentro de `promociones.html` para el panel Leaflet.

**Por qué:**
- Es la misma dualidad que ya resolvimos para solar. Mantener la coherencia visual exige el gemelo JS; mantener la coherencia de Atomic Design exige el Cotton; coste bajo.
- Los tres mini-climogramas se apilan vertical (base 375 px), con la misma altura 56 px y marcadores de meses abreviados, para que la pila "solar + clima" se lea como un único módulo.

### Variable de entorno con el patrón ya establecido

**Decisión:** `AEMET_API_KEY = env("AEMET_API_KEY", default="")` en `base.py`, análoga a `EUSKALMET_API_KEY` y `ESIOS_TOKEN`. Si está vacía, el service degrada silenciosamente a `None`.

**Por qué:** cero fricción con el patrón del proyecto; permite que la implementación avance con fixtures sin bloquear hasta que llegue la clave.

## Risks / Trade-offs

- **Riesgo:** cobertura AEMET irregular — Donostia, Vitoria, Bilbao, Pamplona, Madrid y aglomeraciones mediterráneas tienen estación cerca; algunos pueblos pequeños del catálogo de Amenabar pueden quedar fuera del umbral 50 km.
  **Mitigación:** la tarjeta se omite limpiamente; el resto de la ficha sigue siendo útil. Si al correr el backfill real vemos > 20 % de promociones sin tarjeta, revisamos el umbral (no modificamos el modelo).
- **Riesgo:** segundo GET de AEMET con URL firmada que caduca.
  **Mitigación:** una llamada seguida de otra en el mismo `requests.Session` dentro de `_aemet_get`; no persistimos la URL `datos`.
- **Riesgo:** cambios de schema entre estaciones (nombres de campos `tm_mes`, `p_mes`, `inso` o similares varían según documentación AEMET).
  **Mitigación:** `raw_json` persistido + parseo defensivo (si falta un campo, el valor del mes queda `None` y la serie se guarda igualmente). Logs explícitos.
- **Riesgo:** latencia del 2-step pesa sobre backfill grande (~850 llamadas estación + ~100 llamadas clima).
  **Mitigación:** rate-limit 1 req/s por cortesía + backfill offline en Celery/CLI, nunca síncrono en request.
- **Riesgo:** licencia/atribución de AEMET.
  **Mitigación:** AEMET exige atribución visible. La tarjeta llevará nota "Datos: AEMET" como pie, análoga a la ya existente en el footer del panel con OpenStreetMap.
- **Trade-off:** no se usa Celery de inicio → disciplina operativa (correr el comando tras cada scrape). Aceptable para MVP; mismo compromiso que PVGIS.
- **Trade-off:** umbral 50 km fijo, sin parametrización. Si en el futuro Amenabar entra en zonas rurales profundas, se parametriza por settings.

## Migration Plan

1. **Dev:**
   - `docker compose exec web_maps python manage.py makemigrations amenabar` → `0004_aemetstation_promocionclima.py`.
   - `docker compose exec web_maps python manage.py migrate`.
   - Dar de alta `AEMET_API_KEY` en `.env` (si aún no está).
   - `docker compose exec web_maps python manage.py backfill_aemet_stations` (una vez, idempotente).
   - `docker compose exec web_maps python manage.py backfill_aemet_clima` para rellenar las promociones.
   - `docker compose restart web_maps` tras cambios Python.
2. **Prod:** mismo orden en `scripts/deploy.sh` (`migrate` ya corre; añadir dos líneas opcionales para los dos backfills la primera vez, luego sólo `backfill_aemet_clima` cuando entran nuevas promociones).
3. **Rollback:** `migrate amenabar 0003` revierte las dos tablas nuevas (son hojas, sin FK saliente excepto a `Promocion`). Revertir commit del código. Cero impacto sobre `Promocion`, `POI` o `SolarPotential`.

## Open Questions

- ¿Qué hacemos cuando un municipio tiene varias estaciones y la más cercana es un pluviómetro básico sin horas de sol? Hipótesis MVP: aceptar la más cercana y guardar los campos faltantes como `None`. Si al correr el backfill real descubrimos que esto deja muchas tarjetas con huecos feos, en una propuesta posterior podríamos elegir "la estación más cercana que tenga las tres series completas". No cambia specs ni tareas.
