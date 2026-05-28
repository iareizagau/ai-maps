![1779832249241](image/SESSION_STATE/1779832249241.png)![1779832254381](image/SESSION_STATE/1779832254381.png)# Mubil — Session State (snapshot para reanudar)

**Última actualización:** 2026-05-28
**Deadline confirmado:** **2026-06-19** (22 días naturales / ~15 hábiles desde hoy)
**Objetivo activo:** `ask` MUST — validación end-to-end + ingesta full corpus + embed
**Reanudar leyendo:** este archivo §0 (último avance) → §4 (próximos pasos) → §2 (issues conocidos)

---

## 0. Avance sesión 2026-05-28 (`ask` MUST escrito, pendiente validar live)

**Escrito + listo para correr (todo bajo `src/apps/mubil/ask/`):**

| Pieza | Archivo | Tests | Estado |
|---|---|---|---|
| Ingest CKAN datos.gob.es | `ask/ingest.py` | 12 verde | **live-validado**: 5 docs reales en DB, 40+ por theme |
| Embedding service Gemini | `ask/embeddings.py` | 10 verde (mocked) | live test pendiente |
| RAG pipeline | `ask/services.py` | ~10 verde (mocked) | live test pendiente |
| Schemas Ninja | `ask/schemas.py` | — | — |
| API endpoints | `ask/api.py` | — | `/health`, `/suggested`, `/corpus/stats`, `POST /query` |
| HTMX view | `views.py:77-103` (`ask_query`) | — | wired en `urls.py` |
| Templates | `templates/mubil/ask.html` + `_ask_result.html` | — | con 5 prompts gold pre-cargados |
| Mgmt commands | `ingest_ask_corpus`, `embed_ask_corpus` | — | con `--dry-run` |

**Decisiones tomadas:**
- Modelo embeddings: `text-embedding-004` (768d), modelo gen: `gemini-2.0-flash`. Configurables vía `GEMINI_EMBEDDING_MODEL`/`GEMINI_GENERATION_MODEL` en settings.
- Estrategia: **ingesta-first** (corpus poblado antes de embed batch).
- Fuentes MVP: **solo CKAN** datos.gob.es theme=transporte (~500 docs estimados).
- OpenData Euskadi **diferido** — sólo si CKAN <500 docs o pitch necesita sesgo EH.
- Pipeline RAG: top-k=8, sin re-ranking, sin streaming, MIN_SCORE=0.40 para descartar matches débiles.

**Cambios de infra:**
- `requirements.txt`: añadido `google-generativeai>=0.8`.
- `settings/base.py:209-213`: vars `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL`, `GEMINI_GENERATION_MODEL`.
- **`GEMINI_API_KEY` está en `src/.env` línea 1 (39 chars) Y `.env` raíz línea 12** — el contenedor lee del `.env` raíz vía `env_file`. **⚠️ Key expuesta en log de sesión del 2026-05-28 (cat / od) — considerar rotación.**
- `.dockerignore`: añadido `*.pbf`, `*.osm*`, `*.parquet`, `src/temp_*`, etc. Build context bajó de 3.74 GB → ~70 MB.
- `docker-compose.override.yml`: **eliminado** debugpy + puerto 5678:5678. Ahora `command: python manage.py runserver 0.0.0.0:9000 --noreload`.

**Bugs encontrados y corregidos durante live-validation del CKAN:**
- Endpoint correcto: `GET /apidata/catalog/dataset/theme/{slug}` (no `?theme=URI`).
- URL de cada dataset está en `_about`, no `@id`.

**Pendiente de la sesión que viene:**

```bash
# Suite completa (debería pasar 35+ tests, ya pasaron en mock)
docker exec maps_web python manage.py test apps.mubil --noinput

# Ingesta completa CKAN (~500 docs reales, ~30-60s)
docker exec maps_web python manage.py ingest_ask_corpus --source=ckan

# Embed batch del corpus (~500 calls Gemini, ~50-90s con throttle 0.1s)
docker exec maps_web python manage.py embed_ask_corpus

# Smoke test live del endpoint RAG
curl -X POST http://localhost:9000/mubil/api/v1/ask/query \
  -H "Content-Type: application/json" \
  -d '{"q":"¿Qué ayudas MOVES III hay en Bizkaia?"}'

# Visual UI con prompts gold
# → http://localhost:9000/mubil/ask/
```

---

---

## 1. Lo que está terminado y funcionando

### Backend de la app `mubil`

- App Django `src/apps/mubil/` scaffolded (apps.py, models, schemas, services, api, views, urls, admin, tests, management, migrations).
- Wired en [src/config/settings/base.py](src/config/settings/base.py) (`apps.mubil` añadido a `INSTALLED_APPS`) y [src/config/urls.py](src/config/urls.py) (`path('mubil/', include('apps.mubil.urls'))`).
- 9 modelos creados y migrados:
  Vehicle · FuelStation · ChargingStation · EnergyPricePVPC · EVRegistration · MobilityTrip · MobilityDocument · DemandHex · EVRoutePlan.
- Migración 0001 incluye `CREATE EXTENSION IF NOT EXISTS vector` (necesario para tests).
- Migración 0002 aplica:
  - TimescaleDB hypertables sobre `EnergyPricePVPC.timestamp` y `MobilityTrip.date` con PK compuesta `(id, partition_col)`.
  - Índice pgvector ivfflat `mubil_mobdoc_emb_ivf` (cosine, lists=100).
- AppRegistry entry creado: slug `mubil`, name `Mubil Maps`, icon `route`, color `#06b6d4` cyan, `is_featured=True`. *(Naming display provisional — re-evaluar antes de envío MUBIL).*

### Módulo `advisor` MUST — end-to-end

- Cálculo TCO determinista en [src/apps/mubil/advisor/services.py](src/apps/mubil/advisor/services.py) — pure function `calculate_tco_quote`.
- Constantes de precio en [src/apps/mubil/data/price_defaults.py](src/apps/mubil/data/price_defaults.py) (placeholder hasta token ESIOS).
- Centroides CP hardcoded en [src/apps/mubil/data/cp_centroids.py](src/apps/mubil/data/cp_centroids.py) (12 CPs EH).
- Endpoints Ninja en [src/apps/mubil/advisor/api.py](src/apps/mubil/advisor/api.py):
  - `GET /mubil/api/v1/advisor/health`
  - `GET /mubil/api/v1/advisor/vehicles?q=&propulsion=`
  - `GET /mubil/api/v1/advisor/cp/{cp}`
  - `POST /mubil/api/v1/advisor/quote`
- Vista HTMX `POST /mubil/advisor/quote/` que renderiza partial.
- Template form en [src/templates/mubil/advisor.html](src/templates/mubil/advisor.html) — light/dark adaptive, Leaflet + ECharts vía CDN.
- Partial resultado en [src/templates/mubil/_advisor_result.html](src/templates/mubil/_advisor_result.html) — 4 stat cards + chart ECharts apilado + mapa Leaflet con cargadores ordenados por distancia.
- Seed `manage.py seed_advisor_demo` → 6 vehículos (3 ICE/HEV + 3 BEV) + 6 cargadores Donostia.
- 14 tests pasando en `apps.mubil.tests.test_advisor_tco` (precisión cálculo, edge cases, espacial GIST).

### Verificado funcionalmente

```
GET  /mubil/                    → 200 (landing con 4 cards)
GET  /mubil/advisor/            → 200 (form)
POST /mubil/advisor/quote/      → 200, ~12KB partial HTML
GET  /mubil/api/v1/advisor/quote (JSON) → 200 con quote completa
```

Smoke test reproducible: ver §3 abajo.

---

## 2. Issues conocidos a fecha de cierre

### Bloqueantes ninguno

### Cosméticos / pendientes

1. **Tailwind `bg-white/5` y opacity-slash classes intermitentes.**
   En la sesión `npm run build:css` no compilaba `bg-white/5`, `border-white/10`, etc. (count=0 en `app.css`) a pesar de que pintxos los usa.
   Workaround aplicado: el template usa clases sólidas con variantes `light/dark` (`bg-white dark:bg-slate-800`).
   Tarea pendiente: investigar por qué la JIT scanning falla — puede ser cache / orden de scripts o flag config.

2. **Leaflet escapaba al viewport.**
   Causa raíz: el div `#advisor-map` con `class="h-80"` no tenía altura cuando se inicializa el mapa (el class no había compilado).
   Fix aplicado: estilo inline `style="width:100%; height:320px; position:relative; z-index:0; ..."` + tres llamadas a `invalidateSize()` en `rAF`, `+250ms` y `+600ms`.
   Verificar al volver: que con CSS actualizada se siga viendo bien (la pérdida del z-index 0 podría dejar el mapa por encima del navbar si quitamos el estilo inline).

3. **Tiles OSM no cargaban (mapa blanco).**
   Causa probable: `tile.openstreetmap.org` rechazando tráfico de localhost por política de uso (Referer / User-Agent / patrón).
   Fix aplicado: cambiar el `tileLayer` a **CARTO basemaps** (`basemaps.cartocdn.com`) con variantes `light_all` / `dark_all` según `<html class="dark">`. Sin API key. Fallback automático a OSM directo si `tileerror` (defensivo).
   Verificar al volver: el mapa muestra calles de Donostia con tiles ya renderizados, no fondo blanco.

4. **`window.mubilAdvisorRender is not a function` tras HTMX swap.**
   Causa: el `<script>` del partial se inserta por HTMX, pero Alpine `x-init` se ejecuta antes de que el navegador parsee/evalúe el script inline. Resultado: race condition.
   Fix aplicado: mover la función `mubilAdvisorRender` al template padre (`advisor.html`) dentro del `{% block extra_js %}`, no al partial. La función está siempre definida en window antes de que el partial llegue.

5. **`runserver --noreload`.**
   El override fuerza no-reload. Tras cualquier cambio en `urls.py` / `settings.py` / views / models hay que `docker compose restart web`.

6. **Tests interactivos** — solución aplicada: añadir `RunSQL("CREATE EXTENSION IF NOT EXISTS vector")` al inicio de `mubil/0001_initial.py`. Funciona, pero **NO se hizo lo mismo para `postgis` ni `pgrouting`** porque la test DB que crea Django ya lleva PostGIS vía el backend GIS. Si en el futuro algún test toca `pgrouting`, fallará igual.

7. **Naming `Mubil Maps`** es placeholder. Revisar OEPM antes del envío (§17 PROPUESTA).

8. **Payback 14 años > horizonte 10 años** en el demo Golf TDI vs Niro EV. Para el pitch puede ser problema. Mitigaciones discutidas:
   - Añadir input `subvencion_eur` (MOVES III + Plan Renove EH).
   - O cambiar baseline a un coche más caro (Audi A4 ~45k€).

---

## 3. Comandos de "arrancar limpio" mañana

```bash
# Si los contenedores se pararon:
docker compose up -d

# Pickup de cualquier cambio que hagas en código:
docker compose restart web

# CSS si tocas templates:
npm run build:css

# Tests:
docker exec maps_web python manage.py test apps.mubil --noinput

# Re-seed (idempotente, update_or_create):
docker exec maps_web python manage.py seed_advisor_demo

# Smoke test rápido (con CSRF, en bash):
CJAR=$(mktemp)
HTML=$(curl -s -c "$CJAR" http://localhost:9000/mubil/advisor/)
TOKEN=$(echo "$HTML" | grep -oE 'name="csrfmiddlewaretoken" value="[^"]+"' | head -1 | sed 's/.*value="\([^"]*\)".*/\1/')
curl -s -b "$CJAR" -X POST http://localhost:9000/mubil/advisor/quote/ \
  -H "Referer: http://localhost:9000/mubil/advisor/" \
  -d "csrfmiddlewaretoken=$TOKEN&cp=20018&km_year=15000&vehicle_current_id=1&vehicle_target_id=5&years_horizon=10" \
  -o /tmp/p.html -w "%{http_code} %{size_download}\n"
```

URLs útiles:

- Landing: <http://localhost:9000/mubil/>
- Advisor: <http://localhost:9000/mubil/advisor/>
- Admin: <http://localhost:9000/admin/mubil/>
- OpenAPI docs: <http://localhost:9000/mubil/api/docs>

---

## 4. Próximos pasos por orden de prioridad

### Bloque A — `advisor` polish (1-2 días)

- [ ] Verificar visualmente en navegador el render del mapa Leaflet tras el fix (screenshot esperado: mapa de 320px alto dentro del card, markers correctos, controles dentro de su esquina).
- [ ] Hacer click en el mapa y validar popups.
- [ ] Recalcular en distintos CPs (20018, 20300 Irun, 48001 Bilbao — este último no tiene chargers en seed, mostrar mensaje "sin resultados").
- [ ] Añadir input `subvencion_eur` para mejorar el payback (PROPUESTA §6 issue conocido).
- [ ] Añadir ~30 vehículos más al seed (DGT top matriculaciones 2025) → un poco más de profundidad demo.

### Bloque B — Wiring de datos reales (cuando lleguen tokens)

- [ ] Solicitar token ESIOS → email a `consultasios@ree.es` (PROPUESTA §18).
- [ ] Solicitar API key DGT NAP + Gemini.
- [ ] Crear API key OpenChargeMap (instantáneo).
- [ ] Implementar `tasks.py` Celery: `ingest_pvpc_hourly`, `ingest_fuel_stations`, `ingest_charging_stations`.
- [ ] Sustituir `price_defaults` por queries a `EnergyPricePVPC` / `FuelStation` cuando haya datos reales.

### Bloque C — `ask` MUST (7-9d, segundo módulo del scope)

- [ ] Endpoint `POST /mubil/api/v1/ask/query`.
- [ ] Pipeline RAG: embed Gemini `text-embedding-004` (768d) → pgvector cosine top-k → compose prompt → Gemini Flash.
- [ ] Ingesta CKAN `datos.gob.es/apidata/catalog/dataset?theme=transport`.
- [ ] 5 prompts gold pre-calentados como red de seguridad para la demo.
- [ ] UI consola HTMX con spinner "thinking…" para latencias ≥3s.

### Bloque D — MOCKs (4-6d cada uno, scope cut decidido en §17)

- [ ] `route` MOCK: 5 rutas O-D precomputadas Donostia↔Bilbao/Vitoria/etc., Leaflet polyline + paradas carga visuales.
- [ ] `plan` MOCK: heatmap H3 Gipuzkoa con scoring heurístico precomputado por management command.

### Bloque E — Envío MUBIL (sem 7)

- [ ] Landing pública del proyecto.
- [ ] Vídeo 3 min (asignar 4-5 días de edición, no 1 — riesgo solopreneur clásico).
- [ ] Executive summary 2 pág generado desde §1 PROPUESTA.
- [ ] Memoria completa.
- [ ] Confirmar deadline BOG exacto.
- [ ] Documentación administrativa: certificado empadronamiento, AEAT/Seg.Social, declaración responsable.

---

## 5. Decisiones recientes (resumen — fuente de verdad en §17 PROPUESTA)

- Scope cut: `advisor`+`ask` MUST, `route`+`plan` MOCK.
- Una sola app `mubil` con sub-routers Ninja (no 4 apps planas).
- Diferenciador #1: agregador GTFS vasco unificado (no existe oficial).
- HVDS-compliant como mensaje técnico-regulatorio.
- Envío como persona física (emprendedor), no empresa.
- Naming display `Mubil Maps` provisional hasta OEPM check.
- Publicación HVDS-compliant vía datos.gob.es como follow-up post-premio.

---

## 6. Archivos clave a leer al volver

| Archivo | Para qué |
|---|---|
| [.claude/knowledge/mubil/PROPUESTA.md](.claude/knowledge/mubil/PROPUESTA.md) | Documento maestro de producto |
| [src/apps/mubil/README.md](src/apps/mubil/README.md) | Cómo está estructurada la app |
| [src/apps/mubil/advisor/services.py](src/apps/mubil/advisor/services.py) | Lógica TCO actual |
| [src/apps/mubil/data/price_defaults.py](src/apps/mubil/data/price_defaults.py) | Dónde sustituir constantes por ingesta real |
| [src/apps/mubil/tests/test_advisor_tco.py](src/apps/mubil/tests/test_advisor_tco.py) | Cobertura actual + cómo extender |
| [src/templates/mubil/advisor.html](src/templates/mubil/advisor.html) | Form actual |
| [src/templates/mubil/_advisor_result.html](src/templates/mubil/_advisor_result.html) | Render partial con JS para Leaflet/ECharts |
