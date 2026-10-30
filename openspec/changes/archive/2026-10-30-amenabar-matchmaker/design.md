## Context

Ver `proposal.md — Why` para la motivación. Estado técnico de partida:

- Las tres capacidades promovidas en la tanda anterior (`solar-potential`, `climate-normals`, `air-quality`) ya están pobladas: 107/107 promociones con solar, inventario AEMET + clima pendiente de clave real del usuario, OpenAQ pendiente de clave real. Los modelos y relaciones existen.
- `Promocion` ya tiene `location` 4326 (107 geocodificadas); `POI` tiene `Categoria` como `TextChoices` con 17 valores; `services.nearest_by_category(promocion)` ya calcula "más cercano por categoría + conteo en radios 5'/15'" para la ficha.
- Gemini está integrado y probado en `apps.mubil.ask.services`: `_call_gemini_generate(prompt, max_output_tokens)` encapsula la **fallback ladder** definida en `settings.GEMINI_GENERATION_FALLBACK_MODELS`. Es una función privada con `_` acoplada a `embeddings.EmbeddingError` (ver `mubil/ask/services.py:258-303`).
- Convenciones (`.claude/CLAUDE.md`): mobile-first base 375 px, `gettext_lazy`, autoreload off (restart `web_maps` tras edits Python), docker-compose nombre `web_maps`, `pyproject.toml` ya tiene `src/apps/amenabar/tests` en `testpaths`. No tocar imagen de BD.
- HTMX + Alpine disponibles vía django-cotton. Ya se usa patrón HTMX-partial en otras apps (mubil news-page, etc.).

## Goals / Non-Goals

**Goals:**

- Convertir una frase libre en 3 recomendaciones objetivas en < 4 s wall-clock mediano.
- Blindar frente a alucinación: Gemini **no decide qué sale**, sólo extrae preferencias y, al final, redacta explicación sobre datos ya seleccionados.
- Degradación limpia: cada eslabón del pipeline (extract → rank → explain) debe fallar sin tumbar el conjunto.
- Permitir que el ranking funcione aunque alguna promoción no tenga solar/clima/aire cacheados (p. ej. promociones nuevas sin backfill).
- Cero coupling cruzado: `apps.amenabar` no debe importar privados de `apps.mubil`.

**Non-Goals:**

- Precio €/m² como variable (depende de la idea #5 Comparables).
- Persistir queries / analytics (futura `MatchQuery` + dashboard).
- Captura de email para alertas (idea #15).
- Streaming / chat conversacional.
- Explicación por promoción con citas estructuradas (RAG-style). El párrafo es narrativo libre sobre un diccionario cerrado de datos.

## Decisions

### El LLM no decide qué promociones salen — pipeline en 3 pasos deterministas

**Decisión:** `extract_preferences` (LLM) → `rank_promociones` (ORM/PostGIS puro, sin LLM) → `generate_explanation` (LLM, sólo redacción). El LLM nunca ve el catálogo completo de promociones.

**Por qué:**
- La alucinación en LLMs sobre entidades concretas (nombres de promoción, direcciones) es un modo de fallo documentado. Mantener al LLM fuera de la decisión elimina el riesgo por diseño, no por prompt engineering.
- El SQL es nuestro: podemos añadir filtros duros (p. ej. `estado__in=['EN_VENTA','PROXIMA']`) sin confiar en que el prompt los respete.
- La UX de "párrafo generado" se mantiene porque Gemini redacta — pero sobre un dict cerrado de valores reales.

**Alternativa descartada:** pedir a Gemini que elija top-3 pasándole un resumen del catálogo. Más vulnerable a alucinación, no determinista para tests, y escala mal cuando el catálogo crece.

### Duplicar un helper Gemini mínimo en `services_match`, no importar de mubil

**Decisión:** `services_match.py` incluirá su propia función `_call_gemini_json(prompt, schema_dict)` (~40 líneas) replicando la fallback ladder de `mubil.ask.services._call_gemini_generate` pero orientada a extracción JSON (temperatura baja, parse con tolerancia).

**Por qué:**
- `_call_gemini_generate` es `_privado` en `mubil.ask.services` y acoplado a `embeddings.EmbeddingError`. Importarlo rompe encapsulación y crea una dependencia direccional `amenabar → mubil` que no queremos.
- Mover a `apps.core.gemini` sería scope creep (tocar mubil callers). Lo hacemos cuando sean 3+ consumidores.
- 40 líneas duplicadas tienen coste mantenimiento bajo; la lógica es estable (fallback ladder dura meses sin cambios).

**Alternativa descartada:** `from apps.mubil.ask.services import _call_gemini_generate`. Rechazada por los motivos de arriba.

### Dataclass + schema cerrado para preferencias, no diccionario libre

**Decisión:** `MatchPreferences` como `@dataclass(frozen=True)` con tipos explícitos y defaults. Validación por `__post_init__` que reduce valores fuera de rango al default (no raise).

**Por qué:**
- Hace el contrato explícito; cualquier consumidor sabe qué campos esperar sin leer el prompt del LLM.
- Permite que el fallback keyword simple construya un `MatchPreferences` directamente, sin pasar por serialización JSON intermedia.
- Robusto frente a Gemini devolviendo campos extra: los ignoramos.

**Alternativa descartada:** `pydantic.BaseModel`. Añadiría dependencia nueva al grafo (hoy no está en pyproject). `dataclass` + validación manual es suficiente para 10 campos.

### Score lineal ponderado con normalización por eje

**Decisión:** `total = sum(w_i * normalise(axis_i))`. Cada `axis_i` se normaliza al rango [0, 1] con una función explícita (p. ej. `solar: clamp((kwh - 900) / (1700 - 900), 0, 1)`). Pesos por defecto:

- `distance_to_pois`: 0.35
- `solar`: 0.20 (si `prefers_sunny` activo; si no, 0)
- `climate`: 0.20 (si `climate_preference != 'any'`; si no, 0)
- `air`: 0.15 (si `prefers_clean_air` activo; si no, 0)
- `fit_city`: 0.10 (match binario con `cities` si se especifica)

Pesos ausentes (por preferencia inactiva) se redistribuyen al eje de servicios para que el total siempre sume 1.

**Por qué:**
- Lineal es trivial de testear y auditar (ningún "black box"); el usuario puede entender por qué una promoción está primera.
- La redistribución mantiene el rango [0, 1] para que las cifras sean comparables entre consultas distintas.
- Los umbrales de normalización se eligen para el catálogo actual (kWh/kWp 900–1700 cubre todo España). Si el catálogo se expande, se re-calibran en una propuesta separada.

**Alternativa descartada:** aprendizaje automático sobre interacciones. Overkill sin tráfico real; empezamos con heurística auditable.

### El `breakdown` queda expuesto en la respuesta y guía la explicación

**Decisión:** `ScoredPromocion` incluye `breakdown: dict[str, float]` con los valores reales por eje (p. ej. `{"nearest_school_m": 320, "kwh_kwp_year": 1540, "pm25_latest": 7.4}`). La función `generate_explanation` recibe `prefs` + `breakdown` y nada más del catálogo.

**Por qué:**
- La UI puede mostrar las cifras clave debajo del párrafo narrativo (útil para el que no se fía del texto).
- Facilita tests: aseveras que `breakdown[eje]` toma el valor esperado antes de meter al LLM.
- Garantiza que Gemini no se inventa números: todo lo que puede citar está en el dict.

### Fallback keyword simple si Gemini falla en la extracción

**Decisión:** si `extract_preferences` lanza o devuelve inválido, caer a `_extract_keyword_fallback(user_text)` que detecta con regex:
- `budget_eur_min/max`: números con `€`, `k€`, `mil`.
- `bedrooms_min`: números seguidos de "dormitorios"/"habitaciones"/"hijos" (+1 por hijo asumiendo pareja).
- `cities`: match contra lista de ciudades conocidas (de `Promocion.ciudad distinct`).
- `prefers_sunny`: regex "sol", "soleado", "cálido".
- `prefers_clean_air`: regex "aire", "limpio", "contaminación".
- `climate_preference`: match con "costa", "mar", "interior", "montaña".

**Por qué:**
- No bloquear al usuario cuando Gemini quota se agota.
- Precisión baja pero suficiente para dar una respuesta útil con el disclaimer "modo degradado — no se pudo interpretar el texto completo".
- Mantiene el flujo determinista y testeable.

### HTMX request-response con partial, sin streaming

**Decisión:** `POST /amenabar/match/results/` devuelve HTML partial que HTMX inyecta en un contenedor `#match-results`. Indicador de carga simple vía atributo `hx-indicator`.

**Por qué:**
- El pipeline tarda ~2–4 s mediana; con un spinner el usuario tolera; streaming añade complejidad JS por una ganancia marginal.
- Coherente con el resto de la app (vistas Django + HTMX ya es el patrón del proyecto).
- Rinde bien en móvil 3G/4G sin requisitos de WebSocket.

**Alternativa descartada:** SSE / WebSocket para streaming del párrafo. Fuera de alcance MVP.

### Añadir una card nueva a `_ideas()` para que el match-maker aparezca en la home

**Decisión:** nueva entrada en `views._ideas()` con `estado='LIVE'`, `slug='match-maker'`, URL a `match_page`.

**Por qué:** la home ya es el shop-window de ideas. Que la nueva feature aparezca ahí hace natural el discovery sin tocar nada más de navegación.

## Risks / Trade-offs

- **Riesgo:** usuario escribe texto muy vago (p. ej. "quiero un piso") → extracción casi vacía → ranking cae al orden canónico (sólo distancia POI general).
  **Mitigación:** cuando `prefs` queda casi vacía, la UI muestra un mensaje "Afina tu búsqueda con detalles como presupuesto, nº de hijos, zona preferida…" + 3 promociones aleatorias disponibles. Honesto, no finge comprensión.
- **Riesgo:** cambios en el schema de respuesta de Gemini (p. ej. `generate_content` cambia shape).
  **Mitigación:** mismo helper que mubil, actualizar en los dos sitios cuando pase. Documentado en el docstring que viven en paralelo.
- **Riesgo:** latencia en free tier Gemini durante demos.
  **Mitigación:** fallback ladder del proyecto cubre quota 429 y cae de modelo. Explicación es opcional: si tarda > 3 s se omite.
- **Riesgo:** falta de datos (clima o aire aún no cacheados por depender de claves externas pendientes del usuario).
  **Mitigación:** el ranking degrada ejes sin datos; el match funciona desde el día 1 con sólo POIs + solar (ya cacheado 107/107).
- **Trade-off:** sin persistencia de queries no sabemos qué busca la gente. Si Amenabar lo valora, abrimos una propuesta nueva para `MatchQuery` + dashboard.
- **Trade-off:** pesos fijos vs. aprendidos. MVP con fijos; si hay tracción, pasar a aprendizaje supervisado requiere datos de interacción que hoy no tenemos.

## Migration Plan

1. **Dev:**
   - Ningún `migrate`.
   - Verificar que `GEMINI_API_KEY` está en `.env` (ya lo está porque mubil la usa).
   - Reiniciar `web_maps` tras cambios Python.
2. **Prod:** mismo. Sin backfills, sin cambios de infra.
3. **Rollback:** revertir commit; cero residuo.

## Open Questions

- ¿Qué hacemos si el usuario escribe en inglés? MVP: lo pasamos tal cual al prompt de Gemini (que es multilingüe); la UI responde en el idioma activo del proyecto. Si vemos mal recall con inglés, abrimos una propuesta de detección de idioma + prompt localizado. No cambia specs ni tareas.
