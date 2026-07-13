"""OpenChargeMap (OCM) HTTP client.

Pure HTTP + JSON parsing for the public OpenChargeMap REST API. No DB writes
— those live in :mod:`charging_ingest`.

Auth: register at https://openchargemap.org/site/develop/api to get a free
key (instant). The key goes in the ``X-API-Key`` header *or* the ``key`` query
param; we use the header form because OCM logs the key into their analytics
when it travels as a query string.

Endpoint shape::

    GET  https://api.openchargemap.io/v3/poi/?
         countrycode=ES&
         boundingbox=(SW_lat,SW_lon),(NE_lat,NE_lon)&
         maxresults=1000&
         compact=true&
         verbose=false

The bounding box is the cheap way to keep payloads bounded — fetching the
full Spain catalog would return ~25k POIs each weekly tick.

PROPUESTA.md §3.1.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

log = logging.getLogger(__name__)


BASE_URL = "https://api.openchargemap.io/v3/poi/"
HTTP_TIMEOUT = 30
USER_AGENT = "mubil/0.1 (iareizagau@gmail.com)"

# Default Euskal Herria bounding box (SW corner, NE corner). Wide enough to
# cover Araba + Bizkaia + Gipuzkoa + Navarra + Iparralde, tight enough that
# OCM returns under ~1k POIs per call.
EH_BBOX_SW: tuple[float, float] = (42.30, -3.45)
EH_BBOX_NE: tuple[float, float] = (43.55, -1.30)

DEFAULT_MAX_RESULTS = 1000


class OpenChargeMapError(RuntimeError):
    """Raised on OCM HTTP / payload failures."""


@dataclass
class ChargingPOIRecord:
    """One charging POI from OpenChargeMap — parsed into Python-native types."""

    external_id: str  # "ocm-<ID>", stable across runs
    operator: str = ""
    address: str = ""
    municipality_name: str = ""
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    power_kw: Decimal | None = None
    connectors: list[dict] = field(default_factory=list)
    last_verified_at: datetime | None = None


# ─────────────────────────────────────────────── parsing helpers


def _to_decimal_kw(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: Any) -> datetime | None:
    """Parse OCM's ISO-8601 timestamps. Returns timezone-aware UTC or None."""
    if not value:
        return None
    s = str(value)
    # OCM returns ``2025-04-12T08:31:00Z`` and sometimes ``…+00:00``.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _parse_connectors(raw_connections: Any) -> tuple[list[dict], Decimal | None]:
    """Flatten OCM's ``Connections`` array into our compact form.

    Returns ``(connectors, max_power_kw)`` — the second value is what the
    advisor's "fast charging" filter ultimately runs on.
    """
    connectors: list[dict] = []
    max_kw: Decimal | None = None
    if not isinstance(raw_connections, list):
        return connectors, None
    for c in raw_connections:
        if not isinstance(c, dict):
            continue
        kw = _to_decimal_kw(c.get("PowerKW"))
        ctype = ""
        ct = c.get("ConnectionType")
        if isinstance(ct, dict):
            ctype = (ct.get("Title") or "").strip()
        connectors.append({"type": ctype, "kw": str(kw) if kw is not None else ""})
        if kw is not None and (max_kw is None or kw > max_kw):
            max_kw = kw
    return connectors, max_kw


def _parse_poi(raw: dict) -> ChargingPOIRecord | None:
    """Map one OCM POI dict to :class:`ChargingPOIRecord`. ``None`` if unusable.

    A POI is unusable if it has no ID or no coordinates — both of those break
    the downstream upsert (no natural key / no geometry).
    """
    poi_id = raw.get("ID")
    if poi_id is None:
        return None
    addr = raw.get("AddressInfo")
    if not isinstance(addr, dict):
        return None

    lat = _to_float(addr.get("Latitude"))
    lon = _to_float(addr.get("Longitude"))
    if lat is None or lon is None:
        return None

    operator = ""
    op_info = raw.get("OperatorInfo")
    if isinstance(op_info, dict):
        operator = (op_info.get("Title") or "").strip()

    address_parts = [
        (addr.get("AddressLine1") or "").strip(),
        (addr.get("Town") or "").strip(),
    ]
    address = ", ".join(p for p in address_parts if p)

    connectors, max_kw = _parse_connectors(raw.get("Connections"))

    # OCM may verify a POI without updating its status, or vice versa — take
    # whichever is more recent so a stale-but-reverified station still passes
    # the freshness filter in queries.
    last_verified = _parse_iso8601(raw.get("DateLastVerified"))
    last_status = _parse_iso8601(raw.get("DateLastStatusUpdate"))
    last_seen = max((d for d in (last_verified, last_status) if d), default=None)

    return ChargingPOIRecord(
        external_id=f"ocm-{poi_id}",
        operator=operator,
        address=address,
        municipality_name=(addr.get("Town") or "").strip(),
        postal_code=(addr.get("Postcode") or "").strip(),
        latitude=lat,
        longitude=lon,
        power_kw=max_kw,
        connectors=connectors,
        last_verified_at=last_seen,
    )


# ─────────────────────────────────────────────── public API


def fetch_bbox(
    *,
    api_key: str,
    sw: tuple[float, float] = EH_BBOX_SW,
    ne: tuple[float, float] = EH_BBOX_NE,
    country_code: str = "ES",
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[ChargingPOIRecord]:
    """Fetch every charging POI inside the bounding box and parse it.

    Args:
        api_key: OCM API key. Empty string is rejected upfront with
            :class:`OpenChargeMapError` — a silent 401 is harder to debug than
            an explicit guard.
        sw, ne: bounding-box corners as (lat, lon). Defaults to Euskal Herria.
        country_code: ISO-3166 alpha-2. Defaults to Spain; pass ``""`` to
            drop the filter (useful for the French side of Iparralde).
        max_results: cap returned POIs (OCM hard-caps at ~5000).

    Raises:
        OpenChargeMapError: on missing key, HTTP failure, or non-JSON payload.
    """
    if not api_key:
        raise OpenChargeMapError(
            "OpenChargeMap API key missing — set OPENCHARGEMAP_API_KEY."
        )

    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "X-API-Key": api_key,
    }
    params = {
        "boundingbox": f"({sw[0]},{sw[1]}),({ne[0]},{ne[1]})",
        "maxresults": max_results,
        "compact": "true",
        "verbose": "false",
    }
    if country_code:
        params["countrycode"] = country_code

    try:
        r = requests.get(BASE_URL, headers=headers, params=params, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise OpenChargeMapError(f"OCM request failed: {e}") from e

    if r.status_code >= 400:
        raise OpenChargeMapError(f"OCM returned HTTP {r.status_code}: {r.text[:200]}")
    try:
        payload = r.json()
    except ValueError as e:
        raise OpenChargeMapError(f"OCM returned non-JSON: {e}") from e

    if not isinstance(payload, list):
        raise OpenChargeMapError(
            f"OCM payload was not a JSON array (got {type(payload).__name__})."
        )

    records: list[ChargingPOIRecord] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        rec = _parse_poi(raw)
        if rec is not None:
            records.append(rec)
    return records


def parse_payload(payload: Iterable[dict]) -> list[ChargingPOIRecord]:
    """Public wrapper around :func:`_parse_poi` for tests / offline fixtures."""
    records: list[ChargingPOIRecord] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        rec = _parse_poi(raw)
        if rec is not None:
            records.append(rec)
    return records
