# MUBIL Mobility Awards 2026 — Propuesta

> **Documento vivo.** Estructurado para iterar con agentes (Plan, Explore, code-reviewer, etc.).
> Cada sección incluye `state:` (draft / refining / locked) y `agent-notes:` cuando aplique.

---

## 0. Metadatos

| Campo | Valor |
|---|---|
| **Edición** | MUBIL Mobility Awards 2026 |
| **Convocatoria BOG** | 5 mayo 2026 |
| **Deadline aplicación** | 45 días naturales desde BOG → **~19 junio 2026** *(verificar fecha exacta del BOG)* |
| **URL** | https://mobilityawards.mubil.eus/en/ |
| **Categoría MUBIL** | Movilidad eléctrica + Movilidad conectada + Infraestructuras relacionadas |
| **Fase** | Prototipo (MVP funcional sobre Maps.eus) |
| **Tipo de participante** | **Persona física (emprendedor)** — requiere certificado de empadronamiento |
| **Idioma del envío** | EU / ES (preparar pitch en EN también) |
| **Máx. propuestas** | 5 por participante — *podemos enviar 1 principal + 1 “lite”* |

**state:** locked
**agent-notes:** Verificar fecha BOG exacta (el PDF dice "publicado 5 mayo 2026"). Confirmar plazo con `mubil@mubil.eus`.

---

## 1. Identidad del proyecto

**Nombre:** **TBD — se decidirá tras refinar producto (§3)**

> Posicionamiento provisional: *“La capa de inteligencia abierta de la movilidad sostenible vasca.”*

**Alternativas a evaluar:**

| Nombre | Pro | Contra |
|---|---|---|
| EFFIMOVE EH | Marca preexistente, dominio disponible | Anglicismo |
| BidaiBI | Euskera + “BI” | Menos memorable fuera EH |
| MugiTu | Verbo euskera “muévete” | Riesgo conflicto trademark |
| GeoBidai | Refuerza vínculo Maps.eus | Menos brand-able |

**state:** draft (pospuesto explícitamente)
**agent-notes:** Decisión congelada hasta que §3 esté `locked`. Búsqueda OEPM/EUIPO obligatoria antes de fijar.

---

## 2. Problema

La movilidad sostenible en Euskadi sufre **fragmentación de datos y decisiones subóptimas**:

1. **Ciudadano / empresa**: no tiene cómo decidir *racionalmente* si comprar coche eléctrico vs combustión. Las calculadoras existentes son estáticas, no incluyen precios reales de electricidad/combustible, ni la red de carga local, ni patrones reales de uso.
2. **Municipios / Diputaciones**: planifican infraestructura de carga “a ojo”. No hay herramientas abiertas que crucen demanda potencial × red eléctrica × tráfico × patrones turísticos.
3. **Operadores de carga / movilidad compartida**: optimizan rutas y ubicaciones con datos cerrados de cada silo. No hay capa común de open data semánticamente consultable.
4. **Turista / visitante**: planificación multimodal en EH es manual y desconectada (Renfe, Euskotren, Lurraldebus, Donostibus, BiziDF, carga EV, P&R…).

**Dolor cuantificado — slots citables (rellenar con número exacto):**

- *(TBD)* % matriculaciones BEV/PHEV Gipuzkoa 2025 vs media ES — **fuente:** DGT Matriculaciones (notebook Laboratorio-Datos) + EVE
- *(TBD)* nº cargadores públicos por 1000 hab en Gipuzkoa vs Bizkaia/Araba — **fuente:** MITECO + datos.gob.es (gap HVDS cat. 5)
- *(TBD)* % viajes intermodales o multimodales Gipuzkoa — **fuente:** MITMA OD Big Data (`pyspainmobility` por distrito/GAU)
- *(TBD)* fallecidos/heridos en accidentes Gipuzkoa 2024 — **fuente:** DGT Cifras microdatos
- *(TBD)* spread precios PVPC máx-mín diario y % renovable mix — **fuente:** ESIOS + apidatos.ree.es

**state:** refining
**agent-notes:** *Tarea Explore (cuando haya red disponible)*: rellenar TBD desde las fuentes ya mapeadas en §5.4. Mínimo 5 cifras citables antes de F4 (envío).

---

## 3. Solución

Plataforma SaaS + open data con **4 módulos integrados** sobre la misma base GIS+IA. Tras refinamiento técnico (agente Plan, 2026-05-26), **2 módulos son MUST con demo en vivo** y **2 son MOCK-UP con datos precomputados** — perfectamente coherente con las bases MUBIL ("MVP **o** mock-up que resuelve el problema").

### 3.1. `advisor` — Asesor TCO Eléctrico vs Combustión  · **MUST** (demo en vivo)

| | |
|---|---|
| **Input UI** | CP (5 dígitos), km/año, vehículo actual (autocomplete), vehículo objetivo, horizonte años, carga nocturna sí/no |
| **Output** | Coste total horizonte, payback años, kg CO₂ evitados/año, breakdown energía/mantenimiento/seguro, mapa cargadores 5 km del centroide CP |
| **Datos en vivo** | ESIOS indicator 1001 (PVPC), MINCOTUR `FiltroProvincia/20`, OpenData Euskadi puntos recarga + OpenChargeMap fallback |
| **Diferencial** | **Única calculadora vasco-específica con PVPC + carburantes locales + red de carga real.** Lo que un alcalde puede teclear y obtener un número creíble. |
| **Esfuerzo** | 9-11 días |

### 3.2. `ask` — Q&A sobre movilidad EH (Gemini + RAG pgvector)  · **MUST** (demo en vivo)

| | |
|---|---|
| **Input UI** | Textarea + 5 prompts curados, filtro opcional municipio |
| **Output** | Markdown con respuesta + lista de fuentes citables (URL + score) + tabla si procede |
| **Corpus** | 1.000-1.500 docs: metadatos `datos.gob.es` (CKAN) + DGT matriculaciones agregadas + ESIOS resúmenes + MITMA OD top-50 + MITECO recarga. Embeddings Gemini `text-embedding-004` |
| **Diferencial** | **Primer asistente IA sobre datos de movilidad EH con citas trazables.** Wow factor alto, riesgo bajo (si Gemini tarda, HTMX muestra "thinking…") |
| **Esfuerzo** | 7-9 días |

### 3.3. `route` — Planificador multimodal EV-aware  · **MOCK-UP** (5 rutas precomputadas)

| | |
|---|---|
| **Input UI** | Origen/destino (autocomplete) + vehículo BEV + SOC inicial % |
| **Output** | Polyline + segmentos `[drive, charge_stop, drive, transit_leg]` + tiempo + kWh + coste estimado |
| **Realidad** | 5 pares O-D precomputados (Donostia↔Bilbao/Vitoria/Pamplona/Tolosa/Eibar). Fallback Dijkstra simple para el resto. Sin SOC dinámico, sin GTFS-RT |
| **Diferencial honesto** | Mock visual convincente para el pitch. La construcción real (pgRouting+SOC+GTFS multimodal) = >2 sem, inviable solo |
| **Esfuerzo MOCK** | 4-5 días · *(real: 12-15 días, fuera de scope)* |

### 3.4. `plan` — Heatmap demanda infraestructura carga  · **MOCK-UP** (score heurístico, no ML)

| | |
|---|---|
| **Input UI** | Dropdown municipio Gipuzkoa (89) + horizonte 1/3/5 años |
| **Output** | Heatmap H3 hex-grid sobre Leaflet + tabla top-10 hex + leyenda |
| **Realidad** | Score heurístico `matriculacionesEV × 0.4 + densidad_OD × 0.4 − cargadores_actuales × 0.2`. Recalculado en `compute_demand_scores` management command, no en vivo |
| **Diferencial honesto** | Visualmente convincente para el pitch + extensible a ML real post-premio. Las bases admiten "mock-up que resuelva el problema identificado" |
| **Esfuerzo MOCK** | 5-6 días · *(real con embeddings + Prophet: 15+ días)* |

**state:** locked
**agent-notes:** Cualquier cambio de scope reabre §6 y §7. Plan completo del agente: ver task `a93d1b29b7e778eac` o decisión §17.

---

## 4. Propuesta de valor y diferenciación

| Para… | Valor entregado | Diferencial vs alternativas |
|---|---|---|
| **Ciudadano** | Decisión informada compra EV con números creíbles | Única calculadora con PVPC vivo + carburantes locales + red carga real |
| **Municipio** | Planificación basada en datos | Open data + heatmap por hex H3 + dashboard ECharts |
| **Operador (carga/sharing)** | Optimización ubicaciones/rutas | API Django-Ninja + capa GIS común |
| **MUBIL/EVE/GV** | Capa de inteligencia compartida | Open source, HVDS-compliant, vasco |
| **Investigador** | Dataset semánticamente consultable con citas trazables | RAG Gemini sobre catálogo CKAN |

**Foso defendible** (priorizado tras investigación open data 2026-05-26):

1. **Agregador GTFS+RT vasco unificado — no existe oficial.** Mugi/Barik unifica billetaje, no datos. Hueco real, no marketing.
2. **Cubrimos gaps HVDS UE 2023/138 cat. 2/4/5 en Euskadi** (cat. 4 tiempo real foral <30% cubierta). Argumento técnico-regulatorio fuerte.
3. **Base GIS+IA ya construida** (Maps.eus, PostGIS + pgvector + pgRouting operativos) → time-to-demo brutalmente corto.
4. **Stack moderno y solopreneur-friendly** → coste marginal cercano a cero.
5. **Open source / open data + vasco-específico** → barrera contra incumbentes cerrados.

**state:** locked

---

## 5. Arquitectura técnica

### 5.1. Stack

| Capa | Tecnología | Rol | Justificación |
|---|---|---|---|
| Backend | **Django 6** | Dominio + ORM | Productividad solopreneur |
| API | **Django Ninja** | REST tipada (Pydantic) | API pública para reutilizadores |
| GIS | **PostGIS** (4326/3857) | Geometrías, índices GIST | Fuente de verdad espacial |
| Routing | **pgRouting** | Grafos sobre OSM | Multimodal EV-aware |
| Semántica | **pgvector** | Embeddings + RAG | Búsqueda Q&A sobre open data |
| Series temporales | **TimescaleDB** | Hypertables ESIOS/REE/carburantes | Precios horarios, retención eficiente |
| Frontend | Django-Cotton + Tailwind + HTMX + Alpine | UI Atomic, sin SPA | Coherente con Maps.eus |
| Viz | ECharts | Dashboards interactivos | Open source, compatible HTMX |
| IA | Gemini API | Q&A, extracción estructurada | Calidad/coste competitivo |
| Automatización | n8n | Ingesta open data programada | Visual, sin código glue |
| Despliegue | *(TBD: VPS + Docker / Fly.io / GCP)* | — | — |

### 5.2. Mapa al monorepo Maps.eus
```
src/
├── core/           # ya existe — modelos y utilidades GIS
├── www/            # landing global → punto de entrada a effimove
├── bidaiak/        # rutas → backbone de effimove-route
└── mubil/          # ← NUEVA APP (pendiente de scaffold; se itera el MD primero)
    ├── advisor/   # TCO calculator
    ├── route/     # EV-aware multimodal (delega en bidaiak)
    ├── plan/      # demanda de carga
    └── ask/       # RAG Gemini
```

### 5.3. Modelo de datos clave (esbozo)

- `ChargingStation(Point, operator, power_kw, connectors[])` — GIST index
- `Vehicle(make, model, year, battery_kwh, range_km, consumption_kwh_100km)`
- `FuelStation(geom POINT 4326, prices JSONB, updated_at)` — GIST index, snapshot diario MINCOTUR
- `EnergyPrice(indicator_id, geo_id, datetime, value)` — TimescaleDB hypertable (ESIOS/REE)
- `EVRegistration(municipio FK, fecha, propulsion, marca, modelo)` — serie histórica DGT
- `MobilityTrip(origin_district, dest_district, hour, mode, motive, n_trips)` — MITMA hypertable
- `MobilityDocument(content, embedding vector(768))` — pgvector RAG sobre datasets/blogs/normativa
- `RouteSegment` (de bidaiak) — pgRouting topology + penalización por incidencias DATEX II

**state:** refining
**agent-notes:** *Tarea agente postgis-model*: redactar models.py con índices y QuerySets nearby/within.

---

### 5.4. Catálogo de datos abiertos (fuentes confirmadas)

> Investigación 2026-05-26 sobre fuentes propuestas. **Todas las URLs/endpoints requieren verificación live** (los agentes operaron sin acceso a red — ver §18).

#### Energía y carburantes

| Fuente | Endpoint | Auth | Formato | Frecuencia | Granularidad | Módulo | Notas |
|---|---|---|---|---|---|---|---|
| **ESIOS** (REE) | `api.esios.ree.es/indicators/{id}` | Token (email a `consultasios@ree.es`) | JSON | Horaria / 15-min | Nacional + sistemas + `geo_ids[]=8932` (País Vasco) | `advisor`, `plan` | PVPC = indicator `1001`. CC BY 4.0. ~50 req/min razonable |
| **REE apidatos** | `apidatos.ree.es/es/datos/{cat}/{widget}` | No | JSON-API | 10-min / horaria | CCAA (`geo_ids=17` País Vasco) | `advisor`, `ask` | Mix generación → factor CO₂/kWh dinámico. Cache 5-10 min |
| **Carburantes MINCOTUR** | `sedeaplicaciones.minetur.gob.es/.../FiltroProvincia/20` | No | JSON | Diaria | **Coordenadas exactas por estación** (~280 en Gipuzkoa) | `advisor`, `route`, `plan` | Snapshot rolling, sin histórico → ingestar a PostGIS + Timescale localmente. Atención: comas decimales en strings |

#### Movilidad y tráfico

| Fuente | Endpoint | Auth | Formato | Frecuencia | Granularidad | Módulo | Notas |
|---|---|---|---|---|---|---|---|
| **DGT NAP** | `nap.dgt.es/dataset` + `infocar.dgt.es/datex2/dgt/` | Token (registro gratis) | DATEX II XML, GeoJSON, GTFS-RT | Tiempo real (2-5 min) | Estatal — **sólo red estatal en Gipuzkoa** (AP-1/8, A-1/15, N-I/121-A) | `route`, `advisor` | Datasets clave: incidencias, obras, VMS, cámaras, aforos, meteo vial, radares, ZBE, puntos recarga |
| **MITMA OD Big Data** | `movilidad-opendata.mitma.es/` | No | Parquet (v2) | Diaria (lag ~2 meses) | Distrito MITMA (5-15k hab) / municipio / GAU | `plan`, `ask` | O-D agregada (k≥15) por hora, modo, motivo. EH Sur cubierta (no Iparralde) |
| **pySpainMobility** | `pip install pyspainmobility` | No (wrapper MITMA) | pandas DF | Diaria | Distrito / municipio / GAU | `plan`, `ask` | EUPL-1.2. Soporta v1 (2020-21) + v2 (2022→). Acceso O-D inmediato |
| **DGT en Cifras** | `dgt.es/.../dgt-en-cifras/` + microdatos en `datos.gob.es` | No | CSV / XLSX | Anual (definitivo) + mensual (avance) | Provincia + municipio | `advisor`, `plan` | Accidentes con 50+ campos. Útil para riesgo-tramo y puntos negros |
| **datos.gob.es CKAN** | `datos.gob.es/apidata/catalog/dataset/...` | No | JSON-LD | Continua | Heterogénea | `ask` | Indexar metadatos en pgvector → descubrimiento semántico de datasets |

#### Vehículo eléctrico + catálogo

| Fuente | Endpoint | Auth | Formato | Frecuencia | Granularidad | Módulo | Notas |
|---|---|---|---|---|---|---|---|
| **DGT Matriculaciones** (vía notebook Laboratorio-Datos) | `github.com/Admindatosgobes/Laboratorio-de-Datos` | No | `.ipynb` + CSV | Mensual | Provincial + municipal | `advisor`, `plan` | Series BEV/PHEV/HEV/ICE. Reutilizable para benchmark Gipuzkoa vs ES |
| **investigacoches.es** | HTML (sin API) | No (verificar robots.txt + ToS) | Scraping → JSON | Continua (nuevos modelos) | Por modelo/versión | `advisor`, `ask` | Ficha técnica WLTP, batería kWh, autonomía, precio. **Atribuir explícitamente** |
| **MITECO puntos recarga** | Datasets en `datos.gob.es` + NAP DGT | No | CSV / GeoJSON | Variable | Coordenadas | `route`, `plan` | Calidad heterogénea — gap HVDS a cubrir |

#### Datos Euskadi (investigación 2026-05-26)

| Fuente | Endpoint | Auth | Formato | Datasets clave | Granularidad | Módulo | Notas |
|---|---|---|---|---|---|---|---|
| **OpenData Euskadi** | `opendata.euskadi.eus/catalogo/` + `api.euskadi.eus/datasets/v1.0/` | No (algunos sí) | JSON/CSV/GeoJSON/RDF | Parque vehículos por municipio, matriculaciones por combustible, **puntos recarga CAV**, Encuesta Movilidad, accidentalidad | Municipio / TTHH / CAV | `advisor`, `plan` | CC-BY 4.0. Metadatos desiguales |
| **GeoEuskadi** | `geoservicios.euskadi.eus` WMS/WFS | No | WMS/WFS/WMTS, INSPIRE | Red carreteras CAV, callejero, ortofotos, bidegorris, transporte (estático) | Vectorial | `route` (snap red foral GI-*) | CC-BY 4.0 |
| **Gipuzkoa Irekia / b5m DFG** | `gipuzkoairekia.eus` + `b5m.gipuzkoa.eus` | No | CSV/JSON/GeoJSON, WMS/WFS | Aforos GI-* (dumps periódicos), red foral, parking disuasorios, padrón vehículos | Municipio/vía | `route`, `advisor` | API tiempo real foral **no verificada** |
| **EVE** | `eve.eus` | No (informes PDF/XLS) | PDF/XLS, algún CSV | Balance energético CAV, parque EV, mapa recarga | CAV | `advisor` (contexto) | **No publica PVPC propio**, redirige a ESIOS |
| **Eustat** | `opendata.eustat.eus/api/v1.0/` | No | **JSON-stat 2.0**, CSV, PC-Axis | Parque vehículos municipio, encuesta movilidad cotidiana, accidentes | Municipio/comarca | `advisor`, `plan` | CC-BY 4.0. API moderna |
| **Dbus GTFS** | `dbus.eus` + `transit.land` | No | GTFS + API propia `dbus.eus/api/` (RT parcial) | Donostia autobuses | Donostialdea | `route` | CC-BY |
| **Lurraldebus GTFS** | Publicado por DFG (gipuzkoairekia) | No | GTFS | Interurbano Gipuzkoa | GI | `route` | GTFS-RT no público verificado |
| **Bizkaibus GTFS** | `bizkaia.eus` open data | No | GTFS | Interurbano Bizkaia | BI | `route` | Histórico irregular |
| **Euskotren GTFS** | `euskotren.eus` | No | GTFS | Rail + tranvía | CAV | `route` | RT no verificado público |
| **Metro Bilbao GTFS** | `metrobilbao.eus` / opendata Bizkaia | No | GTFS | Metro | BI | `route` | RT abierto no verificado |
| **Renfe Cercanías** | `data.renfe.com` + NAP | Registro | GTFS + RT | C-1/C-2/C-3 EH | EH | `route` | API NAP con RT |
| **dBizi / Bilbobizi / Gasteiz Aurrera** | Web operadores | No (verificar) | GBFS posible (no verificado) | Bike sharing | Urbano | `route` | A confirmar en F0 |
| **Ayto. Donostia / Bilbao / Vitoria-Gasteiz** | Portales open data municipales | No | CSV/JSON/GTFS | Aforos urbanos, OTA, parking, ciclismo | Municipal | `route`, `advisor` | CC-BY 4.0 |
| **OpenChargeMap API v3** (fallback global) | `api.openchargemap.io/v3/poi` y `/v3/referencedata` | API key (gratis, instantáneo) header `X-API-Key` o param `key=` | JSON | Crowdsourcing — actualización continua | Coordenadas (lat/lon) | `advisor`, `route` | Params clave: `countrycode`, `latitude`, `longitude`, `distance` (km), `maxresults`, `connectiontypeid`, **`polyline` (chargers a lo largo de una ruta — útil para `route`)**. Rate-limit no documentado pero admin puede banear abuso; obligatorio user-agent custom + throttle |
| **OpenChargeMap OpenAPI spec** | `raw.githubusercontent.com/openchargemap/ocm-docs/master/Model/schema/ocm-openapi-spec.yaml` | No | YAML OpenAPI 3.1 | — | — | tooling | Auto-generar cliente Python con `openapi-python-client` (no existe oficial) |
| **OpenChargeMap ocm-export** | `github.com/openchargemap/ocm-export` (JS, MIT, activo) | — | Snapshots periódicos POI por archivo | — | — | bulk sync | Alternativa al API para ingesta inicial masiva sin tocar rate-limit |

**Hallazgos críticos:**

1. **No existe agregador GTFS vasco oficial.** Mugi/Barik unifica billetaje, no datos → **diferenciador real** para EFFIMOVE EH.
2. **API tiempo real foral GI-*** (aforos/incidencias) **no verificada como pública.** Posible gap diferencial — verificar con DFG.
3. **EVE no publica PVPC** → confirmado: ESIOS es la fuente única.
4. **Recarga EV**: OpenData Euskadi + OpenChargeMap como fallback redundante.

**state:** refining
**agent-notes:** *F0 verificación live*: probar APIs Eustat (JSON-stat), confirmar GBFS bike sharing, validar que aforos GI-* tienen alguna ruta de acceso programática.

---

#### Marco UE — federación y publicación

> Verificado 2026-05-26 con `WebFetch`. Estas fuentes son meta-portales, no productores de datos brutos — pero **definen el mecanismo por el que EFFIMOVE EH se publica como HVDS-compliant** y se hace descubrible en toda la UE.

| Fuente | Endpoint | Auth | Formato | Aporte para nosotros |
|---|---|---|---|---|
| **data.europa.eu** (portal) | `data.europa.eu/api/hub/search/` (REST) + `/data/sparql` (SPARQL) + CKAN | No para lectura | DCAT-AP RDF/XML, JSON-LD, Turtle | Descubrimiento de 1.729.121 datasets federados de 36 países. Búsqueda HVDS: `/data/datasets?is_hvd=true` |
| **data.europa.eu Provider Manual** | `dataeuropa.gitlab.io/data-provider-manual/` | — | Guía operativa | Cómo publicar y federar. Para España: **vía datos.gob.es como portal intermediario**, no publicación directa |
| **Geospatial Trends 2022 (Op-EU)** | DOI `10.2830/041345` — descarga manual PDF | — | PDF | Argumentos institucionales citables en la memoria del premio. *No conseguido extraer contenido vía WebFetch — descargar manualmente en F0* |

**Implicación estratégica:**

- **No nos registramos directamente como provider de data.europa.eu** (sólo lo hacen administraciones públicas oficiales). El camino es: publicar nuestros datasets agregados con metadatos **DCAT-AP / GeoDCAT-AP** + licencia abierta (CC-BY 4.0 u ODbL) → solicitar federación a `datos.gob.es` → data.europa.eu cosecha automáticamente desde ahí.
- Formatos exigidos para movilidad HVDS cat. 2: **GTFS, NeTEx, DATEX II** (alineados con nuestra estrategia §5.5).
- Validadores recomendados: **JOINUP DCAT-AP**, **INSPIRE validator**, **MQA dashboard** (`data.europa.eu/mqa/`).
- ⚠️ data.europa.eu **NO soporta euskera** en metadatos. Multiidioma vía eTranslation. Mantener `eu` como idioma fuente y `es/en` como traducción.

---

### 5.5. Cumplimiento marco UE — HVDS (diferenciador para jurado)

El **Reglamento UE 2023/138 de Conjuntos de Alto Valor (HVDS)** obliga a España a publicar 5 categorías de datos de movilidad en formatos abiertos estándar (GTFS, NeTEx, DATEX II, SIRI, INSPIRE GML).

| Cat. HVDS | España (general) | **Euskadi (medido)** | Oportunidad EFFIMOVE EH |
|---|---|---|---|
| 1. Redes transporte (INSPIRE) | ✅ CNIG/IGN | **~70%** vía GeoEuskadi + DGT NAP | Reusar; enriquecer atributos red foral |
| 2. Horarios TP (GTFS/NeTEx) | ⚠️ Parcial | **No existe agregador oficial vasco** — operadores publican por separado | **Agregador GTFS+RT vasco unificado** — diferenciador único |
| 3. Tráfico RT (DATEX II) | ✅ NAP DGT | NAP solo red estatal | Consumir, no duplicar |
| 4. Señalización y limitaciones | ⚠️ Parcial | **<30%** — aforos forales GI-* no RT, incidencias forales sin API | **Cerrar gap RT foral** (alto valor B2G) |
| 5. Puntos recarga / combustibles alt. | ⚠️ Heterogéneo | **~40%** — recarga sí (OpenData Euskadi), parking RT solo Donostia/Bilbao parcial | **Unificar** OpenData Euskadi + EVE + OpenChargeMap |

**Posicionamiento:** EFFIMOVE EH se anuncia como *"plataforma vasca HVDS-compliant"*. Tres gaps medidos (cat. 2, 4, 5) — los tres reales, no marketing. Mensaje fuerte para jurado MUBIL y para EVE/DFG como cliente B2G.

#### Formatos y validadores HVDS obligatorios

| Capa | Formato exigido | Validador |
|---|---|---|
| Metadatos generales | **DCAT-AP** (RDF/XML, JSON-LD, Turtle) | JOINUP DCAT-AP validator |
| Metadatos geoespaciales | **GeoDCAT-AP** (extensión DCAT-AP con campos espaciales) | JOINUP + MQA dashboard |
| Cat. 2 — horarios TP | **GTFS** + **NeTEx** | gtfs-validator (Google) + NeTEx validator (CEN) |
| Cat. 3/4 — tráfico RT y señalización | **DATEX II v3** | DATEX II validator |
| Capa INSPIRE (red vial) | **GML / INSPIRE schemas** | INSPIRE validator |
| Calidad agregada | — | data.europa.eu MQA dashboard (`/mqa/`) |

**Camino de publicación para EFFIMOVE EH:**

1. Generamos metadatos DCAT-AP/GeoDCAT-AP de nuestra capa agregada.
2. Publicamos los datasets con licencia CC-BY 4.0 u ODbL.
3. Solicitamos a `datos.gob.es` que nos federe (España es el portal intermediario obligatorio).
4. data.europa.eu cosecha automáticamente desde datos.gob.es.
5. Solicitamos anotación HVDS para los conjuntos elegibles → visibilidad de "alto valor" en toda la UE.

**state:** refining

---

### 5.6. Referencias estratégicas (precedentes y posicionamiento)

| # | Proyecto | Qué hace | Relevancia para nosotros |
|---|---|---|---|
| 1 | **alijaalejandro/ejercicio-datos-ia-copiloto** | LLM consumiendo datos.gob.es vía API | Validación institucional del patrón `ask` (Gemini + RAG sobre open data) |
| 2 | **montera34 eskola-bideapp** | Caminos escolares con datos abiertos (Errenteria/Bilbao) | **Complementario, no competidor.** Aliado preferente. Scope micro-territorial vs nuestro regional. Citarlos en memoria refuerza arraigo vasco |
| 3 | **Google/Moovit/Citymapper** | Consumen GTFS/NeTEx/DATEX II públicos | Marco — justifica apostar por estándares europeos. Argumento ante jurado |
| 4 | **Open Data Charter** | 6 principios (Open by Default, Timely…) | Argumento ético/gobernanza alineado con MUBIL/GV |
| 5 | **Laboratorio de Datos (datos.gob.es)** | Notebooks oficiales de análisis BEV/PHEV/HEV | Material directo para `advisor` + `plan`; reutilizar con atribución |
| 6 | **DGT Programa Marco vehículos automatizados (18-jun-2025)** | Régimen autorizaciones pruebas vía abierta | Capa futura `effimove-auto` (registro público pruebas Euskadi) |

**state:** locked

---

## 6. MVP / Prototipo — alcance del envío

> Las bases MUBIL exigen *"MVP **o** mock-up que resuelva el problema identificado"* — explícitamente admiten mock-up. Aprovechamos esto.

### MUST (demo en vivo, datos reales)

- [ ] **`advisor` completo**: jurado teclea CP 20018 (Donostia), Golf 1.6 TDI vs Kia Niro EV, 15k km/año → ve coste 10 años + payback + CO₂ + mapa cargadores. Precisión TCO ±5% vs valor real.
- [ ] **`ask` completo**: jurado pregunta libre, recibe respuesta con ≥3 fuentes citadas en <3s (5 prompts gold pre-calentados como red de seguridad).

### MOCK-UP (datos precomputados / hardcoded, UI pulida)

- [ ] **`route`**: 5 pares O-D precomputados (Donostia↔Bilbao/Vitoria/Pamplona/Tolosa/Eibar) con polyline + parada de carga visualmente convincente. Fallback Dijkstra simple para queries fuera del set.
- [ ] **`plan`**: heatmap H3 sobre Gipuzkoa con score heurístico precomputado por management command. Sin modelo ML, sin Prophet.

### Soportes de envío

- [ ] **Landing pública** explicando los 4 módulos + acceso a `advisor` y `ask` sin login.
- [ ] **Vídeo 3 min** (asignar **4 días** de edición, no 1 — riesgo solopreneur subestimado).
- [ ] **Executive summary 2 pág** generado desde §1.
- [ ] **Memoria completa** con secciones §2-§13.

**Criterio de aceptación duro**: cualquier miembro del jurado debe poder probar `advisor` y `ask` en vivo desde el navegador sin briefing previo. `route` y `plan` se enseñan, no se prueban.

**state:** locked
**agent-notes:** Scope cut decidido tras agente Plan (§17). Si en F2 (sem 5) advisor o ask están retrasados → cortar `plan` a 3 días, mantener `route` mock.

---

## 7. Roadmap a la defensa

| Fase | Días netos | Semana | Entregables |
|---|---|---|---|
| **F0 — Setup** | 5d | 1 | Scaffold app `mubil` (sub-routers Ninja), modelos base, ingesta MINCOTUR+ESIOS, **token ESIOS solicitado día 1** |
| **F1 — `advisor` MUST** | 9-11d | 2-3 | Calculadora TCO con PVPC + carburantes + cargadores reales, tests ±5% |
| **F2 — `ask` MUST** | 7-9d | 4-5 | RAG Gemini con 1.000-1.500 docs, citas trazables, 5 prompts gold |
| **F3a — `route` MOCK** | 4-5d | 6 | 5 rutas precomputadas + UI Leaflet pulida |
| **F3b — `plan` MOCK** | 5-6d | 6-7 | Heatmap H3 con score heurístico precomputado |
| **F3c — Landing + vídeo + memoria** | 3-4d *(realista: 4-5d)* | 7 | Landing pública, vídeo 3 min, executive summary 2 pág |
| **F4 — Envío** | — | < BOG+45d (~19 jun 2026) | Aplicación online + adjuntos |
| **F5 — Defensa** | — | < BOG+6m | Pitch 3 min + Q&A jurado |

**Total estimado honesto**: **33-40 días** netos ≈ 7-8 semanas a 5 días/semana → **1 semana over budget** vs los 45 naturales hasta deadline. Slack escaso, requiere disciplina.

**state:** locked
**agent-notes:** Si en sem 5 advisor o ask van retrasados → cortar `plan` a 3d (sólo modelos + heatmap estático sin scoring). Si Gemini API key se demora → fallback embeddings locales BGE-M3. Confirmar fecha exacta BOG.

---

## 8. Modelo de negocio

**Vías de monetización (escalonadas):**

1. **B2G — Licencias a ayuntamientos y diputaciones** (`plan` + dashboard custom).
2. **B2B — API premium para operadores** (carga, sharing, leasing, concesionarios).
3. **B2C — Premium en `advisor`** (alertas, simulaciones flota, comparador detallado).
4. **Servicios** — consultoría de movilidad data-driven a gobiernos locales.
5. **Open core** — los módulos base permanecen open source / open data.

**Sostenibilidad**: con el premio (12.500€ metálico + hasta 12.500€ colaboración + oficina) y 2-3 contratos B2G piloto, llegamos a break-even en 12 meses.

**state:** draft
**agent-notes:** *Tarea agente Plan*: validar pricing con benchmarks (Geotab, Wallbox Analytics, Vaisala Roadview).

---

## 9. Mercado

- **Inicial (TAM mínimo demostrable):** Gipuzkoa — 89 municipios, 720k hab.
- **Expansión 12m:** Euskadi (2,2M hab) + Navarra (660k hab).
- **Expansión 36m:** España + regiones UE con estructura similar (NUTS-3 con red EV emergente).

**Why now:**
- Plan Estatal Despliegue EV (PERTE VEC III) 2026-2030.
- Obligación municipal de planes de movilidad sostenible (LCCTE).
- Datos abiertos vascos en máximo histórico (OpenData Euskadi 2025).

**state:** refining
**agent-notes:** *Tarea agente WebSearch*: sizing del mercado de software de planificación de carga EV en UE.

---

## 10. Equipo

- **Imanol Gasteasoro** — *Emprendedor / fundador único*. Stack: Django, PostGIS, IA aplicada.
- **(opcional) Mentor de negocio** — Bic Gipuzkoa Berrilan SA (incluido en el premio si ganamos).
- **(opcional) Colaboradores académicos** — UPV-EHU / CIDETEC / Tecnalia vía cartas LoI para el bloque colaboración.

**Forma jurídica del envío:** **Persona física** *(decisión 2026-05-26, ver §17)*.

**state:** refining
**agent-notes:** Solopreneur asumido. Si en F2 el alcance se demuestra inviable a solas, evaluar incorporar 1 colaborador técnico antes de la defensa (no del envío).

---

## 11. Impacto y escalabilidad

**Impacto cuantitativo (ambiciones a 36 meses):**
- 50.000 ciudadanos EH usan `advisor` antes de comprar coche.
- 20 ayuntamientos vascos planifican carga con `plan`.
- 1 millón de toneladas CO₂ eq. evitadas por decisiones modal-shift inducidas. *(modelo a validar)*
- 100% open data municipal de movilidad vasca indexada en `ask`.

**Escalabilidad técnica:**
- Multitenancy por NUTS-3 nativo.
- Misma codebase, distintas configuraciones regionales.
- pgvector + Gemini → cero coste marginal por consulta nueva.

**state:** refining

---

## 12. Colaboraciones (clave para premio +12.500€)

> El premio incluye hasta **12.500€ extra** para colaboración con agentes vascos. Necesitamos al menos 1 carta de intención antes de defensa.

Candidatos:
- **EVE** (Ente Vasco de la Energía) — datos de carga + validación modelo `plan`.
- **CIDETEC** — investigación EV/baterías.
- **Tecnalia / IK4** — modelado de demanda.
- **UPV-EHU (Donostia / Bilbao)** — TFM/TFG colaborativos.
- **GeoEuskadi (Gobierno Vasco)** — open data spatial.
- **Lurraldebus / Euskotren** — GTFS y datos de demanda.
- **MUBIL Center** — espacio + ecosistema (ya parte del premio).

**state:** draft
**agent-notes:** *Tarea*: priorizar y redactar emails de approach. Mínimo 2 cartas firmadas antes de la defensa.

---

## 13. KPIs / Métricas

### Producto
- Tiempo a primera respuesta `ask` < 3s.
- Precisión TCO `advisor` ±5% vs realidad medida.
- Cobertura cargadores: 100% de Gipuzkoa en pgvector.

### Negocio
- MoUs firmados antes de defensa: ≥2.
- Usuarios beta `advisor`: ≥500 antes de defensa.
- Posts/menciones medios EH: ≥5.

### Premio (criterios jurado)
- Market placing ✅
- Innovation ✅ (IA + open data + GIS)
- Impact & potential ✅
- Presentation ✅
- Compliance ✅

**state:** draft

---

## 14. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Datos abiertos incompletos | Alta | Medio | Web scraping + n8n + fallback manual |
| **Red foral Gipuzkoa (GI-*) fuera de DGT NAP** | Alta | **Alto** | OpenData Euskadi + Gipuzkoa Irekia + acuerdo con DFG (§12) |
| **GTFS interurbanos vascos fragmentados** | Alta | Medio | Agregación propia HVDS-compliant (§5.5) — convertimos en feature |
| **Token ESIOS tarda 5-10d en llegar** | Alta | **Alto** | **Solicitar día 1 de F0**. Fallback a `apidatos.ree.es` sin token (peor granularidad) |
| **Latencia Gemini >3s en `ask`** | Media | Medio | Usar `gemini-flash`, 5 prompts gold pre-calentados, spinner HTMX ≥500ms |
| **MINCOTUR JSON con comas decimales** | Alta | Bajo | Bug clásico; 0.5d dedicado al parser en F0 |
| **pgRouting+SOC+GTFS multimodal real** = inviable solo | Alta | Alto | **`route` queda como MOCK** (decisión §17) |
| **Vídeo 3 min** subestimado | Alta | Medio | Asignar 4-5d, no 1d (riesgo solopreneur clásico) |
| Coste Gemini API | Media | Medio | Cache + embeddings locales (BGE-M3 si necesario) |
| Trademark naming | Media | Alto | Búsqueda OEPM tras §3 `locked` |
| Competidor incumbente (Geotab, Wallbox) | Media | Alto | Foco hyper-local + open source + HVDS-compliant |
| Solopreneur burnout | Alta | Alto | Scope cut decidido (§17); cortar `plan` a 3d si retraso |
| MUBIL favorece equipos vs solos | Media | Medio | Sumar 1 cofounder o carta UPV-EHU |
| URLs/endpoints cambiaron desde el mapeo §5.4 | Media | Bajo | Verificación live obligatoria en F0 (§18) |
| **OCM sin cliente Python oficial** | Media | Bajo | Auto-generar desde su `ocm-openapi-spec.yaml` con `openapi-python-client`, o `requests` directo |
| **OCM ban por abuso de API** (rate-limit no documentado) | Media | Medio | User-agent custom + throttle (≤30 req/min) + cache local. Para ingesta inicial usar `ocm-export` (snapshots por archivo) |
| **datos.gob.es harvesting demora semanas** | Media | Bajo (post-premio) | Publicación HVDS no es bloqueante para el envío MUBIL. Diferir a F5 / post-defensa |
| **Sin euskera en metadatos data.europa.eu** | Baja | Bajo | Mantener `eu` como source + traducción `es/en` vía eTranslation |

**state:** refining
**agent-notes:** *Crítica honesta:* el riesgo “competidor incumbente” NO está bien mitigado solo con “open source”. Hace falta diferencial defendible más fuerte. Revisar.

---

## 15. Pitch outline (3 min — defensa final)

> El premio fuerza pitch de 3 minutos con mentoring previo.

```text
[0:00–0:20] Hook        — “Hoy un alcalde vasco decide dónde poner un cargador EV con un Excel.”
[0:20–0:40] Problema    — fragmentación de datos + gap HVDS UE (cat. 4 <30% en Euskadi).
[0:40–1:20] Demo advisor (40s) — jurado teclea CP 20018 + Golf vs Niro → coste, payback, CO₂, cargadores.
[1:20–2:00] Demo ask (40s)     — pregunta libre sobre Tolosaldea + matriculaciones EV → respuesta con citas <3s.
[2:00–2:30] Route+plan mock (30s+30s) — polyline Donostia↔Bilbao + heatmap Hernani.
[2:30–2:50] Diferencial — agregador GTFS vasco unificado + HVDS-compliant.
[2:50–3:00] Cierre      — “Decisiones de movilidad basadas en datos, no en intuición.”
```

**state:** draft
**agent-notes:** Iterar el script con un agente “pitch-coach” cuando esté maduro el producto.

---

## 16. Documentación requerida (compliance MUBIL)

Checklist según PDF de bases:

- [ ] Formulario estándar (online)
- [ ] Executive summary (máx. 2 páginas) — *generar desde este MD*
- [ ] Memoria o business plan
- [ ] Vídeo presentación ≤3 min (opcional pero recomendado)
- [ ] Personas físicas: certificado empadronamiento
- [ ] Personas jurídicas: escritura constitución
- [ ] Declaración responsable cumplimiento bases
- [ ] Certificación al corriente Hacienda + Seg.Social
- [ ] Declaración no incursos Art.12 NF 3/2007 Gipuzkoa

**state:** draft

---

## 17. Decisiones (log)

| Fecha | Decisión | Motivo | Reversible? |
|---|---|---|---|
| 2026-05-26 | Crear app `mubil` en monorepo Maps.eus | Reaprovecha PostGIS, pgRouting, pgvector ya operativos | Sí |
| 2026-05-26 | Apostar por cuatro módulos integrados (advisor/route/plan/ask) | Maximiza scoring jurado (market+innov+impact) | Sí |
| 2026-05-26 | **Iterar MD antes de scaffoldear código** | Refinar concepto/alcance evita boilerplate prematuro | Sí |
| 2026-05-26 | **Envío como persona física (emprendedor)** | Simpler, sin necesidad de constituir sociedad ad hoc | Difícil tras envío |
| 2026-05-26 | **Posponer naming** hasta §3 `locked` | Producto define marca, no al revés | Sí (mientras no se envíe) |
| 2026-05-26 | **Posicionar plataforma como HVDS-compliant** | Argumento técnico/regulatorio fuerte ante jurado; gap real en cat. 2/4/5 en Euskadi | Sí |
| 2026-05-26 | **Acercamiento a montera34 como aliado, no competidor** | Scope complementario (micro-territorial vs regional); refuerza arraigo vasco en la memoria | Sí |
| 2026-05-26 | **Stack: explicitar TimescaleDB + django-ninja** | Hypertables ESIOS/MITMA + API tipada para reutilizadores externos | Sí |
| 2026-05-26 | **Scope cut: `advisor` + `ask` MUST · `route` + `plan` MOCK-UP** | Inviable construir los 4 reales en 6-7 sem a solas; bases MUBIL admiten "MVP **o** mock-up" | Sí (mientras no se envíe) |
| 2026-05-26 | **Una sola app `src/apps/mubil/` con sub-routers Ninja** | Más simple que 4 apps planas; coherente con patrón pintxos/inguru | Sí |
| 2026-05-26 | **Nuevo diferenciador #1: agregador GTFS vasco unificado** | Confirmado: Mugi/Barik unifica billetaje, no datos. Hueco real | Sí |
| 2026-05-26 | **OpenChargeMap como fallback** de OpenData Euskadi para puntos de recarga | Redundancia de datos = menos riesgo en demo | Sí |
| 2026-05-26 | **Solicitar token ESIOS día 1 de F0** | Espera 5-10d → bloqueante si se posterga | Sí |
| 2026-05-26 | **Scaffold app `mubil` creado** en `src/apps/mubil/` con 9 modelos, 4 sub-routers Ninja, admin, tests stub, management command `compute_demand_scores`, plantillas base. Wireado en `INSTALLED_APPS` y `config/urls.py` (path `/mubil/`) | F0 desbloqueado | Sí |
| 2026-05-26 | **Discrepancia detectada**: `apps.bidaiak` es **sólo un stub** (un único `urls.py` con placeholder), no app real. **No existe pgRouting topology** que reutilizar. `core.Municipio` tampoco existe. | El plan asumía existencias falsas — `mubil` se autocontiene: usa `municipality_naia` string en lugar de FK Municipio; el módulo `route` no depende de `bidaiak` | Sí |
| 2026-05-26 | **Publicar capa agregada como HVDS-compliant** vía DCAT-AP/GeoDCAT-AP → datos.gob.es → data.europa.eu | Materializa el diferenciador §5.5; visibilidad UE; argumento institucional para EVE/GV | Sí (no bloquea envío, diferible a F5) |
| 2026-05-26 | **Cliente OCM auto-generado** desde su `ocm-openapi-spec.yaml` con `openapi-python-client` | No hay cliente oficial; auto-gen evita escribir wrapper manual y mantenido sincronizado con su schema | Sí |
| 2026-05-26 | **`ocm-export` para ingesta inicial OCM** + API on-demand para refresh | Evita banear nuestra IP por descarga masiva; snapshots por archivo desde GitHub | Sí |
| 2026-05-26 | **`advisor` MUST backend completo + UI HTMX/Leaflet/ECharts** ejecutándose en `/mubil/advisor/`. Quote Golf TDI vs Niro EV produce 20.388€/11.109€/9.279€ ahorro/1.508 kg CO₂ evitados. 14 tests pasando. | Hito principal de F0 cerrado | Sí |
| 2026-05-26 | **AppRegistry entry creado** (slug `mubil`, name `Mubil Maps`, icon `route`, color `#06b6d4`, featured). Naming display PROVISIONAL | Mubil aparece en el Home Hero. Revisar OEPM antes del envío | Sí |

---

## 18. Tareas abiertas (para iterar con agentes)

### Iteración del MD (próximas)

- [ ] **Refinar §2 Problema**: cifras citables (EVE, OpenData Euskadi, Eustat, IDAE).
- [ ] **Refinar §3 Solución**: para cada módulo, entrada/salida concreta y mock-up textual.
- [ ] **Refinar §4 Diferenciación**: foso real más allá de “open source vasco”.
- [ ] **Refinar §6 MVP**: scope honesto — ¿son 4 módulos demo-ables en 6-7 semanas a solas?
- [ ] **Refinar §8 Modelo de negocio**: benchmarks de pricing reales.

### Bloqueadas hasta refinar

- [ ] Decisión naming (depende de §3 `locked`).
- [ ] Scaffold de `src/apps/mubil/` (depende de §3 y §6 `locked`).
- [ ] `models.py` de mubil (depende de scaffold).
- [ ] Lista priorizada de colaboradores + drafts de email (depende de §12).

### Verificación administrativa

- [ ] Confirmar fecha exacta deadline BOG → email `mubil@mubil.eus`.
- [ ] Listar docs persona física: certificado empadronamiento, AEAT/Seg.Social al corriente, declaración responsable.

### Día 1 de F0 (críticas, bloqueantes)

- [ ] **Solicitar token ESIOS** → email a `consultasios@ree.es` (5-10d lag).
- [ ] **Solicitar token DGT NAP** → registro en `nap.dgt.es`.
- [ ] **Crear API key OpenChargeMap** (gratis, instantáneo) en `openchargemap.org`.
- [ ] **Solicitar Gemini API key + cuota** (verificar tier free para `text-embedding-004`).
- [ ] **Confirmar fecha deadline BOG** + email a `mubil@mubil.eus`.
- [ ] **Descargar `ocm-openapi-spec.yaml`** desde `github.com/openchargemap/ocm-docs` y auto-generar cliente Python.
- [ ] **Descargar manualmente PDF Geospatial Trends 2022** (DOI 10.2830/041345) — WebFetch falló, descarga directa desde data.europa.eu.

### HVDS publication (post-premio, no bloqueante)

- [ ] Leer Data Provider Manual completo (`dataeuropa.gitlab.io/data-provider-manual/`).
- [ ] Generar DCAT-AP/GeoDCAT-AP de los datasets agregados.
- [ ] Contactar `datos.gob.es` para solicitar federación.
- [ ] Validar metadatos con JOINUP + MQA dashboard.
- [ ] Solicitar anotación HVDS para los conjuntos elegibles.

### Verificación técnica del catálogo §5.4 (cuando haya red)

- [ ] Probar endpoints ESIOS con token (verificar header `application/vnd.esios-api-v1+json`).
- [ ] Probar `apidatos.ree.es` para `geo_ids=17` (País Vasco) en 3 widgets.
- [ ] Descargar JSON MINCOTUR carburantes `FiltroProvincia/20` y validar 280 estaciones esperadas.
- [ ] Solicitar token DGT NAP y probar 1 DATEX II endpoint.
- [ ] `pip install pyspainmobility` y descargar OD de 1 semana para Donostialdea.
- [ ] Investigar **OpenData Euskadi**, **GeoEuskadi**, **Gipuzkoa Irekia**, **GTFS Lurraldebus/Dbus/Euskotren** con la misma ficha de §5.4.
- [ ] Verificar robots.txt + ToS de `investigacoches.es` antes de planificar scraping.

### Crítica honesta a la propuesta (tarea code-reviewer / second-opinion)
- [ ] ¿Está la diferenciación realmente defendida o es marketing? Revisar sección 4.
- [ ] ¿Los 4 módulos son demo-ables en 6-7 semanas o estamos prometiendo demasiado?
- [ ] ¿El modelo de negocio B2G es realista o requiere ciclos comerciales de 18+ meses?

**state:** locked (la lista crece, no se cierra)

---

## 19. Referencias

### Internas

- `mubil.pdf` — Bases oficiales MMA 2026 (este directorio)
- `Electricoogasolina.xlsx` — Calculadora origen del módulo `advisor`
- [TECHNICAL_RUNBOOK.md](../../TECHNICAL_RUNBOOK.md)
- [PROJECT_STATE.md](../../PROJECT_STATE.md)
- [DECISIONS.md](../../DECISIONS.md)

### Convocatoria

- <https://mobilityawards.mubil.eus/en/>

### Fuentes — energía y carburantes

- ESIOS API — <https://www.esios.es/>
- REE apidatos — <https://www.ree.es/>
- Precios carburantes (catálogo) — <https://datos.gob.es/es/catalogo/e05068001-precio-de-carburantes-en-las-gasolineras-espanolas>

### Fuentes — movilidad y tráfico

- DGT NAP — <https://nap.dgt.es/> · datasets <https://nap.dgt.es/dataset>
- MITMA Big Data — <https://www.transportes.gob.es/ministerio/proyectos-singulares/estudios-de-movilidad-con-big-data/opendata-movilidad>
- MITMA metodología — <https://www.transportes.gob.es/ministerio/proyectos-singulares/estudios-de-movilidad-con-big-data/metodologia-del-estudio-de-movilidad-con-bigdata>
- pySpainMobility — <https://github.com/pySpainMobility/pySpainMobility>
- DGT cifras accidentes — <https://www.dgt.es/menusecundario/dgt-en-cifras/dgt-en-cifras-resultados/?tema=accidentes-de-trafico&pag=1&order=DESC>
- DGT blog datos.gob.es — <https://datos.gob.es/es/blog/los-conjuntos-de-datos-de-la-dgt-para-ayudar-mejorar-el-trafico-y-la-seguridad-vial>
- Transportes — <https://www.transportes.gob.es/>

### Vehículo eléctrico

- Notebook “Ruta a la electrificación” — <https://github.com/Admindatosgobes/Laboratorio-de-Datos/tree/main/Data%20Science/Ruta%20a%20la%20electrificaci%C3%B3n%20de%20la%20Movilidad>
- Artículo datos.gob.es — <https://datos.gob.es/es/conocimiento/ruta-la-electrificacion-descifrando-el-crecimiento-del-vehiculo-electrico-en-espana>
- investigacoches.es — <http://www.investigacoches.es/>

### Vehículo autónomo

- DGT nota prensa programa marco — <https://www.dgt.es/comunicacion/notas-de-prensa/20250618-dgt-nuevo-programa-marco-pruebas-vehiculos-automatizados>
- datos.gob.es blog VA — <https://datos.gob.es/es/blog/el-papel-de-los-datos-en-el-impulso-de-los-vehiculos-autonomos>

### Marco regulatorio y referencias estratégicas

- Reglamento UE HVDS Movilidad — <https://datos.gob.es/es/blog/cumpliendo-con-europa-el-reglamento-de-conjuntos-de-alto-valor-de-movilidad>
- Open Data Charter — <https://opendatacharter.org/>
- Proyectos open data + IA — <https://datos.gob.es/es/blog/proyectos-que-reutilizan-datos-abiertos-e-ia-para-solucionar-desafios-medioambientales>
- Google/Moovit/Citymapper — <https://datos.gob.es/es/blog/como-reutilizan-google-moovit-y-citymapper-los-datos-abiertos-de-movilidad>
- Datos para navegar ciudades — <https://datos.gob.es/es/blog/datos-abiertos-para-navegar-ciudades>
- Sector transporte (catálogo) — <https://datos.gob.es/es/sectores/transporte> · blog <https://datos.gob.es/es/blog/etiquetas_blog/transporte-20087>

### UE — federación y publicación HVDS

- data.europa.eu (portal) — <https://data.europa.eu/en>
- Data Provider Manual — <https://dataeuropa.gitlab.io/data-provider-manual/>
- Solicitar harvesting — <https://dataeuropa.gitlab.io/data-provider-manual/how-to-publish/request-harvesting/>
- Búsqueda HVDS — <https://data.europa.eu/data/datasets?is_hvd=true>
- Geospatial Trends 2022 (PDF, descarga manual) — <https://data.europa.eu/en/doc/geospatial-trends-2022-opportunities-dataeuropaeu-emerging-trends-geospatial-community>
- MQA (Metadata Quality Assessment) — <https://data.europa.eu/mqa/>

### OpenChargeMap

- API docs — <https://openchargemap.org/develop/api> *(403 al fetch, abrir en navegador)*
- OpenAPI spec — <https://raw.githubusercontent.com/openchargemap/ocm-docs/refs/heads/master/Model/schema/ocm-openapi-spec.yaml>
- Org GitHub — <https://github.com/openchargemap>
- ocm-system (backend C#) — <https://github.com/openchargemap/ocm-system>
- ocm-app (TS web/móvil) — <https://github.com/openchargemap/ocm-app>
- ocm-export (snapshots POI) — <https://github.com/openchargemap/ocm-export>

### Precedentes / patrones replicables

- alijaalejandro — LLM + open data — <https://github.com/alijaalejandro/ejercicio-datos-ia-copiloto/>
- montera34 eskola-bideapp — <https://montera34.com/project/eskola-bideapp/>

### Euskadi (pendiente investigar)

- OpenData Euskadi — <https://opendata.euskadi.eus>
- EVE — <https://www.eve.eus>
- *(añadir)* GeoEuskadi, Gipuzkoa Irekia, GTFS Dbus/Lurraldebus/Euskotren/Bizkaibus/Metro Bilbao

---

## 20. Cómo iterar este documento

1. **Cambio de estado**: actualiza el `state:` de la sección antes de iterar.
2. **Agentes**: cita el agente sugerido en `agent-notes:` y mueve los hallazgos al cuerpo.
3. **Decisiones**: cada decisión irreversible va al log §17 con fecha.
4. **Crítica**: las objeciones honestas viven en §14 y §18 — no las suavizar.
5. **Snapshot pre-envío**: cuando `state` de §1–§17 estén `locked`, exportar a PDF de 2 págs (sección 1) + memoria completa.
