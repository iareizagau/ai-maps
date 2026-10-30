## Why

El change recién archivado `amenabar-pvgis-solar` metió en la ficha de cada promoción el dato de energía solar aprovechable. El comprador que valora obra nueva por confort y orientación todavía no tiene un ancla climática concreta: cuánto llueve, qué temperatura hace y cuántas horas de sol tiene **ese barrio** mes a mes. Añadir un climograma mensual (medias 1991-2020 de AEMET) termina de responder a la pregunta ambiental y refuerza el ángulo de sostenibilidad y confort del edificio.

## What Changes

- Dos modelos nuevos:
  - `AemetStation` — inventario completo de estaciones AEMET (≈850 España) con `idema`, `nombre`, `provincia`, `altitud_m`, `location` (PointField), `raw_json`. Dataset estable, se refresca manualmente cada muchos meses.
  - `PromocionClima` — 1:1 con `Promocion`, FK a la `AemetStation` **más cercana ≤ 50 km**, con `distance_m` y tres series mensuales de 12 valores (`temp_mean` °C, `precipitation` mm, `sun_hours` h), `period_label` (p.ej. `"1991-2020"`) y `raw_json` auditable.
- Nuevo módulo de servicio `services_aemet.py` que gestiona la indirección propia de AEMET OpenData (la primera llamada devuelve `{estado:200, datos: <url al JSON real>}`, hay que hacer un segundo GET) y expone `sync_stations()`, `nearest_station(point)`, `store_clima(promocion)`. Fallo silencioso: logs + `None`.
- Dos management commands separados:
  - `backfill_aemet_stations` — primera carga del inventario, idempotente.
  - `backfill_aemet_clima` — por promoción, con `--force` y `--slug` (igual que `backfill_pvgis`), rate-limit 1 req/s.
- Endpoint existente `promocion_pois` ([views.py:85](../../../src/apps/amenabar/views.py#L85)) extendido con un bloque `clima` retrocompatible (clientes antiguos lo ignoran):
  ```json
  "clima": {
    "station": "DONOSTIA/SAN SEBASTIAN - IGUELDO",
    "distance_m": 2130,
    "temp_mean": [...12...],
    "precipitation": [...12...],
    "sun_hours": [...12...],
    "period": "1991-2020"
  }
  ```
- Nuevo componente Cotton `cotton/molecules/climate_card.html` con 3 mini-climogramas apilados verticalmente mobile-first (base 375 px), siguiendo el mismo lenguaje visual que `solar_card.html` para que la ficha se sienta coherente. En el panel Leaflet se inserta vía un gemelo JS `_climateBlock()`, análogo al patrón ya validado de `_solarBlock()`.
- Nueva variable de entorno `AEMET_API_KEY` registrada en `config/settings/base.py` (mismo patrón que `ESIOS_TOKEN`, `EUSKALMET_API_KEY`, `OPENWEATHERMAP_API_KEY`).
- Tests pytest `apps/amenabar/tests/test_aemet.py` + fixtures recortadas: envelope 2-step, idempotencia del sync, nearest station ≤ 50 km, `store_clima` sin estación cercana devuelve `None`, endpoint incluye el bloque.

Fuera de alcance (futuras propuestas separadas): datos diarios/históricos (sólo normales 1991-2020); fallback a OpenWeatherMap si AEMET falla; signal `post_save` + Celery para recomputar automáticamente; dashboard admin más allá de `ModelAdmin` básico.

## Capabilities

### New Capabilities
- `amenabar/climate-normals`: calcular y mostrar las normales climatológicas mensuales (temperatura, precipitación, horas de sol) de cada promoción, cacheando la respuesta de AEMET OpenData.

### Modified Capabilities
<!-- Ninguna. Las specs de `amenabar/solar-potential` ya promovidas no cambian. -->

## Impact

- **Código**:
  - `src/apps/amenabar/models.py` (añade `AemetStation` + `PromocionClima`).
  - `src/apps/amenabar/services_aemet.py` (nuevo).
  - `src/apps/amenabar/management/commands/backfill_aemet_stations.py` (nuevo).
  - `src/apps/amenabar/management/commands/backfill_aemet_clima.py` (nuevo).
  - `src/apps/amenabar/views.py` (`promocion_pois` enriquecido).
  - `src/apps/amenabar/admin.py` (registro `AemetStation` + `PromocionClima` solo-lectura).
  - `src/apps/amenabar/tests/test_aemet.py` + `tests/fixtures/aemet_station_sample.json` + `tests/fixtures/aemet_normals_sample.json` (nuevos).
  - `src/apps/amenabar/migrations/0004_aemetstation_promocionclima.py` (migración autogenerada).
  - `src/templates/cotton/molecules/climate_card.html` (nuevo).
  - `src/templates/amenabar/promociones.html` (nuevo `_climateBlock()` + CSS gemelo).
  - `src/config/settings/base.py` (añade `AEMET_API_KEY`).
  - `.env.example` (añade `AEMET_API_KEY=`).
- **APIs externas**: AEMET OpenData (requiere clave gratuita). Sin nuevas dependencias Python.
- **BD**: dos tablas nuevas, una FK (`PromocionClima.station → AemetStation`) y un `OneToOneField` sobre `Promocion`. No afecta a tablas existentes.
- **Infra**: ninguna. No se cambia la imagen de BD (`timescale/timescaledb-ha:pg15`), ni se añade servicio Docker.
- **Despliegue**: tras merge → `migrate` + `backfill_aemet_stations` (una vez) + `backfill_aemet_clima` para rellenar las promociones existentes.
- **Rollback**: cero impacto sobre tablas existentes; `migrate amenabar 0003` + revertir commit.
- **Riesgo**: bajo. Degradación silenciosa si AEMET falla o la estación más cercana > 50 km. `raw_json` persistido para reingestar si cambia el schema.
