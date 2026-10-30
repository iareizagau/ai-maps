## Why

Tras cerrar la tanda de enriquecimientos (solar + clima + aire), tenemos tres variables objetivas por promoción que ningún competidor publica. Pero están pasivas: hay que abrir una por una y leer. Un comprador consciente llega con una frase: _"pareja con dos niños, teletrabajo + 2 días en oficina en Donostia, 300–400 k, cerca de colegio público, costa"_ — queremos convertir esa frase en **tres recomendaciones objetivas en 3 s**, con un párrafo explicando por qué cada una encaja. Es la demo WOW y, además, justifica a posteriori haber invertido en las tres capacidades de la tanda anterior porque las convierte en argumentos accionables.

## What Changes

- Nueva página `/amenabar/match/` (vista GET con form) + endpoint POST HTMX que devuelve el partial de resultados. **Sin modelo nuevo**: las preferencias son efímeras (no persistimos query ni analytics, al menos de inicio).
- Nuevo módulo `services_match.py` con tres funciones puras:
  1. `extract_preferences(user_text) -> MatchPreferences` — Gemini Flash con la fallback ladder del proyecto (reutilizamos la mecánica probada en `mubil.ask.services`). Prompt estricto que devuelve JSON con **schema cerrado y validado**: `budget_eur_min/max`, `bedrooms_min`, `cities`, `must_near` (códigos de `POI.Categoria`), `nice_to_have`, `climate_preference ∈ {coastal, mild, warm, cold, any}`, `prefers_sunny` (bool), `prefers_clean_air` (bool), `destination_city` opcional, `summary` (una línea en lenguaje natural). Valores fuera de rango se corrigen a defaults; schema inválido → fallback keyword simple + log.
  2. `rank_promociones(prefs) -> list[ScoredPromocion]` — **puro Django ORM / PostGIS, sin LLM**. Filtra `Promocion.estado__in=['EN_VENTA','PROXIMA']` + ciudad opcional. Score ponderado:
     - **Distancia a POIs prioritarios** (`ST_Distance` sobre `POI` filtrado por `must_near`).
     - **Potencial solar** (`SolarPotential.kwh_kwp_year`) si `prefers_sunny`.
     - **Confort climático** (banda `temp_mean` de `PromocionClima`) si `climate_preference != 'any'`.
     - **Aire limpio** (`AirQualityStation` más cercana vía `ST_Distance`) si `prefers_clean_air`.
     - Devuelve **top-3** con `score` total, `breakdown` por eje y los objetos relacionados cargados.
  3. `generate_explanation(prefs, scored) -> str` por promoción — párrafo breve escrito por Gemini **únicamente sobre los datos reales ya rankeados**. Anti-alucinación: Gemini recibe sólo nombre, ciudad y los números del `breakdown`; no genera listas, no inventa valores, sólo redacta el porqué. Si Gemini falla o tarda, se omite el párrafo y la card se renderiza sin él.
- Vista nueva `match_page` (GET renderiza form) + `match_results` (POST devuelve `templates/amenabar/match_results.html` como partial HTMX con 3 cards). Mobile-first base 375 px, reutilizando atoms/molecules Cotton ya existentes cuando aplique.
- Nueva entrada en el listado de ideas (`views._ideas`) con estado `LIVE` y URL a `match_page`, para que aparezca junto a "Promociones + servicios cercanos" en la home.
- Tests pytest cubriendo: schema cerrado del extractor, filtro de estado, boost por `prefers_sunny`, join espacial por aire limpio, promociones sin métricas opcionales (score degradado, no crash), endpoint HTMX devuelve 3 cards.

Fuera de alcance (futuras propuestas separadas):
- Precio €/m² como variable de ranking (depende de la idea #5 Comparables, aún no implementada).
- Persistir queries en un modelo `MatchQuery` + dashboard analítico interno.
- Captura de email para alertas (idea #15).
- Chat conversacional / streaming (hoy es request-response).

## Capabilities

### New Capabilities
- `amenabar/matchmaker`: ofrecer sobre la landing de Amenabar una búsqueda en lenguaje natural que convierte una descripción libre en tres promociones rankeadas con explicación por promoción, usando los datos ya cacheados de servicios cercanos, solar, clima y calidad del aire.

### Modified Capabilities
<!-- Ninguna. Las capacidades existentes (`solar-potential`, `climate-normals`, `air-quality`) se consumen como lecturas; sus contratos no cambian. -->

## Impact

- **Código**:
  - `src/apps/amenabar/services_match.py` (nuevo).
  - `src/apps/amenabar/views.py` (añade `match_page` + `match_results`; ya existe import de `apps.amenabar.services`, re-import limpio).
  - `src/apps/amenabar/urls.py` (dos rutas nuevas: `match/` y `match/results.json` o `match/results/` para HTMX).
  - `src/templates/amenabar/match.html` (página con form + contenedor HTMX).
  - `src/templates/amenabar/match_results.html` (partial con 3 cards).
  - `src/apps/amenabar/tests/test_match.py` + fixtures JSON si procede.
- **APIs externas**: ninguna nueva. Reutiliza `GEMINI_API_KEY` ya configurada y la fallback ladder definida en `config/settings/base.py` (`GEMINI_GENERATION_FALLBACK_MODELS`), misma clave y mecánica que usa mubil.
- **BD**: ninguna tabla nueva, ninguna migración.
- **Infra**: ninguna. No se añade servicio Docker. No se cambia la imagen de BD.
- **Riesgos**:
  - Alucinación de Gemini → mitigada por el pipeline en 3 pasos (Gemini NO decide qué promociones salen; sólo extrae preferencias y, al final, redacta la explicación sobre filas reales ya seleccionadas).
  - Latencia (2 llamadas Gemini + ranking) → extracción con Flash (p99 ~1.5 s con fallback ladder), ranking local sub-segundo, explicación opcional y renderizada bajo HTMX indicador de carga.
  - Fallo de Gemini en extracción → fallback a parseo keyword simple (regex de "€", "dormitorios", nombre de ciudad conocida, etc.) para no bloquear al usuario.
- **Despliegue**: tras merge, nada que correr más allá de desplegar los templates. Sin backfills.
- **Rollback**: revertir commit; no deja residuos en BD.
