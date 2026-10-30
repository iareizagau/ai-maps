## 1. Settings y entorno

- [x] 1.1 Añadir `OPENAQ_API_KEY = env("OPENAQ_API_KEY", default="")` en `src/config/settings/base.py` (patrón ya usado por `AEMET_API_KEY`).
- [ ] 1.2 Añadir `OPENAQ_API_KEY` al `.env` local si llega la clave (depende del usuario — el clasificador de credenciales bloquea la escritura automática en `.env`).

## 2. Modelo y migración

- [x] 2.1 Añadir `AirQualityStation(BaseModel)` a `src/apps/amenabar/models.py`: `openaq_id` (CharField unique), `name`, `city` (blank), `country` (default `"ES"`), `location` (`PointField` 4326), `pm25` / `pm10` / `no2` / `o3` (DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)), `measurements_at` (DateTimeField nullable), `raw_json` (JSONField).
- [x] 2.2 En `Meta` añadir `indexes: ClassVar[list] = [gis_models.Index(fields=["location"])]` y `constraints: ClassVar[list] = [CheckConstraint(check=Q(country="ES"), name="aqs_country_es_only")]`.
- [x] 2.3 Generar migración con `docker compose exec web_maps python manage.py makemigrations amenabar` (nombrada `0005_airqualitystation.py`).
- [x] 2.4 Aplicar migración.
- [x] 2.5 Registrar `AirQualityStation` en `src/apps/amenabar/admin.py` como solo-lectura (`list_display`: `openaq_id`, `name`, `city`, `pm25`, `measurements_at`; `search_fields`: `openaq_id`, `name`, `city`; `has_add_permission` → False).

## 3. Servicio OpenAQ

- [x] 3.1 Crear `src/apps/amenabar/services_openaq.py` con `OPENAQ_BASE = "https://api.openaq.org/v3"`, `OPENAQ_RATE_S = 0.5`, `OPENAQ_PAGE_LIMIT = 1000`, `OPENAQ_BBOX_SPAIN = (-10.0, 35.0, 5.0, 44.0)` y constantes `TRACKED_PARAMS = ("pm25", "pm10", "no2", "o3")`.
- [x] 3.2 Implementar `fetch_openaq_locations_page(bbox, page) -> dict`: `GET /v3/locations` con `X-API-Key` header, params `bbox` (minLon,minLat,maxLon,maxLat), `limit`, `page`. Timeout 30 s. Reutilizar `USER_AGENT` de `services.py`.
- [x] 3.3 Implementar helper `_extract_latest(sensors, parameter) -> tuple[Decimal | None, datetime | None]` que recorra `sensors[]` y devuelva la lectura más reciente para `parameter.name == parameter` leyendo `latest.value` / `latest.datetime.utc`.
- [x] 3.4 Implementar `sync_openaq_spain() -> int`: itera páginas del bbox España, filtra `country.code == "ES"`, hace `update_or_create(openaq_id=…, defaults={…})` con nombre, ciudad (`locality`), location (`Point(lon, lat)`), las 4 lecturas y `measurements_at = max()` de los timestamps presentes. Devuelve nº total persistido. Rate-limit entre páginas. Clave vacía → `raise RuntimeError("OPENAQ_API_KEY is empty")`.
- [x] 3.5 Documentar en docstring del módulo: endpoint v3, header, unidades (µg/m³), que sólo persiste España y los 4 parámetros.

## 4. Management command

- [x] 4.1 Crear `src/apps/amenabar/management/commands/sync_openaq.py` con `help` descriptivo y flag `--force` (no cambia la lógica — `update_or_create` ya es idempotente — pero deja la opción semántica abierta).
- [x] 4.2 Capturar el `RuntimeError` de clave vacía y escribir mensaje humano a `stderr` (mismo patrón que `backfill_aemet_stations`).
- [x] 4.3 Imprimir `OK: N estaciones España persistidas`.

## 5. Endpoint HTTP

- [x] 5.1 En `src/apps/amenabar/views.py`, añadir vista `airquality(request)` que devuelve `JsonResponse({"stations": [...]})` con la lista completa de `AirQualityStation` (campo-a-campo: `id` = openaq_id, `name`, `city`, `lat`, `lon`, `pm25`, `pm10`, `no2`, `o3`, `measurements_at` en ISO 8601 o `None`).
- [x] 5.2 En `src/apps/amenabar/urls.py`, añadir `path("airquality.json", views.airquality, name="airquality")`.
- [x] 5.3 Verificar que `promocion_pois` no cambia su shape (no añadir aire al JSON por-promoción).

## 6. UI (Leaflet)

- [x] 6.1 En `src/templates/amenabar/promociones.html`, dentro del `<style>` añadir reglas para marcadores y leyenda. *(Añadidos `.amb-aq-legend` y `.amb-aq-popup`; el marcador es `L.circleMarker` con `fillColor` directo, no requiere clase CSS.)*
- [x] 6.2 En `_controlHTML()`, añadir nueva sección "Capas globales" con un único toggle `kind=global`, code `air`, label traducible "Calidad del aire", y la leyenda compacta inline debajo (sólo visible cuando el toggle está activo).
- [x] 6.3 En `_getLayer()`, atender `kind === 'global'` → devolver `this.airQualityLayer`.
- [x] 6.4 Inicializar `this.airQualityLayer = L.layerGroup()` en `initMap()` y `this.aqStations = null` como cache de sesión.
- [x] 6.5 En el handler `panel.addEventListener('change', ...)`, si `kind === 'global' && code === 'air'` y check es true: si `aqStations` es null, hacer `fetch('/amenabar/airquality.json')`, pintar; si falla, poner el toggle a false, log y abortar.
- [x] 6.6 Función `_paintAirQuality()` que itera `this.aqStations.stations`, crea `L.circleMarker([lat, lon], {radius: 7, fillColor: colorFor(pm25), weight: 1, color: '#fff', fillOpacity: 0.95})` y `.bindPopup(...)` con nombre, parámetros disponibles con valor y timestamp relativo ("hace 3 h"). Añadir todos al `this.airQualityLayer`.
- [x] 6.7 Función `colorFor(pm25)` con los 4 umbrales WHO 2021 (verde ≤ 12, amarillo ≤ 35, naranja ≤ 55, rojo > 55) y gris si null. *(Función `_colorForPm25`.)*
- [ ] 6.8 Verificar a 375 px que la nueva sección del control no provoca overflow horizontal. *(Pendiente de validación visual del usuario.)*

## 7. Tests

- [x] 7.1 Crear fixtures en `src/apps/amenabar/tests/fixtures/`: `openaq_locations_page1.json` (3 estaciones: 2 ES + 1 FR para probar el filtro) y `openaq_locations_page2.json` (1 estación más).
- [x] 7.2 Crear `src/apps/amenabar/tests/test_openaq.py` con fixture `db` por test. *(Patrón consistente con `test_pvgis.py` y `test_aemet.py`.)*
- [x] 7.3 `test_fetch_openaq_locations_page_parses_results`: mock de `requests.get`, verificar que devuelve el JSON tal cual y que incluye el header `X-API-Key`. *(Nombrado `test_fetch_openaq_locations_page_sends_api_key_header`.)*
- [x] 7.4 `test_sync_openaq_spain_filters_non_spain`: fixture con una estación FR; tras `sync_openaq_spain()`, aseverar que sólo hay estaciones ES en la BD.
- [x] 7.5 `test_sync_openaq_spain_persists_latest_readings`: comprobar que `pm25` y `measurements_at` quedan correctamente poblados.
- [x] 7.6 `test_sync_openaq_spain_idempotent`: ejecutar dos veces, aseverar que no se duplican filas.
- [x] 7.7 `test_sync_openaq_without_key_raises`: sin clave → `RuntimeError`.
- [x] 7.8 `test_country_check_constraint`: intentar `AirQualityStation.objects.create(country="FR", ...)` → `IntegrityError`.
- [x] 7.9 `test_airquality_endpoint_returns_stations`: sembrar 2 estaciones, llamar al endpoint, aseverar que devuelve `{"stations": [...]}` con shape correcto.
- [x] 7.10 `test_airquality_endpoint_empty_cache_returns_empty_list`: sin estaciones, el endpoint devuelve 200 y `{"stations": []}`.
- [x] 7.11 `test_promocion_pois_unchanged`: verificar que `promocion_pois` NO incluye clave `air_quality` ni similar (contrato previo intacto). *(También 2 tests extra: paginación y manejo de error de red.)*

## 8. Verificación en dev

- [ ] 8.1 Si llegó la clave: `docker compose exec web_maps python manage.py sync_openaq` y verificar que persiste > 100 estaciones. *(Pendiente — `OPENAQ_API_KEY` aún no en `.env`.)*
- [x] 8.2 Si no llegó la clave: documentar que el sync real queda pendiente; los tests en verde demuestran que el flujo funciona. *(46 passed; comando aborta limpio con "ERR: OPENAQ_API_KEY is empty"; endpoint responde `{"stations": []}` para cache vacío.)*
- [ ] 8.3 Abrir `/amenabar/promociones/` en el navegador, activar "Calidad del aire", comprobar que aparecen los puntos coloreados y que al pinchar uno sale el popup. *(Pendiente — depende de 8.1.)*
- [ ] 8.4 Validar a 375 px que la nueva sección del control no desborda, que la leyenda es legible y que el popup no se corta. *(Pendiente — depende de 8.1 / 8.3.)*
- [ ] 8.5 Desactivar el toggle y volver a activarlo: verificar que no se vuelve a llamar al endpoint (segunda activación instantánea). *(Pendiente — depende de 8.1 / 8.3.)*
- [x] 8.6 Ejecutar `docker compose exec web_maps python -m pytest apps/amenabar/tests/ -v` y verificar que todo sigue en verde (incluye PVGIS + AEMET + nuevos OpenAQ). *(46 passed.)*

## 9. Housekeeping

- [x] 9.1 Confirmar que `ruff check` sobre los ficheros nuevos pasa. *(All checks passed sobre services_openaq, sync_openaq, test_openaq, views, urls.)*
- [x] 9.2 `docker compose restart web_maps` tras cambios Python. *(Hecho — endpoint `/amenabar/airquality.json` ya responde.)*
