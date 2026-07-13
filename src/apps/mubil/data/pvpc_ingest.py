"""PVPC data layer: ingest from ESIOS + read avg prices for downstream callers.

Two responsibilities:

1. **Ingest** (`ingest_window`, `ingest_recent_hours`) — pull ESIOS indicator
   1001 and upsert into `EnergyPricePVPC`. Each row is one hour, classified
   into 2.0TD tariff (P1 punta / P2 llano / P3 valle) per the Spanish
   peninsular schedule. Idempotent via `update_or_create`.

2. **Queries** (`recent_avg_eur_kwh`, `current_price_eur_kwh`) — return the
   €/kWh average over a recent window. Used by `advisor` to replace the
   `DEFAULT_PVPC_*` constants in `price_defaults.py`. Falls back to those
   constants if the table is empty so the advisor cannot crash on a missed
   ingest run.

National holidays are not yet honoured for tariff classification (would need
a calendar source); on official holidays the real PVPC follows valle (P3)
all day. Mitigation: this will overstate P1/P2 prices on ~12 days/year.
Revisit if pitch demands holiday precision.

PROPUESTA.md §3.1, §5.1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Avg

from apps.mubil.data import esios_client
from apps.mubil.data.price_defaults import (
    DEFAULT_PVPC_EUR_KWH,
    DEFAULT_PVPC_VALLE_EUR_KWH,
)
from apps.mubil.models import EnergyPricePVPC

log = logging.getLogger(__name__)


PENINSULA_TZ = ZoneInfo("Europe/Madrid")
# ESIOS geo_id for "España peninsular" (mainland PVPC; Canarias/Ceuta/Melilla differ).
PENINSULA_GEO_ID = 8741


# ---------------------------------------------------------------- 2.0TD tariff

# Hour ranges are half-open: [start, end). Reference:
# https://www.cnmc.es/ambitos-de-actuacion/energia/mercado-electrico#peajes-y-cargos
_P1_HOURS = set(range(10, 14)) | set(range(18, 22))  # 10–14, 18–22
_P2_HOURS = (
    set(range(8, 10)) | set(range(14, 18)) | set(range(22, 24))
)  # 8–10, 14–18, 22–24
# everything else is P3 (0–8 + all weekend hours)


def classify_tariff(ts_utc: datetime) -> str:
    """Return '2.0TD_P1' / '_P2' / '_P3' for a given UTC timestamp.

    Conversion to Madrid local time matters: the regulation is defined in
    local hours, and the DST transitions are honoured.
    """
    local = ts_utc.astimezone(PENINSULA_TZ)
    weekday = local.weekday()  # 0=Mon … 6=Sun
    if weekday >= 5:  # Sat/Sun → P3 all day
        return EnergyPricePVPC.Tariff.P3
    hour = local.hour
    if hour in _P1_HOURS:
        return EnergyPricePVPC.Tariff.P1
    if hour in _P2_HOURS:
        return EnergyPricePVPC.Tariff.P2
    return EnergyPricePVPC.Tariff.P3


# ---------------------------------------------------------------- stats


@dataclass
class PVPCIngestStats:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }


# ---------------------------------------------------------------- upsert


def _upsert_value(value: esios_client.ESIOSValue, stats: PVPCIngestStats) -> None:
    """Insert or update one hour. Idempotent: same (timestamp, tariff) wins."""
    tariff = classify_tariff(value.timestamp)
    price_mwh = Decimal(str(value.value)).quantize(Decimal("0.001"))

    obj, created = EnergyPricePVPC.objects.update_or_create(
        timestamp=value.timestamp,
        tariff=tariff,
        defaults={"price_eur_mwh": price_mwh},
    )
    if created:
        stats.created += 1
    else:
        stats.updated += 1


# ---------------------------------------------------------------- public API


def ingest_window(
    *,
    start: datetime,
    end: datetime,
    geo_id: int = PENINSULA_GEO_ID,
    dry_run: bool = False,
) -> PVPCIngestStats:
    """Fetch PVPC indicator 1001 between `start` and `end` and upsert each hour.

    Args:
        start: tz-aware datetime (inclusive).
        end:   tz-aware datetime (exclusive on hour granularity per ESIOS).
        geo_id: ESIOS geo filter; default = mainland Spain.
        dry_run: fetch + parse + classify, don't write to DB.
    """
    stats = PVPCIngestStats()
    try:
        values = esios_client.fetch_indicator(
            esios_client.INDICATOR_PVPC,
            start=start,
            end=end,
            geo_ids=[geo_id],
        )
    except esios_client.ESIOSError as e:
        log.error("ESIOS fetch failed: %s", e)
        stats.errors += 1
        return stats

    stats.fetched = len(values)

    if dry_run:
        return stats

    for v in values:
        try:
            _upsert_value(v, stats)
        except Exception as e:
            log.warning("PVPC upsert failed at %s: %s", v.timestamp.isoformat(), e)
            stats.errors += 1

    return stats


def ingest_recent_hours(hours: int = 48, *, dry_run: bool = False) -> PVPCIngestStats:
    """Convenience wrapper for the hourly cron: pull the last `hours` hours.

    48h default = current day + previous day. ESIOS publishes the next day's
    PVPC around 20:00 Madrid time, so an hourly cron will eventually pick it
    up without us needing to track "is tomorrow already there".
    """
    end = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    return ingest_window(start=start, end=end, dry_run=dry_run)


# ---------------------------------------------------------------- queries

DEFAULT_AVG_WINDOW_DAYS = 30


def recent_avg_eur_kwh(
    *,
    tariff: str | None = None,
    window_days: int = DEFAULT_AVG_WINDOW_DAYS,
) -> Decimal | None:
    """Average PVPC over the recent window, in €/kWh.

    Args:
        tariff: filter to one of EnergyPricePVPC.Tariff (e.g. P3 for valle).
                None = blend all hours (unweighted average across rows).
        window_days: how far back to look (default 30d).

    Returns:
        Decimal €/kWh, or `None` if no rows in the window. ESIOS publishes
        €/MWh; this divides by 1000.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=window_days)
    qs = EnergyPricePVPC.objects.filter(timestamp__gte=cutoff)
    if tariff is not None:
        qs = qs.filter(tariff=tariff)
    agg = qs.aggregate(avg=Avg("price_eur_mwh"))
    avg_mwh = agg.get("avg")
    if avg_mwh is None:
        return None
    return (Decimal(avg_mwh) / Decimal("1000")).quantize(Decimal("0.0001"))


def current_price_eur_kwh(*, night_charging: bool) -> Decimal:
    """The €/kWh the advisor should use right now.

    - `night_charging=True`  → average over valle (P3) in the recent window.
    - `night_charging=False` → blended average across all hours in the window.

    Falls back to the `DEFAULT_PVPC_*` constants in `price_defaults.py` if the
    `EnergyPricePVPC` table has no rows in the window — the advisor must not
    crash because the cron missed a run.
    """
    if night_charging:
        avg = recent_avg_eur_kwh(tariff=EnergyPricePVPC.Tariff.P3)
        if avg is not None:
            return avg
        log.warning(
            "PVPC valle empty in last %dd — falling back to default.",
            DEFAULT_AVG_WINDOW_DAYS,
        )
        return DEFAULT_PVPC_VALLE_EUR_KWH

    avg = recent_avg_eur_kwh(tariff=None)
    if avg is not None:
        return avg
    log.warning(
        "PVPC blended empty in last %dd — falling back to default.",
        DEFAULT_AVG_WINDOW_DAYS,
    )
    return DEFAULT_PVPC_EUR_KWH
