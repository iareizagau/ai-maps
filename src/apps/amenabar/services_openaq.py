"""OpenAQ v3 — monitoring stations + latest readings for Spain.

Endpoint used: `GET /v3/locations?bbox=minLon,minLat,maxLon,maxLat`.
Each location row already includes a `sensors[]` list with `latest.value` and
`latest.datetime.utc`, so one call per page covers "stations + their latest
reading" without a second GET per station.

Auth: free `X-API-Key` header. Register at
https://explore.openaq.org/register. Rationale and shape in
openspec/changes/amenabar-openaq-air-quality/design.md.

Units: µg/m³ (micrograms per cubic metre).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.utils.dateparse import parse_datetime

from .models import AirQualityStation
from .services import USER_AGENT

logger = logging.getLogger(__name__)

OPENAQ_BASE = "https://api.openaq.org/v3"
OPENAQ_RATE_S = 0.5
OPENAQ_PAGE_LIMIT = 1000
# minLon, minLat, maxLon, maxLat
OPENAQ_BBOX_SPAIN: tuple[float, float, float, float] = (-10.0, 35.0, 5.0, 44.0)
TRACKED_PARAMS: tuple[str, ...] = ("pm25", "pm10", "no2", "o3")


def _bbox_param(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(f"{v:.4f}" for v in bbox)


def fetch_openaq_locations_page(bbox: tuple[float, float, float, float], page: int) -> dict:
    """One page of /v3/locations. Raises on HTTP errors or missing key."""
    key = settings.OPENAQ_API_KEY
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is empty")
    resp = requests.get(
        f"{OPENAQ_BASE}/locations",
        params={
            "bbox": _bbox_param(bbox),
            "limit": OPENAQ_PAGE_LIMIT,
            "page": page,
        },
        headers={
            "User-Agent": USER_AGENT,
            "X-API-Key": key,
            "Accept": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_latest(sensors: list[dict], parameter: str) -> tuple[Decimal | None, datetime | None]:
    """Return (value, datetime) for the sensor matching `parameter`, or (None, None)."""
    for s in sensors or []:
        pname = ((s.get("parameter") or {}).get("name") or "").lower()
        if pname != parameter:
            continue
        latest = s.get("latest") or {}
        raw_val = latest.get("value")
        raw_dt = (latest.get("datetime") or {}).get("utc")
        value: Decimal | None = None
        if raw_val is not None:
            try:
                value = Decimal(str(raw_val))
            except (InvalidOperation, TypeError, ValueError):
                value = None
        when = parse_datetime(raw_dt) if raw_dt else None
        return value, when
    return None, None


def _max_dt(dts: list[datetime | None]) -> datetime | None:
    non_null = [d for d in dts if d is not None]
    return max(non_null) if non_null else None


def sync_openaq_spain() -> int:
    """Pull all stations in the Spain bbox and persist them. Idempotent.

    Returns the count of stations persisted (ES only).
    """
    kept = 0
    page = 1
    while True:
        try:
            payload = fetch_openaq_locations_page(OPENAQ_BBOX_SPAIN, page)
        except requests.RequestException as e:
            logger.warning("OpenAQ page %s failed: %s", page, e)
            break
        results = payload.get("results") or []
        if not results:
            break
        for row in results:
            country_code = ((row.get("country") or {}).get("code") or "").upper()
            if country_code != "ES":
                continue
            openaq_id = str(row.get("id") or "").strip()
            if not openaq_id:
                continue
            coords = row.get("coordinates") or {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is None or lon is None:
                continue
            sensors = row.get("sensors") or []
            pm25, dt_pm25 = _extract_latest(sensors, "pm25")
            pm10, dt_pm10 = _extract_latest(sensors, "pm10")
            no2, dt_no2 = _extract_latest(sensors, "no2")
            o3, dt_o3 = _extract_latest(sensors, "o3")
            AirQualityStation.objects.update_or_create(
                openaq_id=openaq_id,
                defaults={
                    "name": (row.get("name") or "")[:200],
                    "city": (row.get("locality") or "")[:120],
                    "country": "ES",
                    "location": Point(float(lon), float(lat), srid=4326),
                    "pm25": pm25,
                    "pm10": pm10,
                    "no2": no2,
                    "o3": o3,
                    "measurements_at": _max_dt([dt_pm25, dt_pm10, dt_no2, dt_o3]),
                    "raw_json": row,
                },
            )
            kept += 1

        meta: dict[str, Any] = payload.get("meta") or {}
        found = meta.get("found")
        if isinstance(found, int) and page * OPENAQ_PAGE_LIMIT >= found:
            break
        if len(results) < OPENAQ_PAGE_LIMIT:
            break
        page += 1
        time.sleep(OPENAQ_RATE_S)
    return kept
