"""ESIOS (Red Eléctrica de España) HTTP client.

Pure HTTP + JSON parsing. No DB writes — those live in `pvpc_ingest.py` so
this module can be reused for any ESIOS indicator (1001 PVPC, 600 demand,
1293 generación renovable, …) without coupling to a specific table.

Auth: token issued by REE via email to `consultasios@ree.es`, lives in
`settings.ESIOS_TOKEN`. Sent as `x-api-key` header.

PROPUESTA.md §3.1, §5.1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

log = logging.getLogger(__name__)


BASE_URL = "https://api.esios.ree.es"
HTTP_TIMEOUT = 30
USER_AGENT = "mubil/0.1 (iareizagau@gmail.com)"

# ESIOS indicator IDs we care about — extend as needed.
INDICATOR_PVPC = 1001          # PVPC 2.0TD horario (€/MWh)


class ESIOSError(RuntimeError):
    """Raised on ESIOS HTTP / payload failures."""


@dataclass
class ESIOSValue:
    """One hourly datapoint from an ESIOS indicator."""

    timestamp: datetime          # tz-aware UTC
    value: float                 # raw indicator value (units depend on indicator)
    geo_id: Optional[int] = None
    geo_name: str = ""


def _auth_token() -> str:
    token = settings.ESIOS_TOKEN
    if not token:
        raise ESIOSError(
            "ESIOS_TOKEN is not set — request one at consultasios@ree.es and "
            "put it in .env. See settings/base.py."
        )
    return token


def fetch_indicator(
    indicator_id: int,
    *,
    start: datetime,
    end: datetime,
    geo_ids: Optional[List[int]] = None,
) -> List[ESIOSValue]:
    """Fetch hourly values for an ESIOS indicator between `start` and `end`.

    Args:
        indicator_id: numeric ESIOS indicator (e.g. 1001 for PVPC).
        start: tz-aware datetime (UTC recommended).
        end:   tz-aware datetime (UTC recommended). Exclusive on hour granularity.
        geo_ids: optional filter (e.g. [8741] for "España peninsular").

    Returns:
        List of ESIOSValue, sorted by timestamp.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ESIOSError("start/end must be timezone-aware.")

    url = f"{BASE_URL}/indicators/{indicator_id}"
    params = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    if geo_ids:
        params["geo_ids[]"] = [str(g) for g in geo_ids]

    headers = {
        "Accept": "application/json; application/vnd.esios-api-v1+json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "x-api-key": _auth_token(),
    }

    r = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    if r.status_code == 401:
        raise ESIOSError("ESIOS rejected the token (401). Verify settings.ESIOS_TOKEN.")
    if r.status_code == 403:
        raise ESIOSError("ESIOS denied access (403). Token may lack permission for this indicator.")
    r.raise_for_status()
    try:
        payload = r.json()
    except ValueError as e:
        raise ESIOSError(f"ESIOS returned non-JSON: {e}") from e

    raw_values = (payload.get("indicator") or {}).get("values") or []
    parsed: List[ESIOSValue] = []
    for v in raw_values:
        ts_raw = v.get("datetime") or v.get("datetime_utc")
        if not ts_raw:
            continue
        ts = parse_datetime(ts_raw)
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        try:
            value = float(v["value"])
        except (KeyError, TypeError, ValueError):
            continue
        parsed.append(ESIOSValue(
            timestamp=ts,
            value=value,
            geo_id=v.get("geo_id"),
            geo_name=v.get("geo_name") or "",
        ))

    parsed.sort(key=lambda x: x.timestamp)
    return parsed
