# mubil — Inteligencia movilidad sostenible EH

App Django del monorepo Maps.eus para los **MUBIL Mobility Awards 2026**.
Plataforma abierta de datos y decisiones de movilidad sostenible vasca con 5 módulos integrados sobre la misma base GIS + IA.

**Documento maestro de producto:** [.claude/knowledge/mubil/PROPUESTA.md](../../../.claude/knowledge/mubil/PROPUESTA.md)

---

## Estructura

```
src/apps/mubil/
├── apps.py                         # MubilConfig
├── models.py                       # 9 modelos compartidos por los 4 sub-módulos
├── admin.py                        # Registros GISModelAdmin
├── api.py                          # Router raíz que monta sub-routers
├── urls.py                         # NinjaAPI mubil_api + paths views
├── views.py                        # HTMX views (índice + 1 por módulo)
├── schemas.py · services.py        # cross-cutting
├── tasks.py                        # hooks Celery para n8n
├── advisor/   (MUST · demo en vivo)
├── ask/       (MUST · demo en vivo · RAG mixto datasets + noticias)
├── route/     (MOCK · datos precomputados)
├── plan/      (MOCK · score heurístico)
├── news/      (Blog público + señal contextual para advisor/ask)
├── tests/
├── management/commands/compute_demand_scores.py
└── migrations/
```

Cada sub-módulo expone `api.py` (Router Ninja) + `services.py` + `schemas.py`.
Todos los modelos viven en el `models.py` raíz (decisión §17 de PROPUESTA.md — más simple que 4 apps planas).

---

## Sub-módulos

| Slug | Scope | Endpoint base | Estado MVP | Esfuerzo |
|---|---|---|---|---|
| `advisor` | TCO eléctrico vs combustión (calculadora con datos vivos PVPC + carburantes) + alertas contextuales de noticias | `/estrata/api/v1/advisor/` | **MUST** | 9-11 d |
| `ask`     | Q&A movilidad EH con Gemini + RAG pgvector (datasets oficiales **+ noticias EV**) | `/estrata/api/v1/ask/` | **MUST** | 7-9 d |
| `route`   | Planificador EV-aware multimodal | `/estrata/api/v1/route/` | MOCK | 4-5 d |
| `plan`    | Heatmap demanda infraestructura carga (H3) | `/estrata/api/v1/plan/` | MOCK | 5-6 d |
| `news`    | Blog público EV (NewsAPI + RSS castellanos) resumido por Gemini en eu/es; clasifica `affects_user_plan` para advisor; embeddings alimentan el RAG de ask | `/estrata/api/v1/news/` | ✅ | 2 d |

Detalle por módulo (entrada/salida, datos, demo flow): PROPUESTA.md §3.

---

## Modelos

| Modelo | Rol | Fuente principal |
|---|---|---|
| `Vehicle` | Catálogo BEV / PHEV / HEV / ICE / DIESEL | DGT matriculaciones + investigacoches.es |
| `FuelStation` | Estaciones de carburante con precios | MINCOTUR `FiltroProvincia/20` (diario) |
| `ChargingStation` | Puntos de recarga EV | OpenData Euskadi + OpenChargeMap fallback |
| `EnergyPricePVPC` | Precio horario electricidad (TimescaleDB hypertable) | ESIOS indicator 1001 |
| `EVRegistration` | Serie histórica matriculaciones por municipio | DGT (notebook Laboratorio-Datos) |
| `MobilityTrip` | Orígenes-destinos agregados (TimescaleDB) | MITMA OD Big Data vía `pyspainmobility` |
| `MobilityDocument` | Corpus RAG con embeddings 768d (pgvector) | datos.gob.es CKAN + blogs + normativa |
| `DemandHex` | Score precomputado por hex H3 | Composición heurística (registrations × 0.4 + OD × 0.4 − chargers × 0.2) |
| `EVRoutePlan` | Cache de las 5 rutas precomputadas demo | Manual / management command |
| `NewsArticle` | Noticias EV traducidas a eu/es + clasificación + embedding 768d (HNSW) | NewsAPI + RSS castellanos especializados |

Detalle de campos y QuerySets: `models.py`.

---

## Endpoints API

Documentación OpenAPI auto-generada: `GET /estrata/api/v1/docs`

| Verbo | Path | Estado |
|---|---|---|
| GET | `/estrata/api/v1/health` | ✅ implementado |
| GET | `/estrata/api/v1/{advisor,ask,route,plan,news}/health` | ✅ implementado |
| POST | `/estrata/api/v1/advisor/quote` | ✅ implementado |
| GET  | `/estrata/api/v1/advisor/vehicles?q=` | ✅ implementado (trigram, tolerante a typos) |
| POST | `/estrata/api/v1/ask/query` | ✅ implementado (RAG mixto datasets + noticias) |
| GET  | `/estrata/api/v1/ask/suggested` | ✅ implementado |
| GET  | `/estrata/api/v1/news/` | ✅ implementado (filtros `relevance`, `tag`, `limit`) |
| POST | `/estrata/api/v1/news/refresh` | ✅ implementado (dispatch on-demand a Celery si caché stale) |
| POST | `/estrata/api/v1/route/ev-plan` | ⏳ F3a (mock) |
| GET  | `/estrata/api/v1/plan/heatmap` | ⏳ F3b (mock) |
| GET  | `/estrata/api/v1/plan/top-locations` | ⏳ F3b (mock) |

### Búsqueda de vehículos (`/advisor/vehicles?q=`)

Tolerante a typos vía trigram. Ranking en dos capas:

1. **Prefix boost** (`Q(make__istartswith=q) | Q(model__istartswith=q)` → +1.0).
   Privilegia el patrón real de autocomplete: el usuario escribe el **principio** del nombre (`mer` → Mercedes, no Mercury; `gol` → Golf, no GoldenLion en cuanto teclea la 4ª letra).
2. **Trigram similarity** (`Greatest(TrigramSimilarity(make, q), TrigramSimilarity(model, q))`)
   contra el índice GIN `vehicle_text_trgm` (migración `0005`). Umbral `0.08` —
   deliberadamente bajo porque queries de 2-3 chars tienen similitud baja por
   construcción aunque el usuario vaya bien encaminado. Subirlo descarta
   matches válidos en autocomplete.

Implementación: [`advisor/api.py`](advisor/api.py) `list_vehicles`.

### Pipeline `news` (on-demand, sin beat)

Fuentes: NewsAPI (`/v2/everything` con query `"coche eléctrico" OR "vehículo eléctrico" OR "movilidad eléctrica"`, `language=es`) + 4 RSS castellanos especializados (Forococheselectricos, Híbridos y Eléctricos, Movilidad Eléctrica, Motorpasión Eléctrico). Configurados en [`news/sources.py`](news/sources.py).

Cada visita a `/estrata/news/` renderiza al instante lo que haya en BD; si la noticia más reciente es de hace > `NEWS_CACHE_HOURS` (default 6), la view dispara `mubil.news.refresh` en Celery. Sin schedule en beat — coste Gemini controlado.

Por cada artículo nuevo (dedupe por `source_url`), Gemini Flash:

1. Traduce título + resumen a castellano y euskera.
2. Etiqueta con tags cerrados (`subvencion`, `precio_luz`, `modelo_nuevo`, `normativa`, `infraestructura`, `industria`, `opinion`, `otro`).
3. Asigna `relevance` (`EUSKADI` | `ESPANA` | `GLOBAL`).
4. Marca `affects_user_plan` solo si la noticia cambia el TCO (subvención, fiscalidad, PVPC, normativa).

El JSON estructurado se parsea con tolerancia a fences ```json (gemini-3.1-flash-lite los añade a veces aunque se le pida lo contrario). Reusa el fallback ladder de [`ask/services.py`](ask/services.py) para resistencia a quota.

Tras clasificar, el artículo se embebe con `gemini-embedding-001` (768d, mismo modelo y task type que `MobilityDocument`). El índice HNSW `mubil_newsarticle_emb_hnsw` (migración `0013`) sirve dos consumidores:

- **`advisor`** ([`views.advisor_quote`](views.py)): construye una query a partir del vehículo objetivo + código postal + km/año del usuario y rankea hasta 3 noticias `affects_user_plan` de los últimos 30 días por similaridad coseno. Fallback cronológico si el embed call falla.
- **`ask`** ([`ask/services.py`](ask/services.py) `answer`): retrieval mixto `retrieve_topk` (6 datasets) + `retrieve_news_topk` (2 noticias) → merge por score → top-8 final con `MIN_SCORE=0.40`. El prompt distingue `DATASET` vs `NOTICIA` y obliga a citar fecha de publicación.

---

## Setup

### 1. Dependencias del sistema

- **PostgreSQL 16+** con extensiones `postgis`, `pgvector`, `timescaledb`.
- **Redis** (Celery broker — ya provisto por la imagen `tensorchord/pgvector-timescaledb`).
- **Python 3.12** + paquetes del proyecto (`django-ninja`, `pgvector`, `psycopg`, `h3`, `requests`).

### 2. Migraciones

```bash
python manage.py makemigrations mubil
python manage.py migrate mubil
```

Tras la migración inicial añadir dos operaciones SQL manuales (no las auto-genera Django):

```sql
-- TimescaleDB hypertables
SELECT create_hypertable('mubil_energypricepvpc', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('mubil_mobilitytrip', 'date', if_not_exists => TRUE);

-- pgvector ivfflat (tras tener ≥1k filas en MobilityDocument)
CREATE INDEX mubil_mobdoc_emb_ivf
  ON mubil_mobilitydocument
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

### 3. Variables de entorno requeridas

| Var | Quién | Cómo obtenerla |
|---|---|---|
| `ESIOS_TOKEN` | Red Eléctrica | Email a `consultasios@ree.es` (5-10 d lag — solicitar día 1 de F0) |
| `DGT_NAP_TOKEN` | DGT NAP | Registro en `nap.dgt.es` |
| `OPENCHARGEMAP_API_KEY` | OpenChargeMap | Gratis, instantáneo en `openchargemap.org`. Enviar siempre header `X-API-Key` + `User-Agent: mubil/0.1 (mubil@maps.eus)` para evitar baneos. Throttle ≤30 req/min |
| `GEMINI_API_KEY` | Google AI Studio | Free tier OK para `text-embedding-004` |

---

## Fuentes de datos

Catálogo completo en PROPUESTA.md §5.4. Resumen:

- **Energía y carburantes:** ESIOS, REE apidatos, MINCOTUR.
- **Movilidad / tráfico:** DGT NAP (DATEX II), MITMA OD Big Data, `pyspainmobility`, DGT Cifras accidentes.
- **Vehículo eléctrico:** DGT matriculaciones, OpenData Euskadi puntos recarga, OpenChargeMap.
- **Euskadi:** OpenData Euskadi, GeoEuskadi (WMS/WFS), Gipuzkoa Irekia / b5m, EVE, Eustat (JSON-stat 2.0), GTFS Dbus/Lurraldebus/Bizkaibus/Euskotren/Metro/Renfe.

Todas las URLs requieren **verificación live** (los endpoints fueron mapeados desde conocimiento documentado — ver §18 PROPUESTA).

---

## Desarrollo

### Convenciones del repo (imitar pintxos)

- **services.py** contiene la lógica de negocio. Argumentos keyword-only (`*, ...`). Lanza `ValueError` o `PermissionError`. Decorar con `@transaction.atomic` cuando aplique.
- **api.py** llama a services, no implementa lógica.
- **schemas.py** define `In` y `Out` con Pydantic vía `from ninja import Schema`.
- **models.py** define QuerySet con `.nearby()`, `.search()`, etc., y `objects = MyQuerySet.as_manager()`.
- **Templates** en `src/templates/mubil/` (índice + 1 por módulo). Componentes Cotton reutilizables en `src/templates/cotton/`.

### Tests

```bash
python manage.py test apps.mubil
```

Tests stub en `tests/test_models.py`. Cobertura objetivo:

- TCO advisor: precisión ±5% vs valor real (PROPUESTA §13).
- ask RAG: latencia <3 s en 5 prompts gold.
- news pipeline: dedupe, parsing JSON con fences, fallback chronological en ranking; views renderizan con caché vacía y disparan refresh.

### n8n / Celery

Workflows planificados en `tasks.py`:

- `ingest_fuel_stations` — diario 06:00, MINCOTUR.
- `ingest_pvpc_hourly` — horario, ESIOS.
- `ingest_charging_stations` — semanal, OpenData Euskadi + OpenChargeMap fallback.
- `ingest_datos_gob_catalog` — semanal, CKAN datos.gob.es para el corpus `ask`.
- `ingest_mitma_od` — mensual, `pyspainmobility`.
- `compute_demand_scores` — mensual, también como management command.
- `mubil.news.refresh` ([`news/tasks.py`](news/tasks.py)) — **on-demand** (NO beat). Disparada desde `views.news_page` cuando la caché supera `NEWS_CACHE_HOURS`.

---

## Publicación HVDS (post-premio)

Objetivo a medio plazo: publicar nuestra capa agregada como **High-Value Dataset** del Reglamento UE 2023/138, federada a [data.europa.eu](https://data.europa.eu/en).

Camino:

1. Generar metadatos **DCAT-AP / GeoDCAT-AP** de cada dataset agregado.
2. Datos brutos en formatos exigidos por la cat. 2 de movilidad: **GTFS** (transporte público), **NeTEx** (redes), **DATEX II v3** (tráfico/señalización).
3. Licencia **CC-BY 4.0** u **ODbL**.
4. Solicitar federación a [`datos.gob.es`](https://datos.gob.es) (España es el portal intermediario obligatorio — no se publica directo en data.europa.eu).
5. Validar metadatos con **JOINUP DCAT-AP** y el **MQA dashboard** (`data.europa.eu/mqa/`).
6. Solicitar anotación HVDS para los conjuntos elegibles → visibilidad UE.

⚠️ No bloquea el envío MUBIL — diferible a F5 / post-defensa. Detalle: PROPUESTA.md §5.5, §17, §18.

---

## OpenChargeMap — notas operativas

OCM es nuestro **fallback global** para puntos de recarga (OpenData Euskadi es la fuente primaria, OCM rellena huecos crowdsourced).

- **Base URL:** `https://api.openchargemap.io/v3`
- **Auth:** API key gratis. Enviar header `X-API-Key: <KEY>` + `User-Agent: mubil/0.1 (mubil@maps.eus)`.
- **Endpoints:**
  - `GET /poi` — POIs por bbox o coordenadas (parámetros: `countrycode`, `latitude`, `longitude`, `distance`, `maxresults`, `connectiontypeid`, **`polyline`** para chargers a lo largo de una ruta — útil para `route`).
  - `GET /referencedata` — lookup IDs (operadores, conectores, países).
- **Rate limit:** no documentado pero el admin banea abuso. Throttle ≤30 req/min, cache local.
- **Licencia datos:** ODbL.
- **Sin cliente Python oficial.** Estrategia:
  - Auto-generar cliente desde su [`ocm-openapi-spec.yaml`](https://raw.githubusercontent.com/openchargemap/ocm-docs/refs/heads/master/Model/schema/ocm-openapi-spec.yaml) con `openapi-python-client`.
  - O usar `requests` directo con un wrapper fino en `apps/mubil/advisor/services.py`.
- **Ingesta inicial masiva:** usar [`ocm-export`](https://github.com/openchargemap/ocm-export) (snapshots periódicos por archivo) en lugar de paginar API — evita risk de baneo.

---

## Roadmap

| Fase | Semana | Entregable |
|---|---|---|
| F0 — Setup | 1 | Tokens + ingesta MINCOTUR/ESIOS inicial |
| F1 — `advisor` MUST | 2-3 | TCO con datos reales + tests ±5% |
| F2 — `ask` MUST | 4-5 | RAG con 1.000-1.500 docs + 5 prompts gold |
| F3a — `route` MOCK | 6 | 5 rutas precomputadas |
| F3b — `plan` MOCK | 6-7 | Heatmap H3 + scoring heurístico |
| F3c — Landing + vídeo + memoria | 7 | Envío MUBIL |
| F4 — `news` | post-F2 | Fase 1 blog público + Gemini eu/es · Fase 2 alertas contextuales en advisor · Fase 3 RAG mixto datasets + noticias en ask |

Detalle, riesgos y estimaciones honestas: PROPUESTA.md §6, §7, §14.

---

## Decisiones clave

- **Una sola app `mubil`** con sub-routers Ninja, no 5 apps planas.
- **2 módulos MUST** (`advisor`, `ask`) con demo en vivo · **2 módulos MOCK** (`route`, `plan`) — las bases MUBIL admiten *"MVP **o** mock-up"*.
- **`news` como capa transversal**, no como módulo aislado: alimenta señal contextual al `advisor` (Fase 2) y RAG mixto al `ask` (Fase 3). Diferencial vs un agregador genérico.
- **Ingesta on-demand** (no beat) para `news`: la página dispara refresh si la caché tiene > `NEWS_CACHE_HOURS`. Coste Gemini controlado y honesto con el flujo real de uso del jurado.
- **HVDS-compliant** como diferenciador (Reglamento UE 2023/138).
- **Solopreneur 33-40 días** = 1 sem over budget vs 45 naturales del BOG. Sin holgura.
- **Sin dependencia de `apps.bidaiak`** (es sólo un stub de URL, no app real — verificado 2026-05-26).
- **Sin FK a `core.Municipio`** (no existe — usamos `municipality_naia` string).

Log completo: PROPUESTA.md §17.

---

## Referencias

- Bases oficiales: `.claude/knowledge/mubil/mubil.pdf`
- Excel origen advisor: `.claude/knowledge/mubil/Electricoogasolina.xlsx`
- Convocatoria: <https://mobilityawards.mubil.eus/en/>
- App ejemplo (patrón a imitar): [`src/apps/pintxos/`](../pintxos/)
