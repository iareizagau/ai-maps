## Why

La landing de Amenabar hoy muestra el barrio alrededor de cada promoción (servicios y accesos), pero ninguna cifra sobre el edificio en sí. El comprador que valora obra nueva por eficiencia energética no tiene con qué anclar la conversación sobre autoconsumo. Añadir un dato concreto de **potencial fotovoltaico por ubicación** convierte la ficha en una herramienta de decisión y abre upsell natural con instalación solar llave en mano.

## What Changes

- Nuevo modelo `SolarPotential` (1:1 con `Promocion`) que cachea la respuesta de PVGIS v5.3 (JRC/EU): kWh/kWp anual, 12 valores mensuales, irradiación anual y parámetros usados.
- Nuevo módulo de servicio `services_pvgis.py` con `fetch_pvgis(lat, lon)` y `store_solar(promocion)`. Fallback silencioso: si PVGIS falla, no se bloquea la ficha.
- Nuevo management command `backfill_pvgis` (`--force`, `--slug`), rate-limit 1 req/s por cortesía.
- Endpoint existente `promocion_pois` (actualmente en [views.py:85](../../../src/apps/amenabar/views.py#L85)) extendido con bloque `solar` cuando la promoción tiene datos; **no se rompe el contrato**: clientes que ignoren la clave siguen funcionando.
- Nuevo componente Cotton `cotton/molecules/solar_card.html` con número grande kWh/kWp·año + 12 barras SVG mensuales, mobile-first (base 375 px).
- Tests pytest en `apps/amenabar/tests/test_pvgis.py`: parsing, idempotencia, endpoint, flag `--force`.

Fuera de alcance (futuras propuestas separadas): ahorro en € con PVPC (ESIOS), amortización 4 kWp, signal Celery `post_save` para recomputar automáticamente.

## Capabilities

### New Capabilities
- `amenabar/solar-potential`: calcular y mostrar el potencial fotovoltaico anual y mensual por promoción, usando PVGIS v5.3 como fuente autoritativa y cacheando el resultado para consulta rápida desde la ficha pública.

### Modified Capabilities
<!-- Ninguna: la app amenabar no tiene specs previos; esta propuesta inaugura su carpeta en openspec/specs/. -->

## Impact

- **Código**:
  - `src/apps/amenabar/models.py` (añade `SolarPotential`).
  - `src/apps/amenabar/services_pvgis.py` (nuevo).
  - `src/apps/amenabar/management/commands/backfill_pvgis.py` (nuevo).
  - `src/apps/amenabar/views.py` (`promocion_pois` enriquecido).
  - `src/apps/amenabar/tests/test_pvgis.py` + `tests/fixtures/pvgis_sample.json` (nuevos).
  - `src/apps/amenabar/migrations/0003_solarpotential.py` (nueva migración autogenerada).
  - `src/templates/cotton/molecules/solar_card.html` (nuevo).
  - `src/templates/amenabar/promociones.html` (hueco para la tarjeta en el panel de detalle).
- **APIs externas**: PVGIS v5.3 (sin clave, dominio público JRC EU). No añade dependencia de npm/pip.
- **BD**: una tabla nueva, FK sobre `promocion`. No afecta a tablas existentes.
- **Infra**: ninguna. No se cambia la imagen de BD (`timescale/timescaledb-ha:pg15`), ni se suma servicio Docker.
- **Despliegue**: tras merge, correr migración + un `backfill_pvgis` manual en producción (una vez). El backfill continuo queda para una propuesta de signals/Celery posterior.
- **Riesgo**: bajo. Degradación silenciosa si PVGIS falla; `raw_json` guardado permite reingestar si cambia el schema v5.3 → v5.4.
