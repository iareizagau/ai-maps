## Context

Ver `proposal.md — Why` para la motivación. Resumen técnico del estado actual:

- `apps.amenabar` tiene dos modelos (`Promocion`, `POI`), un scraper + geocoder (`services.py`, ~540 líneas) y un endpoint JSON por slug ([`views.promocion_pois`](../../../src/apps/amenabar/views.py#L85)) que alimenta un panel Leaflet en [`promociones.html`](../../../src/templates/amenabar/promociones.html).
- Pila: Django 6, PostGIS, Timescale, Celery + Redis, HTMX + Alpine, django-cotton, pytest-django.
- Convenciones del proyecto (ver `.claude/CLAUDE.md`): mobile-first (base 375 px), `gettext_lazy`, `|unlocalize` al meter floats en URLs, docker `web` sin autoreload, imagen BD inmutable `timescale/timescaledb-ha:pg15`.
- Fuente externa: PVGIS v5.3 del JRC (`https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`). Sin clave, sin SLA publicado; se asume best-effort público. Un patrón análogo (requests + User-Agent identificable + fallback silencioso) ya está en `services.py` para Overpass y Nominatim.

## Goals / Non-Goals

**Goals:**

- Entregar un dato per-promoción (`kwh_kwp_year`, serie mensual) que la ficha pública consume sin latencia perceptible.
- Blindar la ficha frente a fallos de PVGIS: nunca romper el panel por una caída externa.
- Mantener la cadena de ingestas del proyecto consistente con lo ya existente (management command idempotente, flags `--force` y `--slug`, rate-limit explícito).
- Dejar el camino abierto a la evolución futura (ahorro €, amortización, signal post_save) sin obligarla ahora.

**Non-Goals:**

- Cálculos con sombras, orientación real de cubierta o modelos 3D del edificio. Se asume orientación óptima (sur, 30°).
- Precios eléctricos ni conversión a euros (futura propuesta separada con ESIOS/PVPC).
- Recomputación automática por signal Celery (futura propuesta separada).
- Panel/UI de administración más allá de un `admin.ModelAdmin` básico de solo lectura.
- Cálculo para otras apps del monorepo (`mubil`, `pintxos`…). La capacidad vive bajo `amenabar/`.

## Decisions

### Tabla separada 1:1, no columnas en `Promocion`

**Decisión:** nuevo modelo `SolarPotential` con `OneToOneField` a `Promocion`.

**Por qué:**
- Permite re-ingestar sin tocar la tabla principal (riesgo cero de corromper otros campos de `Promocion`).
- Guardar `raw_json` suelto en la tabla principal la ensucia; en una tabla aparte queda limpio y vacíable.
- Facilita migración futura a signal Celery (`post_save` sobre `Promocion` → task que escribe en `SolarPotential`).

**Alternativa descartada:** añadir cuatro columnas a `Promocion` (`solar_kwh_kwp_year`, `solar_monthly`, …). Más rápido en el momento pero mezcla preocupaciones y obliga a cambios de schema futuros.

### Fuente: PVGIS v5.3, parámetros fijos documentados

**Decisión:** llamada única a PVGIS por promoción con parámetros fijos (inclinación 30°, acimut 0° sur, pérdidas 14%, `crystSi`, `mountingplace=building`). Guardar los parámetros usados en la fila (`tilt_deg`, `azimuth_deg`, `system_loss_pct`, `pvgis_version`).

**Por qué:**
- Para un MVP, "orientación óptima" es la referencia estándar en el sector. Comparable entre promociones.
- Guardar los parámetros usados permite recomputar en el futuro con otros supuestos sin ambigüedad.
- `peakpower=1` → la respuesta ya viene en `kWh/kWp` directo, sin dividir manualmente.

**Alternativa descartada:** detectar orientación real a partir de la geometría del edificio. Requiere planos no públicos; fuera de alcance MVP.

### Fallo silencioso + `raw_json` persistido

**Decisión:** cualquier fallo (red, 5xx, JSON mal formado) se registra con `logger.warning` y la función `store_solar` devuelve `None`. El endpoint `promocion_pois` emite `null` en el bloque `solar`. El frontend oculta la tarjeta.

**Por qué:**
- La ficha debe seguir viva aunque PVGIS tenga un mal día (patrón que ya aplicamos para Overpass en `services.py`).
- Guardar `raw_json` permite reingestar sin repetir la llamada si descubrimos un bug de parseo.

**Alternativa descartada:** levantar excepción y propagar. Rompería la ficha pública por un fallo externo no crítico.

### Backfill por management command, no por signal

**Decisión:** solo un comando `backfill_pvgis` con flags `--force` y `--slug`. Rate limit `time.sleep(1.0)` entre llamadas.

**Por qué:**
- MVP: queremos control explícito sobre cuándo y a qué promociones se llama.
- El scrape de Amenabar no es diario; el flujo real es: scrape → geocode → backfill, orquestado manualmente o por script.
- Signal `post_save` + Celery se añade en una propuesta posterior cuando la cadencia lo justifique.

**Alternativa descartada:** signal + task Celery desde el principio. Más complejidad, más superficie de error en las pruebas, mínimo retorno hoy.

### Endpoint retrocompatible: nuevo bloque opcional

**Decisión:** extender la respuesta de `promocion_pois` con una clave de nivel superior `solar`, que será un objeto `{kwh_kwp_year, monthly}` o `null`.

**Por qué:**
- Clientes existentes (si los hubiera) ignoran la clave; cero riesgo de breaking change.
- La forma coincide con el patrón que ya tiene la respuesta (`nearest`, `pois`, `promocion`).

**Alternativa descartada:** endpoint separado `/promociones/<slug>/solar.json`. Añade un roundtrip extra desde el navegador para pintar un panel que ya se pinta de golpe.

### Componente Cotton reutilizable con SVG inline

**Decisión:** `cotton/molecules/solar_card.html` acepta `kwh_year` y `monthly` (lista de 12 floats) y renderiza:

- Un número grande con unidad `kWh/kWp · año`.
- 12 `<rect>` SVG, escaladas por `max(monthly)` para que febrero no quede plano.
- Mobile-first: contenedor base 375 px, altura ~96 px.

**Por qué:**
- Encaja con el patrón Atomic Design del proyecto.
- SVG inline evita librerías de charts (ni ApexCharts ni Chart.js), que son overkill para 12 barras planas.
- Permite reutilizar el mismo patrón en la futura tarjeta de clima AEMET (idea #4 del plan) cambiando datos y leyenda.

**Alternativa descartada:** gráfica en canvas con Chart.js. Añade peso al bundle y complejidad accesibilidad para muy poco valor en 12 datos planos.

## Risks / Trade-offs

- **Riesgo:** PVGIS devuelve 500 esporádicamente o tiene downtime no comunicado.
  **Mitigación:** fallo silencioso + `backfill_pvgis` reintentable; worst-case una promoción queda sin tarjeta hasta la siguiente ejecución.
- **Riesgo:** PVGIS cambia schema (v5.3 → v5.4) y el parseo se rompe.
  **Mitigación:** se guarda `raw_json` íntegro + `pvgis_version` por fila; un `backfill_pvgis --force` tras ajustar el parseo recupera todas las promociones.
- **Riesgo:** comprador técnico cuestiona la cifra ("mi tejado no mira al sur").
  **Mitigación:** disclaimer visible en la tarjeta ("estimación bajo orientación óptima; condiciones reales pueden variar"). Enlace futuro a cálculo personalizado.
- **Riesgo:** rate limit no documentado nos corta en mitad de un backfill grande.
  **Mitigación:** `time.sleep(1.0)` entre promociones. Con el catálogo actual de Amenabar (~decenas) el backfill tarda minutos; no es un cuello de botella.
- **Trade-off:** no se usa Celery de inicio → requiere disciplina operativa (correr el comando tras cada scrape nuevo). Aceptable para MVP; se cubrirá cuando añadamos signals.
- **Trade-off:** parámetros PV fijos → cifras no personalizables desde el panel. Suficiente para la demo comercial; parametrización en una propuesta futura.

## Migration Plan

1. **Dev:**
   - `docker compose exec web python manage.py migrate` tras aplicar la migración autogenerada.
   - `docker compose exec web python manage.py backfill_pvgis` para rellenar las promociones existentes.
   - `docker compose restart web` (requerido tras cambios Python por el `--noreload` del compose).
2. **Prod:** mismo orden en el script `scripts/deploy.sh` (ya ejecuta `migrate`; añadir una línea opcional de `backfill_pvgis` o dejarlo manual la primera vez).
3. **Rollback:** la migración añade una tabla nueva y un bloque opcional en un JSON. Rollback = `migrate amenabar <migración-anterior>` + revertir el commit. Cero impacto sobre `Promocion` o `POI`.

## Open Questions

- ¿Queremos exponer la tarjeta solar también en el popup Leaflet (cuando el usuario pasa el ratón sobre un marker) o solo en el panel de detalle? MVP = solo en el panel; decidir con feedback de usuario.
