"""AEMET OpenData — monthly climate normals 1991-2020.

Peculiarity of AEMET OpenData: every endpoint uses a 2-step indirection.
First GET to `/api/...` returns an envelope `{estado:200, datos: <signed url>,
metadatos: <signed url>}`. The second GET to `datos` fetches the real JSON.
The signed URLs expire fast (~1h), so we do both calls back-to-back in one
`_aemet_get(path)` helper.

Rationale: see openspec/changes/amenabar-aemet-clima/design.md.
API key: free, request at https://opendata.aemet.es/centrodedescargas/altaUsuario.

Units:
  temp_mean         — °C   (field `tm_mes` on normals row)
  precipitation     — mm   (field `p_mes`)
  sun_hours         — hours (field `inso`)
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from .models import AemetStation, Promocion, PromocionClima
from .services import USER_AGENT

logger = logging.getLogger(__name__)

AEMET_BASE = "https://opendata.aemet.es/opendata/api"
AEMET_RATE_S = 1.0
AEMET_MAX_STATION_DISTANCE_M = 50_000
AEMET_PERIOD = "1991-2020"

_COORD_RE = re.compile(r"^(\d{2})(\d{2})(\d{2})([NSEW])$")


def _parse_aemet_coord(raw: str) -> float | None:
    """AEMET serves lat/lon as DDMMSS + hemisphere, e.g. '431226N' or '000456W'."""
    m = _COORD_RE.match(raw.strip())
    if not m:
        return None
    deg, mins, secs, hemi = int(m[1]), int(m[2]), int(m[3]), m[4]
    val = deg + mins / 60.0 + secs / 3600.0
    if hemi in ("S", "W"):
        val = -val
    return val


def _aemet_get(path: str) -> Any:
    """Follow AEMET's 2-step envelope. Raises on network/HTTP errors."""
    key = settings.AEMET_API_KEY
    if not key:
        raise RuntimeError("AEMET_API_KEY is empty")
    r1 = requests.get(
        f"{AEMET_BASE}{path}",
        params={"api_key": key},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
    )
    r1.raise_for_status()
    env = r1.json()
    if env.get("estado") != 200 or "datos" not in env:
        raise RuntimeError(f"AEMET envelope: {env}")
    r2 = requests.get(env["datos"], timeout=30)
    r2.raise_for_status()
    return r2.json()


def sync_stations() -> int:
    """Replicate the AEMET station inventory locally. Idempotent.

    Returns the number of stations persisted.
    """
    data = _aemet_get("/valores/climatologicos/inventarioestaciones/todasestaciones")
    if not isinstance(data, list):
        raise RuntimeError(f"AEMET stations: unexpected payload type {type(data).__name__}")

    kept = 0
    for row in data:
        idema = (row.get("indicativo") or "").strip()
        if not idema:
            continue
        lat = _parse_aemet_coord(row.get("latitud") or "")
        lon = _parse_aemet_coord(row.get("longitud") or "")
        if lat is None or lon is None:
            logger.warning("AEMET station %s: bad coords %r / %r", idema, row.get("latitud"), row.get("longitud"))
            continue
        try:
            altitud = int(row.get("altitud")) if row.get("altitud") not in (None, "") else None
        except (TypeError, ValueError):
            altitud = None

        AemetStation.objects.update_or_create(
            idema=idema,
            defaults={
                "nombre": (row.get("nombre") or "")[:200],
                "provincia": (row.get("provincia") or "")[:80],
                "altitud_m": altitud,
                "location": Point(lon, lat, srid=4326),
                "raw_json": row,
            },
        )
        kept += 1
    return kept


def nearest_station(point: Point) -> AemetStation | None:
    """Nearest AemetStation within AEMET_MAX_STATION_DISTANCE_M, or None."""
    qs = AemetStation.objects.annotate(d_m=Distance("location", point)).order_by("d_m")
    s = qs.first()
    if not s:
        return None
    if s.d_m.m > AEMET_MAX_STATION_DISTANCE_M:
        return None
    return s


_MONTH_KEYS: tuple[str, ...] = (
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
)


def _parse_monthly_series(rows: list[dict], field: str) -> list[float | None]:
    """Extract 12 month values from an AEMET normals payload (ignores row 13 'annual').

    AEMET writes decimals with a comma; some fields can be strings like '-' when
    the station lacks that measurement.
    """
    by_month: dict[int, float | None] = {}
    for row in rows:
        mes = str(row.get("mes") or "").lstrip("0")
        if not mes or not mes.isdigit():
            continue
        m = int(mes)
        if m < 1 or m > 12:  # 13 is the annual summary
            continue
        raw = row.get(field)
        if raw in (None, "", "-"):
            by_month[m] = None
            continue
        try:
            by_month[m] = float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            by_month[m] = None
    return [by_month.get(i) for i in range(1, 13)]


def store_clima(promocion: Promocion) -> PromocionClima | None:
    """Fetch AEMET normals for the promocion's nearest station. None on any failure."""
    if not promocion.location:
        return None
    station = nearest_station(promocion.location)
    if not station:
        return None

    try:
        data = _aemet_get(f"/valores/climatologicos/normales/estacion/{station.idema}")
        if not isinstance(data, list):
            raise RuntimeError(f"AEMET normals: unexpected payload type {type(data).__name__}")
        temp = _parse_monthly_series(data, "tm_mes")
        precip = _parse_monthly_series(data, "p_mes")
        sun = _parse_monthly_series(data, "inso")
    except (requests.RequestException, RuntimeError, KeyError, ValueError, TypeError) as e:
        logger.warning("AEMET failed for %s: %s", promocion.slug, e)
        return None

    obj, _ = PromocionClima.objects.update_or_create(
        promocion=promocion,
        defaults={
            "station": station,
            "distance_m": round(station.d_m.m),
            "temp_mean": temp,
            "precipitation": precip,
            "sun_hours": sun,
            "period_label": AEMET_PERIOD,
            "raw_json": data,
        },
    )
    return obj
