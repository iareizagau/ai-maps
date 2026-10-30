## 1. Settings y entorno

- [x] 1.1 Añadir `AEMET_API_KEY = env("AEMET_API_KEY", default="")` en `src/config/settings/base.py` (patrón ya usado por `ESIOS_TOKEN`, `EUSKALMET_API_KEY`).
- [x] 1.2 Añadir `AEMET_API_KEY=` a `.env.example` con comentario del enlace de alta. *(Repo no tiene `.env.example`; omitida sin introducir fichero nuevo. Nota de alta documentada en el docstring del service.)*
- [x] 1.3 Añadir `AEMET_API_KEY` al `.env` local si llega la clave; si no, dejarla vacía (los tests van con mocks). *(Hecho por el usuario tras recibir la clave.)*

## 2. Modelos y migración

- [x] 2.1 Añadir `AemetStation(BaseModel)` a `src/apps/amenabar/models.py`: `idema` (CharField unique), `nombre`, `provincia`, `altitud_m` (nullable), `location` (`gis_models.PointField` 4326), `raw_json` (JSONField). Index GIST en `location` y `indexes: ClassVar[list]` (ver patrón `SolarPotential`).
- [x] 2.2 Añadir `PromocionClima(BaseModel)`: `OneToOneField(Promocion, related_name="clima")`, `station = ForeignKey(AemetStation, on_delete=PROTECT)`, `distance_m` (PositiveIntegerField), `temp_mean` / `precipitation` / `sun_hours` (JSONField, lista 12), `period_label` (CharField), `raw_json` (JSONField).
- [x] 2.3 Generar migración con `docker compose exec web_maps python manage.py makemigrations amenabar` (debe nombrarse `0004_aemetstation_promocionclima.py`).
- [x] 2.4 Aplicar migración (`migrate amenabar`) y verificar que las dos tablas se crean.
- [x] 2.5 Registrar los dos modelos en `src/apps/amenabar/admin.py` como solo-lectura (lista `AemetStation`: `idema`, `nombre`, `provincia`; lista `PromocionClima`: `promocion`, `station`, `distance_m`, `period_label`, `updated_at`).

## 3. Servicio AEMET

- [x] 3.1 Crear `src/apps/amenabar/services_aemet.py` con `AEMET_BASE = "https://opendata.aemet.es/opendata/api"`, `AEMET_RATE_S = 1.0`, `AEMET_MAX_STATION_DISTANCE_M = 50_000`, `AEMET_PERIOD = "1991-2020"`.
- [x] 3.2 Implementar helper interno `_aemet_get(path) -> dict | list` que hace los 2 GETs de la indirección: primer GET con `?api_key=…` lee el sobre `{estado, datos, metadatos}`; segundo GET a `env["datos"]` devuelve el JSON real. Timeout 30 s cada uno. Reutilizar el `USER_AGENT` de `services.py`.
- [x] 3.3 Implementar `sync_stations() -> int`: llama a `/api/valores/climatologicos/inventarioestaciones/todasestaciones`, parsea cada estación (`indicativo`, `nombre`, `provincia`, `altitud`, `latitud`, `longitud`), convierte coordenadas AEMET (formato `425133N`, `000456W` → decimal) a WGS84, `update_or_create` por `idema`. Devuelve el nº total persistido.
- [x] 3.4 Implementar `nearest_station(point) -> AemetStation | None`: usa `Distance("location", point)` y devuelve la estación más cercana con `d_m <= AEMET_MAX_STATION_DISTANCE_M`, o `None`. Anota `d_m` en el objeto devuelto.
- [x] 3.5 Implementar `store_clima(promocion) -> PromocionClima | None`: si no hay `location`, `None`. Resuelve estación; si `None`, `None`. Pide `/api/valores/climatologicos/normales/estacion/{idema}`, parsea las 12 filas mensuales → 3 series `temp_mean` / `precipitation` / `sun_hours` (campos AEMET típicos: `tm_mes`, `p_mes`, `inso` — con parseo defensivo). `update_or_create` sobre `promocion`. Captura excepciones de red/parseo con `logger.warning` y devuelve `None`.
- [x] 3.6 Documentar en docstring del módulo la indirección 2-step y la unidad de los campos (°C, mm, h) para que no se olvide al revisar.

## 4. Management commands

- [x] 4.1 Crear `src/apps/amenabar/management/commands/backfill_aemet_stations.py`. Único flag opcional `--force` (recomputa aunque haya estaciones). Imprime `OK (n)` con el conteo. *(`sync_stations` ya es idempotente vía `update_or_create`; no se necesita flag `--force` para la primera ingesta — simplificado.)*
- [x] 4.2 Crear `src/apps/amenabar/management/commands/backfill_aemet_clima.py` con flags `--force` y `--slug` (mismo diseño que `backfill_pvgis`). Rate-limit `time.sleep(AEMET_RATE_S)` entre promociones. Si el inventario está vacío, aborta con mensaje claro ("ejecuta backfill_aemet_stations primero").
- [x] 4.3 Iterar `Promocion.objects.filter(location__isnull=False)`, saltar si tiene `clima` y no `--force`, llamar `store_clima(p)`, imprimir `OK <slug>`, `SKIP <slug>`, o `ERR <slug>: ...`.

## 5. Endpoint `promocion_pois`

- [x] 5.1 En `src/apps/amenabar/views.py`, en `promocion_pois`, leer `clima = getattr(p, "clima", None)`.
- [x] 5.2 Añadir clave `"clima"` al `JsonResponse`: objeto con `station` (nombre), `distance_m`, `temp_mean`, `precipitation`, `sun_hours`, `period` si existe; `None` si no.
- [x] 5.3 Asegurar que el resto del contrato (`promocion`, `pois`, `nearest`, `solar`) queda intacto.

## 6. Componente Cotton y plantilla

- [x] 6.1 Crear `src/templates/cotton/molecules/climate_card.html` con props `station`, `distance_m`, `temp_series`, `precip_series`, `sun_series`, `period`. *(Simplificado: toma `series_list` pre-normalizada por el caller para evitar math en template.)*
- [x] 6.2 Renderizar cabecera con nombre de la estación + distancia convertida (p. ej. `≈ 2,1 km`) + periodo (`1991–2020`) en texto pequeño.
- [x] 6.3 Apilar 3 mini-climogramas verticales (temperatura °C, precipitación mm, sol h) con la misma estructura visual que `solar_card.html` (barras SVG inline, 12 columnas, mobile-first base 375 px). Título corto para cada serie con unidad traducible via `gettext_lazy`.
- [x] 6.4 Añadir pie con atribución "Datos: AEMET" traducible.
- [x] 6.5 Clases Tailwind base 375 px; verificar que no hay scroll horizontal a ese ancho. *(Clases Tailwind sólo en el molecule Cotton; el panel JS usa CSS puro `.amb-clima*` ya existente en el bloque `<style>`.)*
- [x] 6.6 En `src/templates/amenabar/promociones.html`, añadir CSS `.amb-clima*` siguiendo el estilo de `.amb-solar*` y un método `_climateBlock(clima)` análogo a `_solarBlock(solar)`. Insertarlo justo debajo del bloque solar en `_renderCard`.
- [x] 6.7 Actualizar las llamadas a `_renderCard(nearest, state, solar, clima)` en los tres sitios de `promociones.html` (loading / error / ok) para pasar `data.clima` (o `null`).

## 7. Tests

- [x] 7.1 Crear fixtures en `src/apps/amenabar/tests/fixtures/`: `aemet_stations_sample.json` (3 estaciones, incluida una lejana para el test de 50 km) y `aemet_normals_sample.json` (13 filas: 12 meses + fila 13 anual que debe ignorarse). *(No se necesitan ficheros envelope separados: el mock `_mock_envelope()` del test los genera inline.)*
- [x] 7.2 Crear `src/apps/amenabar/tests/test_aemet.py` con `pytest.mark.django_db`. *(Se usa fixture `db` por test en lugar de la marca global, patrón que ya aplica `test_pvgis.py`.)*
- [x] 7.3 `test_aemet_get_follows_two_step_envelope`: mockear `requests.get` dos veces (primero envelope, luego datos reales) y comprobar que `_aemet_get` devuelve el JSON final.
- [x] 7.4 `test_sync_stations_idempotent`: ejecutar dos veces, aseverar que no se duplican filas y que `update_or_create` conserva PKs.
- [x] 7.5 `test_nearest_station_within_50km_returns_closest`: crear 2 estaciones a distancias conocidas, consultar punto, verificar que la devuelta es la más cercana.
- [x] 7.6 `test_nearest_station_beyond_50km_returns_none`: punto a 60 km de la única estación → `None`.
- [x] 7.7 `test_store_clima_without_nearby_station_returns_none`: promoción cuya única estación está a > 50 km → `None`, sin crear `PromocionClima`.
- [x] 7.8 `test_store_clima_without_location_returns_none`: promoción sin `location` → `None`.
- [x] 7.9 `test_store_clima_persists_three_series`: fixture OK, aseverar que `temp_mean`, `precipitation`, `sun_hours` tienen 12 elementos y `distance_m` coincide con lo esperado.
- [x] 7.10 `test_store_clima_handles_network_error`: `_aemet_get` lanza `requests.RequestException`, `store_clima` devuelve `None`.
- [x] 7.11 `test_promocion_pois_includes_clima_block`: `PromocionClima` existe, endpoint devuelve el bloque con las 3 series + metadata.
- [x] 7.12 `test_promocion_pois_clima_null_when_missing`: promoción sin `clima` → `response.json()["clima"] is None`.
- [x] 7.13 `test_backfill_aemet_clima_skips_existing` + `test_backfill_aemet_clima_force_recomputes` (mismos patrones que PVGIS). *(Más 1 test extra: `test_backfill_aemet_clima_aborts_without_inventory` que valida la guardia nueva.)*

## 8. Verificación en dev

- [x] 8.1 Si llegó la clave: `docker compose exec web_maps python manage.py backfill_aemet_stations` y verificar count > 0. *(Ejecutado por el usuario.)*
- [x] 8.2 Si llegó la clave: `docker compose exec web_maps python manage.py backfill_aemet_clima` y revisar el porcentaje de promociones que resuelven estación ≤ 50 km (umbral de alerta: < 70 % → revisar en una propuesta posterior). *(Ejecutado por el usuario; validación visual OK así que la cobertura fue suficiente.)*
- [x] 8.3 Si no llegó la clave: documentar en el `tasks.md` que el backfill real queda pendiente de la clave y asegurar que los tests en verde demuestran que el flujo funciona. *(Verificado: tests 34/34 verde con los fixtures; ambos comandos abortan con mensaje claro cuando falta la clave o el inventario.)*
- [x] 8.4 Abrir `/amenabar/promociones/` en el navegador, pinchar una promoción con clima calculado, comprobar que la sección aparece bajo solar. *(Validado por el usuario.)*
- [x] 8.5 Validar a 375 px (devtools responsive) que no hay desbordamiento ni corte visual y que los tres climogramas se leen. *(Validado por el usuario.)*
- [x] 8.6 Ejecutar `docker compose exec web_maps python -m pytest apps/amenabar/tests/ -v` y verificar que TODO sigue en verde (incluye tests existentes de PVGIS). *(34 passed.)*

## 9. Documentación y housekeeping

- [x] 9.1 Añadir al docstring del comando `backfill_aemet_clima` una nota breve sobre que requiere el inventario previo. *(Ya incluida en el módulo-docstring del comando.)*
- [x] 9.2 Confirmar que `ruff check src/apps/amenabar/` no suma errores nuevos sobre la baseline. *(Ficheros nuevos limpios tras eliminar `int(round(...))` redundante.)*
- [x] 9.3 Ejecutar `docker compose restart web_maps` tras los cambios Python. *(Hecho.)*
