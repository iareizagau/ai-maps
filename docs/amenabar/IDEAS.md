# Amenabar — Catálogo de ideas / MVPs

Ficha de ideas accionables para la landing [`/amenabar/`](../../src/apps/amenabar/). Cada
idea es un MVP demostrable, no un slide, y se ancla sobre lo que **ya existe en
el repo**: `Promocion` + `POI` con PostGIS, Overpass/Nominatim ya cacheados,
Gemini + pgvector/HNSW probados en `mubil`, Celery + Redis + Timescale listos.

> **Audiencia** del doc: yo mismo (planificación) + decisor técnico de Amenabar que
> abra el repo. Las ideas van ordenadas por **relación esfuerzo / impacto demo**,
> no alfabéticamente. Cada ficha dice qué stack añade, qué fuente externa toca y
> por qué merece la pena antes del coste. Las etiquetas de estado reflejan la
> landing (`home.html`): `LIVE` ya desplegado, `WIP` en curso, `IDEA` por hacer.

Deadline informal de recorrido completo: **antes de proponer reunión comercial
con Amenabar**. Objetivo: tres `LIVE` adicionales encima del actual.

---

## Resumen ejecutivo

| # | Idea                                   | Valor para Amenabar              | Esfuerzo | Stack nuevo             | Fuente externa                 | Estado |
|---|----------------------------------------|-----------------------------------|----------|--------------------------|--------------------------------|--------|
| 1 | Promociones + servicios cercanos       | Barrio en 10 s                   | —        | —                        | Overpass, Nominatim            | LIVE   |
| 2 | Isócronas reales (andando/bici/coche)  | Confianza vs. círculos simples   | S        | —                        | OpenRouteService               | IDEA   |
| 3 | Potencial fotovoltaico por promoción   | Sostenibilidad + ROI buyer       | S        | —                        | PVGIS (JRC/EU)                 | IDEA   |
| 4 | Clima & horas de sol                   | Confort / orientación            | S        | —                        | AEMET OpenData                 | IDEA   |
| 5 | Comparables de precio (2ª mano/obra)   | "¿Está bien de precio?"          | M        | Scrapers (reusa BS4)     | Idealista o Fotocasa (scrape)  | IDEA   |
| 6 | Calculadora hipoteca con Euríbor live  | Captación de lead inmediata      | S        | —                        | BdE / EMMI (Euríbor)           | IDEA   |
| 7 | Perfil sociodemográfico del barrio     | Target de comprador justificado  | M        | —                        | INE Censo 2021 (shapefiles)    | IDEA   |
| 8 | Colegios y zona de admisión            | Compra familiar                  | M        | —                        | Datos regionales / MEFP        | IDEA   |
| 9 | Overlay ruido + calidad del aire       | Transparencia habitabilidad      | S/M      | —                        | EEA + OpenAQ / MITECO          | IDEA   |
| 10| Riesgos (inundación, sísmico)          | Diligencia y seguro              | M        | —                        | CNIG + IGN + Catastro          | IDEA   |
| 11| Match-maker: "familia tipo → promoción"| Demo WOW en entrevista           | M        | —                        | — (reusa Gemini + geo)         | IDEA   |
| 12| Asistente RAG por promoción            | Chat "pregunta cualquier cosa"   | M        | Scraper detalle promoción | — (reusa Gemini + pgvector)   | IDEA   |
| 13| Rendimiento alquiler (yield investor)  | Nicho inversor                   | M        | —                        | Idealista rent + INE renta     | IDEA   |
| 14| Comparador 2 promociones side-by-side  | Herramienta útil "de verdad"     | S        | —                        | —                              | IDEA   |
| 15| Alertas por preferencia (watchlist)    | Captura email → CRM              | S        | Brevo (ya configurado)   | —                              | IDEA   |
| 16| 3D fly-through con Google Photorealist | Impacto visual landing           | M        | MapLibre/Cesium          | Google 3D Tiles API            | IDEA   |
| 17| Timeline de obra (fotos satelitales)   | Transparencia construcción       | L        | —                        | Copernicus Sentinel-2          | IDEA   |
| 18| Prensa & sentimiento del barrio        | Contexto emocional               | S        | —                        | NewsAPI + RSS (ya en mubil)    | IDEA   |
| 19| Huella CO₂ del lugar (movilidad)       | Pitch sostenibilidad             | S        | —                        | — (reusa isócronas)            | IDEA   |
| 20| Mapa calor "demanda" por búsquedas     | Interno (BI de Amenabar)         | M        | —                        | Google Trends API              | IDEA   |

Leyenda esfuerzo: **S** = 1–2 jornadas · **M** = ~1 semana · **L** = > 1 semana.

Las tres apuestas con mejor ratio para **enseñar en una reunión comercial**:
**#3 (Fotovoltaico)**, **#5 (Comparables)** y **#11 (Match-maker)**. Las tres son
visualmente contundentes, cuentan una historia distinta a la actual, y
reaprovechan stack ya probado.

---

## Fichas detalladas

### 2 · Isócronas reales (andando / bici / coche)

**Problema actual.** Los círculos de 5' y 15' son líneas rectas × factor 1.3 de
circuitry. Es honesto, pero cualquier arquitecto urbano o perfil técnico de
Amenabar lo detectará como aproximación. En una promoción con un río o una
autovía en medio, el círculo miente mucho.

**Qué hacemos.** Pedir isócronas reales a **OpenRouteService** (ORS) por cada
promoción, cachear el GeoJSON en una nueva tabla `IsochroneCache` con TTL
largo (geometría estable salvo cambios de red viaria). Dibujar polígonos reales
sobre Leaflet con `L.geoJSON`.

**Fuente externa.** [OpenRouteService](https://openrouteservice.org/) — API
gratuita 2 000 req/día con cuenta, soporta `foot-walking`, `cycling-regular`,
`driving-car`. Alternativa self-hosted: **Valhalla** en Docker, mismo compose,
pero añade ~2 GB de datos OSM por España. Para el MVP, cuenta gratuita.

**Stack nuevo.** Ninguno. Solo requests + un nuevo modelo cacheado.

**Por qué merece la pena.** El salto perceptivo entre un círculo y un polígono
irregular que respeta la trama urbana es brutal, y refuerza la credibilidad
del resto de métricas que ya mostramos.

**Riesgo.** Rate limit de ORS si enseñamos la demo con muchas promociones a la
vez. Mitigación: precalcular isócronas offline en Celery y servir desde cache.

---

### 3 · Potencial fotovoltaico por promoción  ⭐

**Problema.** Amenabar vende obra nueva. La eficiencia energética y la
autoconsumo están en todas las fichas, pero sin **números concretos por
cubierta**. Un comprador consciente no sabe si "panel solar" significa 500 € o
2 500 € de ahorro al año.

**Qué hacemos.**
1. Por cada `Promocion.location`, llamar a **PVGIS v5.3 (JRC Comisión Europea)**
   con parámetros estándar (pendiente 30°, orientación sur, pérdidas 14%). Pide
   `kWh/kWp año`, `horas sol equivalentes`, perfil mensual.
2. Guardar en `SolarPotential(promocion, kwh_kwp_year, monthly_json, azimuth,
   source_version)`.
3. Mostrar en la ficha de promoción: barra mensual, estimación de ahorro €/año
   con precio PVPC medio (ya tenemos ESIOS en `mubil`), tiempo de amortización
   para una instalación tipo 4 kWp.

**Fuente externa.** PVGIS — gratuita, sin clave, estable, EU-wide.
`https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`.

**Stack nuevo.** Ninguno. Reutiliza el patrón de `services.py` con `requests`.

**Por qué merece la pena.**
- Encaja con mi expertise previa (Zenit Solar) → puedo defender la metodología
  en una reunión sin pestañear.
- Es un dato **que Amenabar hoy no da** y que el comprador agradece.
- Visualmente, un gráfico mensual + un número gordo "ahorro año" vende solo.
- Permite abrir conversación sobre **instalación solar llave en mano como
  servicio adjunto** a la obra nueva (upsell real para Amenabar).

**Riesgo.** PVGIS da potencia teórica. Un comprador técnico puede pedir que
tenga en cuenta sombras y orientación real de la cubierta. Para la demo, lo
asumimos ideal; en producción pediríamos los planos técnicos a Amenabar.

---

### 4 · Clima y horas de sol

**Qué hacemos.** Tarjetas con climograma mensual (temperatura media / precipitación / horas de sol) por promoción, usando AEMET OpenData.

**Fuente externa.** [AEMET OpenData](https://opendata.aemet.es/) — API gratuita,
requiere clave que se emite en 2 min. Permite datos climatológicos por
estación y valores normales.

**Stack nuevo.** `AEMET_API_KEY` en `.env`, siguiendo el patrón de
`EUSKALMET_API_KEY` y `ESIOS_TOKEN` ya existentes. Si no se concede clave en
tiempo útil, fallback a **OpenWeatherMap** (ya configurado en `base.py:`
`OPENWEATHERMAP_API_KEY`).

**Por qué.** Barato, útil, visualmente agradable. Se combina bien con #3 (horas
de sol es input directo del cálculo PV).

**Riesgo bajo.**

---

### 5 · Comparables de precio (2ª mano / obra nueva)  ⭐

**Problema.** La promoción cuesta X €/m². ¿Es caro o barato? Hoy el comprador
abre otra pestaña y busca en Idealista. La landing pierde la atención.

**Qué hacemos.**
1. Scrapper mensual (Celery beat) de **Idealista** o **Fotocasa** filtrando
   obra nueva + 2ª mano en el municipio de cada promoción.
2. Guardar `Comparable(promocion, tipo, precio_eur, superficie_m2, dormitorios,
   fecha_snapshot, source_url)`.
3. Al clicar la promoción, mostrar distribución precio €/m² del barrio
   (histogram) + donde cae la promoción. Si lo tengo, serie temporal mensual
   (Timescale ya está en el stack).

**Fuente externa.** Idealista no tiene API pública gratuita abierta — hay que
scrapear con **respeto** (user-agent identificable, delays, cache agresivo) o
tirar de **Fotocasa** vía su export JSON menos protegido. Alternativa pública:
**Idealista Data** (previa petición de credenciales, uso académico).
**Riesgo legal:** Idealista persigue scraping comercial. Para la demo, va bien;
para una integración oficial, hay que negociar.

**Argumento para añadirlo.** Es la pregunta #1 de todo comprador. Sin este
dato, la landing es un folleto bonito. Con él, es una **herramienta de
decisión**.

**Stack nuevo.** Ninguno (BS4 + Celery + Timescale ya están). Posible
`playwright` headless si Idealista empieza a servir con JS; evitar hasta que
sea necesario.

---

### 6 · Calculadora de hipoteca con Euríbor en vivo

**Qué hacemos.** En cada promoción, un simulador: precio (si está en la ficha),
entrada, años, tipo (fijo/variable con Euríbor + diferencial). Resultado:
cuota mensual, coste total, cuadro de amortización.

**Fuente externa.** Euríbor publicado por el **Banco de España** (CSV estable)
o por **EMMI**. Scrape una vez al día en Celery beat.

**Stack nuevo.** Ninguno.

**Por qué.** Captura leads reales. "Introduce tu entrada y te decimos cuánto
pagas al mes" ya es una conversión implícita. Pequeña barrera, enorme utilidad.

**Riesgo.** Ninguno técnico. Hay que ser muy claro con el disclaimer legal
("simulación orientativa").

---

### 7 · Perfil sociodemográfico del barrio

**Qué hacemos.** Overlay con datos del **Censo 2021 del INE** por sección
censal: edad media, renta neta hogar (Atlas de distribución de renta ADRH),
tamaño medio hogar, % extranjeros, % con estudios superiores.

**Fuente externa.** [INE API](https://www.ine.es/dyngs/DataLab/manual.html?cid=66)
+ **Atlas de distribución de renta de los hogares**. Secciones censales como
shapefile vienen del **INE Cartografía** (gratis, licencia CC).

**Stack nuevo.** Ninguno. Carga de shapefile vía `ogr2ogr` → PostGIS (ya hay
`django.contrib.gis`). Primera ingesta grande (~36 000 secciones España),
pero una sola vez.

**Por qué.** Permite a Amenabar justificar precio, hablar al público objetivo y
responder a inversores con datos duros. En la ficha pública: tarjeta "quién
vive aquí" muy visual (donuts de edad, barra de renta vs. media nacional).

**Riesgo medio.** Volumen de datos y UX de que no parezca un dashboard de BI.
Mitigación: enseñar sólo 3–4 KPIs destacados, el resto en un modal.

---

### 8 · Colegios y zona de admisión

**Qué hacemos.** Capa de colegios públicos / concertados / privados ya la
tenemos vía Overpass (ya hay categoría `EDUCACION`). Añadir **zona de
admisión** para los que la publican (Euskadi, Madrid, Navarra lo hacen) +
nota media / idiomas / orientación.

**Fuente externa.** Portales regionales (datos abiertos **Gobierno Vasco** —
`opendata.euskadi.eus` — ya conocido; **Comunidad de Madrid** —
`datos.gob.es`). Varía por comunidad, no hay dataset único nacional.

**Stack nuevo.** Ninguno.

**Por qué.** Comprador familiar es un target claro de Amenabar (3 dormitorios,
periferia). Enseñar "si compras aquí, estos son los colegios de la zona" es
una decisión de compra.

---

### 9 · Ruido & calidad del aire

**Qué hacemos.** Capas raster sobre el mapa:
- **Ruido** (Lden, dBA): mapas estratégicos de ruido publicados por MITECO
  cada 5 años, por aglomeración > 100 k habitantes.
- **Calidad del aire**: estaciones [OpenAQ](https://docs.openaq.org/) con
  interpolación simple (IDW) o directamente puntos.

**Fuente externa.** [EEA Noise viewer](https://www.eea.europa.eu/en/datahub/datahubitem-view/)
+ [OpenAQ](https://openaq.org/) (API pública, sin clave para lectura ligera).
MITECO publica rasters pero descargarlos y servirlos requiere un tile server
(ver riesgo).

**Stack nuevo.** Si se opta por raster: **TiTiler** o **pg_tileserv/mapnik**.
Para MVP, saltar y mostrar sólo puntos OpenAQ sobre el mapa Leaflet.

**Por qué.** Es un diferenciador. Casi nadie en la competencia muestra esto
porque es "feo" de contar. Enseñarlo construye confianza.

**Riesgo.** Rasters pesados → requieren infra tiling. Por eso MVP va sólo con
OpenAQ y, si Amenabar quiere, ampliamos.

---

### 10 · Riesgos naturales (inundación, sísmico, incendio)

**Qué hacemos.** Capas de peligrosidad del **Sistema Nacional de Cartografía
de Zonas Inundables (SNCZI)** del MITECO y mapa sísmico del **IGN**. Si una
promoción cae en zona T=500, el aviso aparece en la ficha.

**Fuente externa.** WMS/WFS públicos de MITECO
(`https://wms.mapama.gob.es/sig/`) y del CNIG (`https://www.ign.es/wms/`).
Son servicios OGC, se pueden consumir directamente desde Leaflet con
`L.tileLayer.wms`, sin backend.

**Stack nuevo.** Ninguno.

**Por qué.** Debida diligencia visible → confianza. Para una promoción que **no
está** en riesgo, es un sello de calidad gratis.

**Riesgo.** Si una promoción **sí** cae en zona de riesgo, hay que decidir con
Amenabar cómo contar la historia. Por defecto: honestidad.

---

### 11 · Match-maker: "describe a tu familia → te sugiero promociones"  ⭐

**Qué hacemos.** Textarea en `/amenabar/`:
> _"Pareja con dos niños (6 y 8), teletrabajo + oficina en Donostia 2 días,
> presupuesto 300–400 k, nos gusta la montaña y queremos cerca de colegio público."_

Pipeline:
1. **Gemini Flash** extrae preferencias estructuradas (presupuesto, dormitorios,
   proximidad transporte X, categorías POI priorizadas, costa vs. interior).
2. Query SQL contra `Promocion` + `POI` (ya existe la base) con ranking:
   - distancia a transporte, colegios, zonas verdes
   - precio si lo tenemos (cuando #5 esté hecho)
   - estado disponible (`EN_VENTA` + `PROXIMA`)
3. Top 3 con un párrafo generado por Gemini explicando por qué cada una encaja.

**Fuente externa.** — Reusa Gemini (ya configurado en `mubil`).

**Stack nuevo.** Ninguno.

**Por qué.**
- **Demo WOW**: pedirle a un comercial de Amenabar que teclee su familia y ver
  la respuesta razonada en 3 s es memorable.
- Reutiliza por completo la fallback ladder de Gemini ya probada en `mubil`,
  así que el riesgo técnico es bajísimo.
- Convierte un listado estático en un **asistente de búsqueda**.

**Riesgo.** Que la respuesta de Gemini "alucine" promociones. Mitigación: tool
calling estricto (Gemini genera filtros estructurados; el SQL es nuestro;
Gemini solo redacta el "porqué" sobre resultados reales).

---

### 12 · Asistente RAG por promoción

**Qué hacemos.** Chat lateral en la ficha de la promoción: "pregunta cualquier
cosa sobre esta promoción". El RAG tira de:
- texto de la ficha scrapeada (hay que scrapear el detalle, hoy solo tengo el
  listado — [`services.py:188`](../../src/apps/amenabar/services.py#L188))
- Memoria del barrio: POIs cercanos + perfil sociodemográfico (#7)
- Noticias del barrio (#18)
- FAQ corporativa de Amenabar (pedírsela)

**Stack nuevo.** Ninguno. Reusa el patrón `mubil/ask`: pgvector HNSW 768d con
`gemini-embedding-001`, migración análoga a `0008*`.

**Por qué.** Es la evolución natural del asistente que ya domino en `mubil`.
Enseñar que la misma pieza se recicla en otro cliente es un argumento comercial
en sí mismo.

**Riesgo.** La ficha pública de Amenabar es escueta. Sin FAQ interna el RAG se
quedará corto. Dependencia operativa de Amenabar.

---

### 13 · Rendimiento de alquiler (yield investor)

**Qué hacemos.** Combinando precios de venta (#5) + precios de alquiler
(Idealista rent / INE índice de alquiler) → yield bruto y neto estimado por
promoción. Vista "Inversor" en la landing con filtros por rentabilidad mínima.

**Por qué.** Público secundario pero **de alto valor por lead**. Un comprador
inversor convierte más rápido que uno finalista.

**Riesgo.** Scraping doble (venta + alquiler) y las mismas pegas legales que
#5. Mejor hacerlo después de #5.

---

### 14 · Comparador 2 promociones side-by-side

**Qué hacemos.** URL `?compare=slug1,slug2`. Tabla con 15–20 métricas lado a
lado: metros a parada bus / supermercado / escuela / parque, kWh/kWp (#3),
precio €/m² (#5), nota ruido (#9), % vendido actual.

**Stack nuevo.** Ninguno.

**Por qué.** Herramienta real, usable. Las comparativas convierten.

---

### 15 · Alertas por preferencia (watchlist)

**Qué hacemos.** Usuario deja email + criterios (ciudad, presupuesto, nº
dormitorios). Cuando aparece una promoción nueva o cambia estado a
`EN_VENTA`, email automático vía **Brevo** (ya configurado:
`BREVO_API_KEY`).

**Stack nuevo.** Ninguno.

**Por qué.** Captura de lead medible y recurrente. Métrica directa para
Amenabar.

**Riesgo.** GDPR + alta en Brevo. Resuelto en producción pero hay que escribir
pie de legalidad.

---

### 16 · 3D fly-through con Google Photorealistic 3D Tiles

**Qué hacemos.** Vista 3D del entorno de la promoción con edificios reales
(no las extrusiones OSM del proyecto `solar`). Google publica tiles
fotorrealistas por API.

**Fuente externa.** [Google Map Tiles API — Photorealistic 3D Tiles](https://developers.google.com/maps/documentation/tile/3d-tiles).
**Precio: 1 € / 1 000 cargas** aprox. Para una demo controlada, calderilla; en
producción, decidir.

**Stack nuevo.** **MapLibre GL JS** o **CesiumJS** sustituyendo (o
coexistiendo con) Leaflet en esta vista concreta. Mantener Leaflet en 2D para
el resto.

**Por qué.** Impacto visual puro. Es la pieza que un director comercial
enseña en una convención.

**Riesgo.** Factura Google si se abre al público sin cuota. Mitigar: proxy en
Django con rate limiting por IP y clave server-side.

---

### 17 · Timeline satelital de la obra

**Qué hacemos.** Para promociones `EN_CURSO`, mostrar un slider temporal con
imágenes **Sentinel-2** (10 m/px, cadencia ~5 días, EU). "Mira cómo ha
avanzado la obra desde 2024".

**Fuente externa.** [Copernicus Open Access Hub](https://scihub.copernicus.eu/)
/ Sentinel Hub. API gratuita con cuenta.

**Stack nuevo.** Procesamiento de imágenes raster → requiere **GDAL** (ya
disponible porque `django.contrib.gis` lo necesita) + pequeña pipeline Celery
que recorta tiles alrededor de la promoción.

**Por qué.** Transparencia de obra sin depender de que Amenabar nos pase fotos.

**Riesgo.** 10 m/px es poca resolución para edificios individuales — se verá
el solar cambiar, no las plantas. Alternativa: webcam de obra o scraping de
las fotos de la ficha. Decidir según coste.

---

### 18 · Prensa & sentimiento del barrio

**Qué hacemos.** Reusar _tal cual_ el pipeline `mubil/news` (NewsAPI + RSS →
Gemini traducción + clasificación → pgvector) filtrado por nombre de barrio
/ ciudad. En cada ficha de promoción: "noticias relevantes del entorno" + un
termómetro simple (positivo / neutro / negativo).

**Stack nuevo.** Ninguno.

**Por qué.** Esfuerzo bajísimo (copiar-pegar un patrón ya depurado), impacto
alto en storytelling.

**Riesgo.** Noticias negativas pueden salir destacadas. Decidir con Amenabar
si se publica tal cual o se modera.

---

### 19 · Huella CO₂ del lugar

**Qué hacemos.** Dado el `destino_trabajo` que escriba el usuario (free text →
geocoding), calcular rutas en coche / bici / transporte público (reusa
OpenRouteService de #2) y multiplicar por factores de emisión del **MITECO**
(gCO₂/km oficial). Resultado: "si vivieras aquí e irías a Donostia en coche,
emitirías X kg/año; en bici, cero; en bus, Y."

**Stack nuevo.** Ninguno (depende de #2).

**Por qué.** Encaja con la narrativa sostenibilidad de Amenabar y permite
sumar el ángulo movilidad al puramente arquitectónico.

---

### 20 · Mapa de calor "demanda" (interno)

**Qué hacemos.** Un panel privado para equipo Amenabar: dónde busca la gente
("piso en Amara", "obra nueva Vitoria") según **Google Trends**, cruzado con
dónde Amenabar tiene (o no tiene) promociones. Un mapa de calor de **demanda
sin oferta propia** = oportunidad comercial.

**Fuente externa.** [Google Trends API](https://developers.google.com/search/apis/trends-api) (recientemente abierta).

**Stack nuevo.** Ninguno. Auth con cuenta Google de servicio.

**Por qué.** Pasa de ser demo de cara al comprador a ser **herramienta de BI
para Amenabar**. Monetizable como feature de un acuerdo plurianual.

**Riesgo.** Granularidad de Trends es provincia / comunidad. Útil, no
quirúrgico. Suficiente para la narrativa de "dónde invertir el próximo
suelo".

---

## Fuentes externas y claves necesarias (resumen)

| Fuente                         | Clave      | Coste        | Añadir a `.env`                 | Ideas que la usan |
|--------------------------------|------------|--------------|---------------------------------|-------------------|
| OpenRouteService               | Sí (free)  | 2 000 req/d  | `OPENROUTESERVICE_API_KEY`      | 2, 19             |
| PVGIS                          | No         | gratis       | —                               | 3                 |
| AEMET OpenData                 | Sí (free)  | gratis       | `AEMET_API_KEY`                 | 4                 |
| OpenAQ                         | No         | gratis       | —                               | 9                 |
| MITECO / IGN WMS               | No         | gratis       | —                               | 9, 10, 19         |
| INE (Censo + ADRH)             | No         | gratis       | —                               | 7, 13             |
| BdE / EMMI (Euríbor)           | No         | gratis       | —                               | 6                 |
| Idealista / Fotocasa           | — scrape — | gris         | —                               | 5, 13             |
| Google 3D Tiles                | Sí         | pay-as-u-go  | `GOOGLE_MAPS_API_KEY`           | 16                |
| Copernicus Sentinel-2          | Sí (free)  | gratis       | `COPERNICUS_USER`/`_PASS`       | 17                |
| Google Trends API              | Sí         | gratis¹      | `GOOGLE_TRENDS_API_KEY`         | 20                |
| NewsAPI                        | Ya hay     | 100 req/día  | `NEWS_API_KEY` ✓                | 18                |
| Gemini                         | Ya hay     | free tier    | `GEMINI_API_KEY` ✓              | 11, 12            |
| Brevo                          | Ya hay     | free tier    | `BREVO_API_KEY` ✓               | 15                |

¹ Google Trends API tiene cuota, pero para uso interno sobra.

## Añadidos de stack (y por qué)

Casi todas las ideas se resuelven **sin tocar el stack**. Las dos únicas
piezas que valdría introducir son:

1. **MapLibre GL JS / CesiumJS** (idea #16). Leaflet no renderiza 3D tiles con
   la calidad necesaria. Introducirlo sólo en la vista 3D, no sustituir
   Leaflet en el resto, para mantener bundle size razonable y seguir siendo
   mobile-first (`CLAUDE.md`).
2. **TiTiler o similar** (idea #9, extensión raster) **solo si** se decide
   servir rasters pesados de ruido/calidad del aire. Para el MVP, saltar.

Todo lo demás vive dentro del stack actual: PostGIS, pgvector/HNSW,
Timescale, Celery/Redis, Django-cotton + HTMX + Alpine, Gemini.

## Prioridad recomendada (orden de ataque)

1. **#11 Match-maker** — máximo impacto demo, cero riesgo de stack. Posible en
   ~1 semana.
2. **#3 Fotovoltaico** — diferenciador real, encaja con mi expertise. ~2 días.
3. **#5 Comparables** — resuelve la pregunta #1 del comprador. ~1 semana (más
   si Idealista pelea). Decidir legalmente antes de empezar.
4. **#2 Isócronas** — mejora la demo que ya hay sin reescribirla. ~2 días.
5. **#6 Hipoteca** — captura lead inmediata. ~1 día.
6. **#15 Watchlist** — métrica recurrente para Amenabar. ~1 día.

Con esos seis `LIVE` encima del actual, la landing de `/amenabar/` pasa de ser
"una idea" a ser **una suite demostrable** de valor por euro invertido.
