## 1. Modelo y migración

- [x] 1.1 Añadir `SolarPotential` a `src/apps/amenabar/models.py` con `OneToOneField(Promocion, related_name="solar")`, campos `kwh_kwp_year` (Decimal 7,2), `monthly_json` (JSONField), `irradiation_year` (Decimal 8,2), `tilt_deg`, `azimuth_deg`, `system_loss_pct`, `pvgis_version`, `raw_json`, `created_at`, `updated_at` (vía `BaseModel`).
- [x] 1.2 Añadir `models.Index(fields=["kwh_kwp_year"])` en `Meta`.
- [x] 1.3 Generar migración con `docker compose exec web python manage.py makemigrations amenabar` (debe nombrarse `0003_solarpotential.py`).
- [x] 1.4 Registrar `SolarPotential` en `src/apps/amenabar/admin.py` como solo-lectura (lista: `promocion`, `kwh_kwp_year`, `updated_at`).
- [x] 1.5 Aplicar migración localmente (`docker compose exec web python manage.py migrate amenabar`) y verificar.

## 2. Servicio PVGIS

- [x] 2.1 Crear `src/apps/amenabar/services_pvgis.py` con constantes `PVGIS_URL`, `PVGIS_RATE_S = 1.0`, `PVGIS_DEFAULTS` (peakpower=1, loss=14, angle=30, aspect=0, pvtechchoice=crystSi, mountingplace=building, outputformat=json).
- [x] 2.2 Implementar `fetch_pvgis(lat, lon) -> dict` con `requests.get`, User-Agent del módulo `services`, timeout 30 s, `raise_for_status()`.
- [x] 2.3 Implementar `store_solar(promocion) -> SolarPotential | None`: devuelve `None` si `promocion.location` es None; captura excepciones de red/parseo con `logger.warning(...)` y devuelve `None`; en éxito hace `update_or_create` con los campos derivados.
- [x] 2.4 Reutilizar el `USER_AGENT` ya definido en `services.py` (importar) para mantener identificación consistente ante PVGIS.

## 3. Management command

- [x] 3.1 Crear `src/apps/amenabar/management/commands/backfill_pvgis.py`.
- [x] 3.2 Añadir flags `--force` (recomputa aunque exista `solar`) y `--slug` (restringe a una sola promoción).
- [x] 3.3 Iterar `Promocion.objects.filter(location__isnull=False)`, saltar si ya tiene `solar` y no `--force`, llamar `store_solar(p)`, imprimir `OK <slug>` o `ERR <slug>: <msg>`.
- [x] 3.4 Pausa `time.sleep(PVGIS_RATE_S)` entre promociones.

## 4. Endpoint `promocion_pois`

- [x] 4.1 En `src/apps/amenabar/views.py`, en `promocion_pois`, leer `solar = getattr(p, "solar", None)`.
- [x] 4.2 Añadir clave de nivel superior `"solar"` al `JsonResponse`: `{"kwh_kwp_year": float(solar.kwh_kwp_year), "monthly": solar.monthly_json}` si existe, `None` si no.
- [x] 4.3 Asegurar que el resto del contrato (`promocion`, `pois`, `nearest`) queda intacto.

## 5. Componente Cotton y plantilla

- [x] 5.1 Crear `src/templates/cotton/molecules/solar_card.html` con props `kwh_year` y `monthly` (lista de 12 floats).
- [x] 5.2 Renderizar número grande con unidad "kWh/kWp · año" (usar `{% load i18n %}` + `{% trans %}` para la etiqueta).
- [x] 5.3 Renderizar 12 `<rect>` SVG inline escaladas por `max(monthly)`, con altura total ~96 px y ancho adaptable 100% al contenedor; etiquetas de meses abreviadas.
- [x] 5.4 Añadir disclaimer breve traducible: "Estimación bajo orientación óptima (sur, 30°). Condiciones reales pueden variar.".
- [x] 5.5 Clases Tailwind base 375 px, variantes `sm/md/lg` solo para escalar arriba; verificar que no hay scroll horizontal a 375 px.
- [x] 5.6 En `src/templates/amenabar/promociones.html`, incluir el componente dentro del panel de detalle de la promoción, condicionado a que el bloque `solar` del JSON exista (lectura client-side desde el JS que ya consume `promocion_pois.json`). *(Panel es render JS-driven dentro de Leaflet control; añadido `_solarBlock()` en el script + CSS gemelo + componente Cotton como referencia canónica para futura reutilización en HTMX.)*
- [x] 5.7 Si se añaden nuevas clases arbitrarias/responsive, ejecutar `npm run build:css` (ver CLAUDE.md) y verificar que `static/css/app.css` las incluye. *(No se añaden clases Tailwind nuevas al panel JS — usa CSS puro en el bloque `<style>`. El Cotton molecule sí usa Tailwind existente.)*

## 6. Tests

- [x] 6.1 Crear fixture `src/apps/amenabar/tests/fixtures/pvgis_sample.json` con un recorte mínimo de respuesta real (12 valores mensuales + totales).
- [x] 6.2 Crear `src/apps/amenabar/tests/test_pvgis.py` con configuración `pytest.mark.django_db`.
- [x] 6.3 `test_fetch_pvgis_parses_monthly`: mockear `requests.get`, invocar `fetch_pvgis(43.3, -1.9)` y comprobar que devuelve el JSON esperado.
- [x] 6.4 `test_store_solar_idempotent`: crear `Promocion` con `location`, mockear `fetch_pvgis`, llamar `store_solar` dos veces, aseverar `SolarPotential.objects.filter(promocion=p).count() == 1`.
- [x] 6.5 `test_store_solar_without_location_returns_none`: `Promocion` sin `location`, `store_solar(p)` debe devolver `None` sin crear filas.
- [x] 6.6 `test_store_solar_handles_network_error`: `fetch_pvgis` levanta `requests.RequestException`, `store_solar` devuelve `None` y no crea fila.
- [x] 6.7 `test_promocion_pois_includes_solar_block`: crear promoción + `SolarPotential`, llamar al endpoint, comprobar `response.json()["solar"]["kwh_kwp_year"]` y `len(monthly) == 12`.
- [x] 6.8 `test_promocion_pois_null_when_missing`: promoción sin `SolarPotential`, `response.json()["solar"] is None`.
- [x] 6.9 `test_backfill_pvgis_skips_existing`: con una `Promocion` que ya tiene `SolarPotential`, ejecutar comando sin `--force`, verificar que no se llamó al fetch (patch de `fetch_pvgis` cuenta 0 llamadas).
- [x] 6.10 `test_backfill_pvgis_force_recomputes`: mismo setup, con `--force`, verificar 1 llamada y que el registro se actualizó.

## 7. Datos y verificación en dev

- [x] 7.1 Confirmar que al menos 3 promociones tienen `location` no nulo; si no, correr `scrape_amenabar_listado` + `geocode_promocion` previo. *(107 promociones ya geocodificadas.)*
- [x] 7.2 Ejecutar `docker compose exec web python manage.py backfill_pvgis` y verificar en logs al menos un `OK <slug>`. *(107/107 OK. Rangos observados: 1091–1607 kWh/kWp·año — coherente con el gradiente norte-sur de España.)*
- [ ] 7.3 Abrir `/amenabar/promociones/` en el navegador, pinchar un marker con solar calculado, comprobar que la tarjeta aparece con el número anual y 12 barras. *(Pendiente de validación visual del usuario; endpoint ya devuelve `solar.kwh_kwp_year` + 12 valores correctamente.)*
- [ ] 7.4 Validar a 375 px (devtools responsive mode) que no hay desbordamiento ni corte visual. *(Pendiente — requiere comprobación en navegador real.)*
- [x] 7.5 Ejecutar `docker compose exec web pytest apps/amenabar/tests/test_pvgis.py -v` y verificar verde. *(8/8 passed.)*

## 8. Documentación y housekeeping

- [x] 8.1 Añadir una línea al `README` de la app (si existe) o nota en el panel admin sobre el backfill a mano. *(No existe README de la app; nota añadida al propio comando `backfill_pvgis.py` como docstring con las 3 formas de uso.)*
- [x] 8.2 Confirmar que `ruff` pasa sobre los ficheros nuevos (`docker compose exec web ruff check src/apps/amenabar/`). *(Ficheros nuevos limpios; 5 errores RUF012 preexistentes en models.py/admin.py sin cambio.)*
- [x] 8.3 Ejecutar `docker compose restart web` tras los cambios Python (CLAUDE.md: autoreload off en dev). *(Hecho.)*
