# Plan técnico — Fotovoltaico, Clima y Ruido/Aire

Plan detallado de implementación para las tres ideas elegidas de
[`IDEAS.md`](IDEAS.md):

- **#3 PVGIS** — mínimo viable (kWh/kWp año + barra mensual). Listo para
  codificar.
- **#4 Clima AEMET** — climograma mensual (Tª / precipitación / sol). Listo
  para codificar.
- **#9 Ruido + Aire** — spike corto. Decisión final tras ver #3 y #4 LIVE.

Las dos primeras comparten patrón: **ingest externo → tabla cacheada →
tarjeta en la ficha** servida por el endpoint existente
[`promocion_pois`](../../src/apps/amenabar/views.py#L85). No se añade stack:
`requests`, PostGIS, Celery, Django-cotton y Leaflet ya están.

Orden de ataque recomendado:

1. **#3 PVGIS** (~2 días) — base: aprende el patrón nuevo (migración + ingest
   + render en ficha) con una API sin clave y rápida.
2. **#4 AEMET** (~2–3 días) — repite patrón con la indirección propia de
   AEMET (2 GETs) y la selección de estación por proximidad.
3. **Decisión #9** — con #3 y #4 LIVE podemos ver si vale la pena añadir
   overlay de ruido/aire o pasar a otra idea del catálogo.

---

## 1 · PVGIS — potencial fotovoltaico (MVP)

### 1.1 Objetivo

Para cada `Promocion` con `location`, mostrar:

- **Un número grande**: `kWh/kWp · año`.
- **Una barra mensual** de 12 valores (`kWh/kWp · mes`).

Sin ahorro €, sin amortización — eso lo decidimos tras validar la UX.

### 1.2 API

Endpoint: `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`

Params fijos (los dejamos duros en código, luego los parametrizamos):

| param | valor | nota |
|---|---|---|
| `lat`, `lon` | de `promocion.location` | WGS84 |
| `peakpower` | `1` | 1 kWp → output = kWh/kWp directo |
| `loss` | `14` | pérdidas de sistema estándar |
| `angle` | `30` | inclinación óptima aproximada ES |
| `aspect` | `0` | sur (acimut 0° PVGIS) |
| `pvtechchoice` | `crystSi` | silicio cristalino |
| `mountingplace` | `building` | tejado edificado |
| `outputformat` | `json` | — |

Respuesta relevante:
- `outputs.monthly.fixed[]` → 12 entradas con `E_m` (kWh/mes).
- `outputs.totals.fixed.E_y` → total anual.
- `outputs.totals.fixed.H(i)_y` → irradiación anual plano inclinado.

### 1.3 Modelo

Fichero nuevo [`src/apps/amenabar/models.py`](../../src/apps/amenabar/models.py)
(se añade al existente):

```python
class SolarPotential(BaseModel):
    promocion = models.OneToOneField(
        Promocion, on_delete=models.CASCADE, related_name="solar"
    )
    kwh_kwp_year = models.DecimalField(max_digits=7, decimal_places=2)
    monthly_json = models.JSONField(default=list)  # [E_m, …] 12 valores
    irradiation_year = models.DecimalField(max_digits=8, decimal_places=2)
    # Parámetros usados — para poder reingestar si cambian supuestos
    tilt_deg = models.PositiveSmallIntegerField(default=30)
    azimuth_deg = models.SmallIntegerField(default=0)
    system_loss_pct = models.DecimalField(max_digits=4, decimal_places=1, default=14)
    pvgis_version = models.CharField(max_length=20, default="v5_3")
    raw_json = models.JSONField(default=dict)  # auditable, útil para debug

    class Meta:
        indexes = [models.Index(fields=["kwh_kwp_year"])]
```

**Decisión**: tabla separada 1:1 (no columnas en `Promocion`) para poder
reingestar sin tocar la tabla principal y conservar `raw_json` sin ensuciarla.

Migración: `0003_solarpotential.py` autogenerada con
`docker compose exec web python manage.py makemigrations amenabar`.

### 1.4 Service

Fichero nuevo [`src/apps/amenabar/services_pvgis.py`](../../src/apps/amenabar/services_pvgis.py)
(separado de `services.py` para no engordar un fichero que ya tiene 537
líneas):

```python
PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
PVGIS_RATE_S = 1.0  # cortesía — PVGIS no publica límite estricto
PVGIS_DEFAULTS = {
    "peakpower": 1,
    "loss": 14,
    "angle": 30,
    "aspect": 0,
    "pvtechchoice": "crystSi",
    "mountingplace": "building",
    "outputformat": "json",
}

def fetch_pvgis(lat: float, lon: float) -> dict | None:
    params = {**PVGIS_DEFAULTS, "lat": lat, "lon": lon}
    resp = requests.get(PVGIS_URL, params=params,
                        headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.json()

def store_solar(promocion: Promocion) -> SolarPotential | None:
    if not promocion.location:
        return None
    data = fetch_pvgis(promocion.location.y, promocion.location.x)
    totals = data["outputs"]["totals"]["fixed"]
    monthly = [round(m["E_m"], 2) for m in data["outputs"]["monthly"]["fixed"]]
    obj, _ = SolarPotential.objects.update_or_create(
        promocion=promocion,
        defaults={
            "kwh_kwp_year": totals["E_y"],
            "irradiation_year": totals["H(i)_y"],
            "monthly_json": monthly,
            "raw_json": data,
        },
    )
    return obj
```

**Error handling**: una promoción que falla **no debe bloquear** la ficha. El
view hace `getattr(promocion, 'solar', None)` y si es `None` oculta la
tarjeta. Logging con `logger.warning`, no `raise`.

### 1.5 Management command

Fichero nuevo
[`src/apps/amenabar/management/commands/backfill_pvgis.py`](../../src/apps/amenabar/management/commands/backfill_pvgis.py):

```python
class Command(BaseCommand):
    help = "Backfill SolarPotential for every Promocion with location."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Recompute even if a row exists")
        parser.add_argument("--slug", help="Only this promocion")

    def handle(self, *args, force=False, slug=None, **opts):
        qs = Promocion.objects.filter(location__isnull=False)
        if slug:
            qs = qs.filter(slug=slug)
        for p in qs:
            if not force and hasattr(p, "solar"):
                continue
            try:
                store_solar(p)
                self.stdout.write(f"OK  {p.slug}")
            except Exception as e:
                self.stdout.write(f"ERR {p.slug}: {e}")
            time.sleep(PVGIS_RATE_S)
```

### 1.6 Celery task (opcional, para producción)

```python
# tasks.py
@shared_task
def recompute_solar(promocion_id: int) -> None:
    p = Promocion.objects.filter(pk=promocion_id).first()
    if p and p.location:
        store_solar(p)
```

Enganchar vía `post_save` signal en `apps.py`: cuando una `Promocion` se
guarda con `location` por primera vez, lanzar `recompute_solar.delay(id)`.
Para MVP: skip, basta con el management command manual tras el scrape.

### 1.7 UI — tarjeta en la ficha

Hoy la ficha vive en el popup lateral de `promociones.html`, poblado por el
endpoint JSON [`promocion_pois`](../../src/apps/amenabar/views.py#L85).

Cambios:

1. **`views.promocion_pois`** — añadir bloque `solar`:

   ```python
   solar = getattr(p, "solar", None)
   return JsonResponse({
       "promocion": {...},
       "pois": [...],
       "nearest": nearest,
       "solar": {
           "kwh_kwp_year": float(solar.kwh_kwp_year),
           "monthly": solar.monthly_json,
       } if solar else None,
   })
   ```

2. **`promociones.html`** — en el panel de la promoción, añadir sección (si
   `solar` ≠ null):

   ```
   ┌───────────────────────────────────┐
   │ ☀️  Potencial solar                │
   │ 1 480 kWh/kWp · año               │
   │ ▁▃▅▇██▇▅▃▁  (12 barras SVG)       │
   └───────────────────────────────────┘
   ```

   Renderizado con SVG inline (12 `<rect>`), **mobile-first** (base 375 px).
   Las barras se escalan por `max(monthly)` para que febrero no quede plano
   comparado con julio.

3. **Componente Cotton nuevo** si cabe:
   [`src/templates/cotton/molecules/solar_card.html`](../../src/templates/cotton/molecules/solar_card.html).
   Props: `kwh_year`, `monthly` (lista). Reutilizable en #4 cambiando datos.

### 1.8 Tests

Fichero [`src/apps/amenabar/tests/test_pvgis.py`](../../src/apps/amenabar/tests/test_pvgis.py):

- `test_fetch_pvgis_parses_monthly` — mock `requests.get` con fixture JSON
  real (guardar un recorte en `tests/fixtures/pvgis_sample.json`).
- `test_store_solar_idempotent` — llamar `store_solar` dos veces, debe haber
  una sola fila.
- `test_promocion_pois_includes_solar` — crear `Promocion`+`SolarPotential`,
  pegarle al endpoint, verificar `response.json()['solar']`.
- `test_backfill_pvgis_skip_without_force` — comando no reescribe filas
  existentes salvo `--force`.

### 1.9 Variables de entorno

Ninguna. PVGIS no requiere clave.

### 1.10 Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| PVGIS devuelve 500 esporádicamente | Try/except por promoción, no abortar backfill |
| Latencia (p99 ~2 s) | Backfill offline en Celery; ficha ya trae `solar` cacheado |
| PVGIS v5.4 cambia schema | Guardamos `raw_json` + `pvgis_version` para poder reingestar |
| Comprador técnico pide sombras reales | Disclaimer "estimación teórica, orientación óptima" en el componente |

### 1.11 Entregable

- [ ] Modelo `SolarPotential` + migración.
- [ ] `services_pvgis.py` con `fetch_pvgis` y `store_solar`.
- [ ] Command `backfill_pvgis`.
- [ ] Endpoint `promocion_pois` incluye bloque `solar`.
- [ ] Componente Cotton `solar_card` renderizado en el panel.
- [ ] Tests: 4 unitarios + 1 end-to-end.
- [ ] `docker compose exec web python manage.py backfill_pvgis` ejecutado en
      dev con las promociones geocodificadas.

---

## 2 · AEMET — climograma mensual

### 2.1 Objetivo

Tarjeta en la ficha con 12 valores mensuales de:

- **Temperatura media** (°C)
- **Precipitación mensual** (mm)
- **Horas de sol mensuales** (h)

Usamos **valores climatológicos normales** (medias 1991–2020), no datos
diarios. Es lo que el comprador necesita y es un dataset estable.

### 2.2 Peculiaridad de AEMET OpenData

AEMET es un **servicio en dos pasos**:

1. GET al endpoint con `?api_key=…` → responde
   `{estado: 200, datos: "https://opendata.aemet.es/opendata/sh/…json", metadatos: "…"}`.
2. GET a la URL `datos` → ese sí trae el JSON real.

Hay que **tratar la primera llamada como un redirect manual**. Documentarlo
en el código.

### 2.3 Endpoints relevantes

| Qué | Path |
|---|---|
| Inventario de estaciones | `/api/valores/climatologicos/inventarioestaciones/todasestaciones` |
| Valores normales por estación | `/api/valores/climatologicos/normales/estacion/{idema}` |

### 2.4 Modelos

```python
class AemetStation(BaseModel):
    idema = models.CharField(max_length=10, unique=True)  # id oficial AEMET
    nombre = models.CharField(max_length=200)
    provincia = models.CharField(max_length=80, blank=True)
    altitud_m = models.IntegerField(null=True, blank=True)
    location = gis_models.PointField(srid=4326)
    raw_json = models.JSONField(default=dict)

    class Meta:
        indexes = [gis_models.Index(fields=["location"])]

class PromocionClima(BaseModel):
    promocion = models.OneToOneField(
        Promocion, on_delete=models.CASCADE, related_name="clima"
    )
    station = models.ForeignKey(AemetStation, on_delete=models.PROTECT)
    distance_m = models.PositiveIntegerField()  # a la estación elegida
    # 12 valores por serie
    temp_mean = models.JSONField(default=list)       # °C
    precipitation = models.JSONField(default=list)   # mm
    sun_hours = models.JSONField(default=list)       # h
    period_label = models.CharField(max_length=40, blank=True)  # "1991-2020"
    raw_json = models.JSONField(default=dict)
```

Migración única: `0004_aemetstation_promocionclima.py`.

### 2.5 Services

Fichero
[`src/apps/amenabar/services_aemet.py`](../../src/apps/amenabar/services_aemet.py):

```python
AEMET_BASE = "https://opendata.aemet.es/opendata/api"
AEMET_RATE_S = 1.0  # free tier

def _aemet_get(path: str) -> dict | list:
    """2-step indirection: first JSON points to real data URL."""
    key = settings.AEMET_API_KEY
    r1 = requests.get(f"{AEMET_BASE}{path}",
                      params={"api_key": key},
                      headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                      timeout=30)
    r1.raise_for_status()
    env = r1.json()
    if env.get("estado") != 200 or "datos" not in env:
        raise RuntimeError(f"AEMET envelope: {env}")
    r2 = requests.get(env["datos"], timeout=30)
    r2.raise_for_status()
    return r2.json()

def sync_stations() -> int: ...
def nearest_station(point) -> AemetStation | None: ...
def store_clima(promocion) -> PromocionClima | None: ...
```

**Selección de estación**: nearest `AemetStation` dentro de **50 km** del
`promocion.location` por `ST_Distance`. Si no hay ninguna, saltar.
Guardamos la `distance_m` para debug/UI.

**Normales por estación**: parseamos las 12 claves `E1`–`E12` o `mes` según
devuelva AEMET (verificarlo con un volcado real en el primer run); extraemos
`tm_mes` (temp media mes), `p_mes` (precipitación mes), `inso` (horas sol).
Los nombres exactos los confirmamos ejecutando una vez con `--debug`.

### 2.6 Management commands

- `backfill_aemet_stations` — primera carga del inventario. Idempotente.
- `backfill_aemet_clima --force --slug` — mismo patrón que `backfill_pvgis`.

Pensarlo en dos commands porque las estaciones es un dataset estable (≈850
estaciones toda España) que se refresca cada muchos meses; el clima por
promoción puede recomputarse al añadir nuevas promociones.

### 2.7 UI

En el panel: tarjeta con 3 mini-climogramas apilados verticalmente (mobile-
first). Reutilizar la molécula `solar_card` o crear `climate_card.html`:

```
🌡️ Clima  (est. Donostia-Igueldo · 2 km)
Tª media (°C)        ▂▂▃▄▅▆▇▇▆▅▄▃
Lluvia (mm)          ▇▆▅▃▂▁▁▂▃▅▇▇
Sol (h)              ▂▃▄▅▆▇▇▆▅▄▃▂
```

Expandir en el `promocion_pois.json`:

```python
clima = getattr(p, "clima", None)
"clima": {
    "station": clima.station.nombre,
    "distance_m": clima.distance_m,
    "temp_mean": clima.temp_mean,
    "precipitation": clima.precipitation,
    "sun_hours": clima.sun_hours,
    "period": clima.period_label,
} if clima else None,
```

### 2.8 Variables de entorno

```
# .env.example (añadir)
AEMET_API_KEY=
```

Y en [`src/config/settings/base.py`](../../src/config/settings/base.py)
siguiendo el patrón ya existente:

```python
AEMET_API_KEY = env("AEMET_API_KEY", default="")
```

**La clave se solicita en** `https://opendata.aemet.es/centrodedescargas/altaUsuario`.
Llega por email en ~2 min. Alta ya, aunque no empecemos la implementación
este mismo día.

### 2.9 Fallback

Si `AEMET_API_KEY` está vacío **o** la estación más cercana > 50 km,
`store_clima` devuelve `None` y la tarjeta no se muestra. Zero-crash.

En un futuro podríamos caer a **OpenWeatherMap** (ya hay
`OPENWEATHERMAP_API_KEY`), pero las normales climatológicas 1991-2020 son
superiores en calidad y gratis — no justifica el esfuerzo para el MVP.

### 2.10 Tests

- `test_aemet_two_step_envelope` — mock de los 2 GETs, verificar que
  seguimos el `datos` url.
- `test_sync_stations_idempotent`.
- `test_nearest_station_within_50km`.
- `test_store_clima_handles_missing_station`.
- `test_promocion_pois_includes_clima`.

### 2.11 Riesgos

| Riesgo | Mitigación |
|---|---|
| Clave AEMET tarda > 24 h | Pedirla hoy, empezar modelo + services mock mientras |
| Schema de "normales" varía entre estaciones | Logging + `raw_json` guardado; parseo defensivo |
| Estaciones AEMET lejos de pueblos pequeños | Umbral 50 km + tarjeta oculta si no hay |
| 2 GET → latencia doble | Backfill offline, nunca síncrono en request |

### 2.12 Entregable

- [ ] Modelos `AemetStation` + `PromocionClima`.
- [ ] `services_aemet.py`.
- [ ] Commands `backfill_aemet_stations` + `backfill_aemet_clima`.
- [ ] `AEMET_API_KEY` en settings + `.env.example`.
- [ ] Endpoint `promocion_pois` incluye bloque `clima`.
- [ ] Componente Cotton `climate_card`.
- [ ] Tests (5).
- [ ] Backfill ejecutado contra todas las promociones con `location`.

---

## 3 · Ruido + Aire — spike (decisión pendiente)

> Esta sección es un **boceto para decidir después**, no un plan ejecutable.
> La elección final (A, B o abandonar) la tomamos tras ver #3 y #4 LIVE para
> saber si la landing necesita más capas o ya tiene suficiente densidad.

### Opción A — "Ligera": OpenAQ puntos

- Capa Leaflet `L.layerGroup` con estaciones OpenAQ dentro de bbox de España
  (una query `GET /v3/locations` cada 24 h, cache en modelo
  `AirQualityStation`).
- Al clicar una estación, popup con último PM2.5 / NO₂ / O₃.
- Toggle en la UI para encender/apagar la capa.
- **Esfuerzo**: ~1 día. **Riesgo**: cero (API pública sin clave, sin raster).
- **Valor**: medio — es un overlay informativo global, no vinculado a cada
  promoción.

### Opción B — "Capa de ruido WMS MITECO"

- `L.tileLayer.wms` apuntando a `https://wms.mapama.gob.es/sig/` con las
  capas `Ruido/.../Lden` publicadas en el visor nacional.
- Sin backend propio: el WMS sirve los tiles.
- **Riesgo**: cobertura solo en aglomeraciones > 100 k hab y grandes ejes
  viarios. Para una promoción en un pueblo, la capa saldrá vacía.
- **Decisión previa**: antes de implementar, listar las promociones de
  Amenabar y comprobar manualmente que al menos 3 están dentro de un
  aglomerado del mapa de ruido. Si no, no vale la pena.

### Qué miraremos antes de decidir

- ¿La ficha con #3 + #4 ya está demasiado cargada? (si sí, abandonar #9).
- ¿Hay feedback de Amenabar pidiendo transparencia sobre entorno? (si sí,
  Opción A como mínimo).
- ¿Vale la pena invertir ~2 días más aquí o pasar a **#2 (isócronas)** o
  **#6 (hipoteca)** del catálogo? Mi intuición hoy: priorizar #2 antes que
  #9. Lo revisamos cuando toque.

### No añadir TiTiler

El plan original de `IDEAS.md` contemplaba TiTiler si queríamos servir
rasters de ruido. **Descartado para esta fase**: añade un servicio Docker
nuevo que no justifica el valor incremental de una capa de ruido con
cobertura parcial.

---

## 4 · Patrón común y convenciones del repo que seguimos

Un recordatorio para ambas features:

- **Settings dev** = `config.settings.local`. Para tests, el `pytest-django`
  por defecto ya lo coge. Ninguna variable nueva es obligatoria (ambas
  features degradan a "no se muestra la tarjeta").
- **Docker**: tras cualquier edición Python,
  `docker compose restart web` (CLAUDE.md:102 — autoreload apagado).
- **Tailwind**: cualquier clase nueva arbitraria o variante responsive
  requiere `npm run build:css`.
- **i18n**: strings nuevos (títulos de tarjetas, labels de unidades) en
  `gettext_lazy`. `LANGUAGE_CODE='eu'` renderiza decimales con coma; si
  pasamos `kwh_kwp_year` a una URL, aplicar `|unlocalize`.
- **Tests**: `docker compose exec web pytest apps/amenabar/tests/test_pvgis.py`.
  Los fixtures JSON reales se recortan al mínimo (una sola estación / una
  sola promoción) para no engordar el repo.
- **No cambiar la imagen de DB** (`timescale/timescaledb-ha:pg15`).
- **Mobile-first**: componentes nuevos con clases base 375 px, `sm/md/lg`
  solo para escalar arriba.

## 5 · Checklist pre-implementación

Antes de abrir el primer PR (idea #3):

- [ ] Pedir `AEMET_API_KEY` hoy para que esté lista cuando empecemos #4.
- [ ] Verificar que las promociones actuales tienen `location` suficientes
      para ver #3 en vivo (si no, correr `scrape_amenabar_listado` y
      `geocode_promocion` primero).
- [ ] Confirmar que `pytest` corre limpio con el estado actual del repo —
      base de referencia para los tests nuevos.
- [ ] Snapshot de la ficha actual (`promociones.html`) para comparar antes/
      después visualmente.
