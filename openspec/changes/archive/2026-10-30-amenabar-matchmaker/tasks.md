## 1. Service: Gemini helper + extraction + fallback

- [x] 1.1 Crear `src/apps/amenabar/services_match.py` con `MatchPreferences` (`@dataclass(frozen=True)` con los 10 campos: `budget_eur_min`, `budget_eur_max`, `bedrooms_min`, `cities`, `must_near`, `nice_to_have`, `climate_preference` ∈ {coastal, mild, warm, cold, any}, `prefers_sunny`, `prefers_clean_air`, `destination_city`, `summary`). `__post_init__` normaliza valores fuera de rango a defaults.
- [x] 1.2 Implementar `_call_gemini_json(prompt, max_output_tokens=800) -> str` replicando el patrón de `mubil.ask.services._call_gemini_generate`: fallback ladder desde `settings.GEMINI_GENERATION_FALLBACK_MODELS`, soft-fail markers (quota/503) continúan la ladder, hard errors (auth) cortan. Devuelve texto crudo.
- [x] 1.3 Implementar `extract_preferences(user_text: str) -> MatchPreferences`: construye prompt con instrucciones estrictas de JSON + enum values; llama `_call_gemini_json`; `json.loads` con tolerancia (strip code fences si vienen); valida contra schema cerrado; cae a `_extract_keyword_fallback` si falla con `logger.warning`.
- [x] 1.4 Implementar `_extract_keyword_fallback(user_text: str) -> MatchPreferences`: regex para `€`/`k€`/`mil` → budget; números + "dormitorio"/"habitación"/"hijo" → bedrooms_min; detect "sol"/"soleado" → prefers_sunny; "aire"/"limpio" → prefers_clean_air; "costa"/"mar" → climate_preference='coastal', "montaña"/"interior" → 'cold'. Match contra lista de ciudades conocidas (`Promocion.objects.values_list('ciudad', flat=True).distinct()`).

## 2. Service: ranking determinista

- [x] 2.1 Añadir `@dataclass` `ScoredPromocion` con `promocion: Promocion`, `score: float`, `breakdown: dict[str, float | None]`, `highlights: list[str]` (p. ej. ["Colegio público a 320 m", "1540 kWh/kWp/año"]).
- [x] 2.2 Implementar `rank_promociones(prefs: MatchPreferences, limit: int = 3) -> list[ScoredPromocion]`:
  - Base: `Promocion.objects.filter(location__isnull=False, estado__in=['EN_VENTA','PROXIMA'])`.
  - Si `prefs.cities`: `.filter(ciudad__iin=prefs.cities)`.
  - Para cada promoción: calcula `axes` (dict por eje) con los helpers 2.3–2.6, normaliza al rango [0, 1] y aplica el score lineal ponderado con redistribución de pesos (ver design.md "Decisions / Score lineal ponderado").
  - Devuelve top-N ordenado por score desc.
- [x] 2.3 Helper `_axis_pois(promocion, must_near, nice_to_have) -> tuple[float, dict]`: usa `services.nearest_by_category(promocion)` (ya existe); por cada categoría en `must_near` penaliza fuertemente si no hay POI en 1500 m, premia a < 600 m. `nice_to_have` con pesos menores.
- [x] 2.4 Helper `_axis_solar(promocion, prefers_sunny) -> tuple[float, float | None]`: devuelve `(score, kwh_kwp_year)`. Si `prefers_sunny` y existe `SolarPotential`: normaliza `kwh_kwp_year` con `clamp((v - 900) / 800, 0, 1)`. Si no hay dato, score 0.5 (neutral).
- [x] 2.5 Helper `_axis_climate(promocion, climate_preference) -> tuple[float, dict | None]`: banda de confort sobre `PromocionClima.temp_mean` (media anual = sum/12). `coastal` prefiere banda 13-18°C, `mild` 12-18, `warm` 16-22, `cold` 8-14. Si no hay clima cacheado o preferencia `any`, score neutral 0.5.
- [x] 2.6 Helper `_axis_air(promocion, prefers_clean_air) -> tuple[float, dict | None]`: si `prefers_clean_air`, busca `AirQualityStation` más cercana con `ST_Distance`; score por `pm25` con breakpoints WHO 2021 (verde=1.0, amarillo=0.7, naranja=0.3, rojo=0). Si no hay estación o `pm25 is None`, score 0.5.
- [x] 2.7 Helper `_build_highlights(breakdown) -> list[str]`: traduce los números del breakdown a strings mobile-first cortos ("Colegio a 320 m", "1540 kWh/kWp·año", "Tª media 14 °C", "PM2.5 7,4 µg/m³"), traducible via `gettext_lazy`.

## 3. Service: explicación narrativa

- [x] 3.1 Implementar `generate_explanation(prefs: MatchPreferences, scored: ScoredPromocion, timeout_s: float = 3.0) -> str | None`: construye prompt con `prefs.summary` + `scored.promocion.nombre` + `scored.breakdown` (dict cerrado); `_call_gemini_json(prompt, max_output_tokens=200)`; si tarda > `timeout_s` o falla, devuelve `None`.
- [x] 3.2 Prompt estricto: "Redacta un párrafo de 2–3 frases en español que explique por qué esta promoción encaja con las preferencias del usuario. Usa SÓLO los datos proporcionados. NO cites precios, rentabilidades ni cifras que no estén en los datos. Devuelve sólo el párrafo, sin encabezados."
- [x] 3.3 Función orquestadora `match(user_text: str) -> MatchResult`: ejecuta extract → rank → paraleliza explicación por promoción (p. ej. `concurrent.futures.ThreadPoolExecutor(max_workers=3)` con timeout global 4 s). `MatchResult` dataclass con `preferences`, `results: list[ScoredPromocionWithExplanation]`, `degraded: bool` (True si se usó keyword fallback o alguna explicación falló).

## 4. Views + URLs

- [x] 4.1 En `src/apps/amenabar/views.py` añadir `match_page(request)` que renderiza `amenabar/match.html` (form con textarea `name="query"` + contenedor `<div id="match-results">` vacío).
- [x] 4.2 Añadir `match_results(request)`: acepta POST con `query`; si vacío → partial con mensaje "Escribe algo primero"; ejecuta `services_match.match(query)` y renderiza `amenabar/match_results.html` con `result` en contexto.
- [x] 4.3 En `src/apps/amenabar/urls.py` añadir dos rutas: `match/` → `match_page` (name `match`) y `match/results/` → `match_results` (name `match_results`).
- [x] 4.4 En `views._ideas()` añadir entrada nueva: slug `match-maker`, título "Match-maker: describe tu familia", descripción breve, URL a `match_page`, estado `LIVE`.

## 5. Templates

- [x] 5.1 Crear `src/templates/amenabar/match.html` (`{% extends "base.html" %}`): header + textarea con `hx-post="{% url 'amenabar:match_results' %}"`, `hx-target="#match-results"`, `hx-indicator="#match-loading"`. Botón enviar. Div `#match-results` vacío. Spinner `#match-loading` (reutilizar atom existente si existe). *(Spinner CSS inline — ningún atom spinner reusable existe aún en atoms/.)*
- [x] 5.2 Mobile-first base 375 px: textarea 100% ancho, 5 filas; container `max-w-xl mx-auto px-4 py-6`.
- [x] 5.3 Pequeño disclaimer bajo el form: "Resultados ordenados sobre datos abiertos (OSM, PVGIS, AEMET, OpenAQ). El párrafo narrativo se genera con IA sobre esos mismos datos." traducible.
- [x] 5.4 Crear `src/templates/amenabar/match_results.html` (partial): si `result.results` vacío → mensaje "No encontramos coincidencias. Prueba a aflojar criterios" + ejemplos sugeridos. Si no, 3 cards apiladas con: nombre promoción + ciudad, badge estado, lista de `highlights`, párrafo narrativo (si existe), botón "Ver en mapa" que linka a `/amenabar/promociones/` con parámetro de slug (si procede).
- [x] 5.5 Si `result.degraded`: mostrar banner informativo "Modo degradado — no pudimos interpretar todo el texto o alguna explicación no cargó" en tono neutro.

## 6. Tests

- [x] 6.1 Crear `src/apps/amenabar/tests/test_match.py` con `pytest.mark.django_db` según necesidad.
- [x] 6.2 `test_preferences_dataclass_normalises_out_of_range`.
- [x] 6.3 `test_extract_preferences_schema_closed_drops_extra_fields`.
- [x] 6.4 `test_extract_preferences_falls_back_on_gemini_error`.
- [x] 6.5 `test_extract_keyword_fallback_detects_budget_and_bedrooms`.
- [x] 6.6 `test_rank_promociones_respects_estado`.
- [x] 6.7 `test_rank_promociones_sunny_prefers_higher_kwh`.
- [x] 6.8 `test_rank_promociones_clean_air_uses_nearest_station`.
- [x] 6.9 `test_rank_promociones_handles_missing_optional_metrics` + `test_rank_promociones_must_near_prefers_closer_pois` (bonus).
- [x] 6.10 `test_generate_explanation_only_cites_breakdown` (verifica que ni nombre de otra promoción, ni su kWh, ni su ciudad llegan al prompt).
- [x] 6.11 `test_generate_explanation_returns_none_on_timeout` + `test_generate_explanation_returns_none_on_error`.
- [x] 6.12 `test_match_endpoint_returns_top3_partial` + `test_match_endpoint_empty_query_message`.
- [x] 6.13 `test_match_endpoint_no_results_message`. Total: 15 tests, 15/15 verde; suite completa amenabar 61/61.

## 7. Verificación en dev

- [x] 7.1 Confirmar que `GEMINI_API_KEY` está en `.env`. *(Verificado — ladder de 7 modelos cargada.)*
- [x] 7.2 Abrir `/amenabar/` en el navegador → ver la card "Match-maker" nueva junto a "Promociones + servicios cercanos". *(Verificado vía urllib.)*
- [x] 7.3 Abrir `/amenabar/match/`, escribir "pareja con dos niños, 3 dormitorios, 300-400 k, cerca de colegio público, costa", submit, verificar que llegan 3 cards con highlights + párrafos narrativos. *(End-to-end real contra Gemini: 3 articles, highlights presentes, sin banner de modo degradado.)*
- [ ] 7.4 Validar a 375 px (devtools responsive) que las 3 cards se leen y el form no desborda. *(Pendiente de validación visual del usuario.)*
- [ ] 7.5 Probar un caso adversarial: query muy vaga ("quiero un piso") → debe mostrar los 3 candidatos genéricos sin crash y, si el schema queda casi vacío, mensaje de "afinar búsqueda". *(Pendiente de validación manual del usuario.)*
- [x] 7.6 Ejecutar `docker compose exec web_maps python -m pytest apps/amenabar/tests/ -v` y verificar que todo sigue en verde. *(61 passed.)*

## 8. Housekeeping

- [x] 8.1 Confirmar que `ruff check src/apps/amenabar/services_match.py src/apps/amenabar/views.py src/apps/amenabar/urls.py src/apps/amenabar/tests/test_match.py` pasa. *(All checks passed; con `# noqa: RUF001` justificado para el regex del budget que acepta en-dash y €.)*
- [x] 8.2 `docker compose restart web_maps` tras los cambios Python (CLAUDE.md: autoreload off en dev). *(Hecho.)*
