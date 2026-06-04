# Route — Plan de mejora (post-advisor)

Estado y plan congelado el 2026-06-04. Deadline MUBIL: 2026-06-19.

## Estado actual

- `route.html` y `_route_result.html` siguen como en `main` (commit `ed2be0e`). **No hay cambios sin commitear** en el módulo.
- `models.py` fue **truncado a 0 líneas** por un `ENOSPC` durante el primer Edit y **restaurado vía `git checkout HEAD -- src/apps/mubil/models.py`**. Confirmado: 457 líneas, idéntico a `main`.
- El trabajo se detuvo antes de tocar ningún fichero de producción del módulo `route/`.

### Bloqueador descubierto

Disco `C:` al 97% (19 GB libres) provocó un fallo de escritura que truncó `models.py`. Antes de retomar, **liberar espacio** y verificar que la herramienta de Edit no vuelve a truncar. Síntomas a vigilar: `ENOSPC`, "file has been modified since read" tras un Edit, ficheros que pasan a 0 bytes.

## Decisiones tomadas (cuestionario respondido por el usuario)

| Pregunta | Decisión |
|---|---|
| Alcance | **Todo**: O/D libre + cargadores OCM + PVPC horario + comparativa ICE. |
| Stepper en Route | **No** — una sola vista, no replicar el stepper de advisor. |
| Bridge advisor↔route | **Sí** — vehículo elegido en advisor se preselecciona en Route vía sesión. |
| Cargadores reales | **Todos los DC ≥ 50 kW a < 5 km de la ruta** (`ST_DWithin` sobre LineString). |
| Coste por hora de salida | **Chart 24h ECharts con highlight de la hora elegida.** |
| 5 demos | **Mantener como chips de "ruta rápida"** sobre el mapa para onboarding. |

## Reutilización confirmada (no reinventar)

| Pieza | Origen | Uso |
|---|---|---|
| `advisor.services.get_commute_route(start_lng, start_lat, end_lng, end_lat)` | [advisor/services.py:442](../advisor/services.py#L442) | Núcleo del O/D libre. Ya tiene pgRouting + fallback OSRM + fallback geométrico. |
| `ChargingStation.objects.nearby()` / `.fast()` | [models.py:222](../models.py#L222) | Base para `.along_route()`. Añadir método nuevo (pendiente). |
| `pvpc_ingest.current_price_eur_kwh(night_charging=...)` | [data/pvpc_ingest.py:207](../data/pvpc_ingest.py#L207) | Ya en `route/services.py`. |
| `pvpc_ingest.recent_avg_eur_kwh(tariff=...)` | [data/pvpc_ingest.py:180](../data/pvpc_ingest.py#L180) | Base para la curva 24h. |
| `EnergyPricePVPC` (timestamp, tariff, price_eur_mwh) | [models.py:275](../models.py#L275) | Group-by hora-del-día para el chart. |
| `fuel_ingest.current_price_eur_l(fuel_key='gasolina_95_e5', postal_code=cp)` | [data/fuel_ingest.py:213](../data/fuel_ingest.py#L213) | Coste ICE comparativo. |
| `cp_centroids.lookup(cp)` → `(lat, lon, name)` | [data/cp_centroids.py:33](../data/cp_centroids.py#L33) | Si hay `cp` en sesión, pre-rellenar origen del mapa. |
| Patrón ECharts | [templates/mubil/advisor.html](../../../templates/mubil/advisor.html) | Curvas SOC vs km y coste vs hora. |
| Patrón Leaflet click O/D | sección advisor commute en [advisor.html](../../../templates/mubil/advisor.html) | Mapa interactivo de origen/destino. |
| Tema Estrata (colores `estrata-teal*`, `estrata-navy*`) | `advisor.html` | Reemplazar el cyan actual de Route. |

## Fases

### Fase 1 — Backend core (`route/services.py`, `models.py`)

**Objetivo**: que `services.plan(...)` acepte O/D libres y devuelva todos los datos que el frontend necesita.

Cambios:
- **`models.py`**: añadir `ChargingStationQuerySet.along_route(polyline_lonlat, radius_km=5)` con `geom__dwithin=(LineString, D(km=...))` + `Distance` annotation, ordenado por proximidad a la línea.
- **`route/services.py`**:
  - Extender `RoutePlanResult` con campos nuevos (con default para mantener compat):
    - `soc_curve: List[Tuple[float, float]]` — `(km_acum, soc_pct)` muestreado sobre el polyline.
    - `cost_by_hour: List[Tuple[int, float]]` — 24 valores `(hora, eur)` del coste total del viaje si saliese a esa hora.
    - `nearby_chargers: List[dict]` — top-N cargadores DC ≥50kW a <5km de la ruta.
    - `selected_charger: Optional[dict]` — el elegido si hay parada.
    - `ice_baseline: dict` — `{cost_eur, fuel_l, vs_ev_pct, vs_ev_eur}`.
    - `departure_hour: int`, `mode: 'demo' | 'free'`.
  - Nueva firma:
    ```python
    def plan(*, slug: str | None = None,
             origin_lng: float | None = None, origin_lat: float | None = None,
             dest_lng: float | None = None, dest_lat: float | None = None,
             vehicle_id: int | None = None,
             soc_start_pct: float = 80.0,
             departure_hour: int | None = None) -> RoutePlanResult
    ```
    - Si `slug` → usa la demo (rápido, sin pgRouting).
    - Si O/D → llama a `advisor.services.get_commute_route(...)`.
  - `_pvpc_24h_curve()`: media por hora-del-día sobre últimos 7d desde `EnergyPricePVPC`. Fallback al precio medio si la tabla está vacía.
  - `_ice_trip_cost(distance_km, cp=None)`: usa `fuel_ingest.current_price_eur_l('gasolina_95_e5', postal_code=cp)` × `6.5 L/100 km`.
  - `_chargers_along_route(polyline, radius_km=5, min_kw=50, limit=10)`: usa el nuevo queryset.
  - `_select_charge_stop(...)`: si SOC baja del reserve, elige el cargador rápido más cercano al punto donde se cruza el umbral (no el midpoint geométrico ficticio).
- **Tests** (`tests/test_route_services.py`): asegurar (a) demo legacy sigue funcionando, (b) modo libre con O/D devuelve polyline pgRouting/OSRM, (c) `ice_baseline` calcula coste creíble, (d) `cost_by_hour` tiene 24 valores monotónicos respecto a PVPC.

**Estimación**: ~1.5 días. **Riesgo**: bajo (puro reuse de advisor).

### Fase 2 — Bridge advisor → route (sesión)

**Objetivo**: si el usuario eligió un coche en advisor, Route lo encuentra preseleccionado.

Cambios:
- `views.advisor_quote` (POST): tras calcular, guardar `request.session['mubil_route_prefill'] = {'vehicle_target_id': ..., 'cp': ...}` (set/forget, no afecta al render actual).
- `views.route_page`: leer `request.session.get('mubil_route_prefill', {})` y pasar `default_vehicle_id` + `default_origin_cp` al template. Si hay `cp`, resolver a (lat, lon) con `cp_centroids.lookup()` para precargar el mapa.
- No tocar `advisor_page` ni el flujo TCO existente.

**Estimación**: ~0.5 días. **Riesgo**: bajo.

### Fase 3 — Frontend (`templates/mubil/route.html`)

**Objetivo**: una vista única, tema Estrata, mapa Leaflet click O/D, chips de demos, selector vehículo con búsqueda y variantes, slider SOC, selector hora.

Cambios:
- Header al estilo advisor (`Volver` + `Route · Planificador EV` en `estrata-teal`), dark mode con `estrata-navy_deep`.
- **Quitar** el `<select name="slug">` actual.
- Layout 2 columnas en `lg:`, 1 columna mobile-first:
  - **Columna izquierda — input**:
    - Mapa Leaflet (h=380px) con primer click = origen, segundo click = destino. Botón "Reiniciar marcadores".
    - Fila de chips arriba del mapa con los 5 demos (`Donostia↔Bilbao`, etc.) — click rellena O/D en el mapa.
    - Selector de vehículo: input de búsqueda + suggestions (reutilizar el componente de advisor 1b modo `search`). Preselect desde sesión.
    - Slider SOC inicial (10-100, step 5). Conserva el actual.
    - Slider hora de salida (0-23). Por defecto, la hora actual del servidor.
    - Botón "Planificar ruta" (HTMX `hx-post`).
  - **Columna derecha — resultado**: `<div id="route-result">` igual que ahora, pero el partial cambia (fase 4).
- Sin stepper, sin pasos. Form único.
- Mobile-first: en `<sm`, todo apilado; el mapa se pone en h=240px.
- Hidden inputs nuevos: `origin_lng`, `origin_lat`, `dest_lng`, `dest_lat`, `departure_hour`. Si vacíos y hay `slug`, el endpoint usa la demo.

**Estimación**: ~2 días. **Riesgo**: medio (Alpine + Tailwind nuevos variantes → recordar `npm run build:css`).

### Fase 4 — Resultado enriquecido (`templates/mubil/_route_result.html`)

**Objetivo**: el resultado que vende a los jueces.

Cambios:
- Mantener: headline, stat cards (distancia/duración/energía/coste), SOC bar, mapa, lista de segmentos.
- **Añadir, en este orden**:
  1. **Badge EV vs ICE** debajo de los stat cards: `🟢 Ahorras 10,42 € vs. gasolina` (cierre del bucle advisor↔route).
  2. **Card "Curva SOC vs km"**: ECharts line chart, eje X = km, eje Y = SOC%, marcadores en parada de carga si la hay. Pintado en `estrata-teal`.
  3. **Card "Coste por hora de salida"**: ECharts bar chart, eje X = 0–23 h, eje Y = €, barras valle/llano/punta coloreadas distinto, highlight en la hora elegida. Anotación "Mejor: 03:00 → ahorras 1,80 €".
  4. **Mapa**: ya existe; añadir capa de cargadores DC ≥50kW a <5km (markers tenues), y resaltar el cargador elegido si hay parada.
  5. **Lista cargadores cercanos a la ruta**: top 5 con operador / kW / distancia a la ruta. Click → centra mapa en el cargador.
- ECharts ya está cargado en `advisor.html`; añadirlo a `route.html` (o moverlo a `base.html` si conviene global).

**Estimación**: ~2 días. **Riesgo**: medio (ECharts dual + filtros mapa).

## Lo que NO se hace (decisión explícita)

- ❌ Stepper multi-paso en Route.
- ❌ Foto del permiso de circulación (es de advisor; en Route ya sabes qué coche tienes).
- ❌ Recomendador de coche en Route (no aplica al planificador).
- ❌ PDF export (post-deadline si sobra tiempo).
- ❌ Multi-stop, viaje vuelta, semana de commute (sobre-scope).

## Cómo retomar

1. Liberar disco en `C:\` (objetivo: >40 GB libres) y reiniciar Docker Desktop si fuera necesario.
2. Verificar con un `git status` que `models.py` sigue intacto.
3. Empezar por **Fase 1** — el orden importa (Fase 2 depende de 1, Fase 4 depende de los nuevos campos de `RoutePlanResult` de Fase 1).
4. Tras Fase 1, ejecutar `docker compose exec web pytest apps/mubil/tests/` y `docker compose restart web` antes de tocar Fase 3.
