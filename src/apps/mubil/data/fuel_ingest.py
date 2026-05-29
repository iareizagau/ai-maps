"""Fuel station data layer: ingest from MINCOTUR + read avg prices.

Two responsibilities, mirroring :mod:`pvpc_ingest`:

1. **Ingest** (`ingest_provinces`, `ingest_default`) — pull province snapshots
   from MINCOTUR and upsert each station by its natural key ``ideess``.
   Idempotent: ``update_or_create`` overwrites prices/geometry, refreshes
   ``last_seen_at``.

2. **Queries** (`recent_avg_eur_l`, `current_price_eur_l`) — return the €/L
   average across the freshest snapshot. Used by ``advisor`` to replace the
   ``DEFAULT_GASOLINA_95_EUR_L`` / ``DEFAULT_GASOLEO_A_EUR_L`` constants in
   :mod:`price_defaults`. Falls back to those constants if the table is empty
   or every station is stale, so the advisor cannot crash on a missed run.

MINCOTUR refreshes ~daily (afternoon), so a freshness window of 48h is a
reasonable default: it lets one missed run self-heal on the next tick without
silently serving week-old prices if the cron has been dead.

PROPUESTA.md §3.1, §5.1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Optional

from django.contrib.gis.geos import Point
from django.db import transaction

from apps.mubil.data import mincotur_client
from apps.mubil.data.price_defaults import (
    DEFAULT_GASOLEO_A_EUR_L,
    DEFAULT_GASOLINA_95_EUR_L,
)
from apps.mubil.models import FuelStation

log = logging.getLogger(__name__)


# Default freshness window for queries. MINCOTUR updates ~daily; 48h means a
# single missed cron run still serves yesterday's prices instead of falling
# back to the static defaults.
DEFAULT_FRESHNESS_HOURS = 48


@dataclass
class FuelIngestStats:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    provinces: int = 0

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "provinces": self.provinces,
        }


# ─────────────────────────────────────────────── upsert


def _upsert_record(
    rec: mincotur_client.FuelStationRecord,
    now: datetime,
    stats: FuelIngestStats,
) -> None:
    """Insert or update one station. Natural key = ``ideess``."""
    geom = Point(float(rec.longitude), float(rec.latitude), srid=4326)
    # JSONField + Decimal don't compose by default — store as string with a
    # plain ``.`` decimal separator so round-trips are stable.
    prices_jsonable = {k: str(v) for k, v in rec.prices.items()}

    _obj, created = FuelStation.objects.update_or_create(
        ideess=rec.ideess,
        defaults={
            "brand": rec.brand,
            "address": rec.address,
            "municipality_name": rec.municipality_name,
            "postal_code": rec.postal_code,
            "geom": geom,
            "prices": prices_jsonable,
            "schedule": rec.schedule,
            "sale_type": rec.sale_type,
            "last_seen_at": now,
        },
    )
    if created:
        stats.created += 1
    else:
        stats.updated += 1


# ─────────────────────────────────────────────── public API — ingest


def ingest_provinces(
    prov_codes: Iterable[str] = mincotur_client.DEFAULT_EH_PROVINCES,
    *,
    dry_run: bool = False,
) -> FuelIngestStats:
    """Fetch each province and upsert into :class:`FuelStation`.

    Args:
        prov_codes: INE province codes as strings (e.g. ``("20",)`` for
            Gipuzkoa, default = Álava + Gipuzkoa + Bizkaia).
        dry_run: fetch + parse, don't write to DB. ``stats.fetched`` still
            reflects what would have been written.
    """
    stats = FuelIngestStats()
    now = datetime.now(tz=timezone.utc)

    for code in prov_codes:
        stats.provinces += 1
        try:
            records = mincotur_client.fetch_province(code)
        except mincotur_client.MincoturError as e:
            log.error("MINCOTUR province %s fetch failed: %s", code, e)
            stats.errors += 1
            continue

        stats.fetched += len(records)
        if dry_run:
            continue

        for rec in records:
            try:
                with transaction.atomic():
                    _upsert_record(rec, now, stats)
            except Exception as e:  # noqa: BLE001
                log.warning("FuelStation upsert failed (ideess=%s): %s", rec.ideess, e)
                stats.errors += 1

    return stats


def ingest_default(*, dry_run: bool = False) -> FuelIngestStats:
    """Convenience wrapper for the daily cron: ingest all EH provinces."""
    return ingest_provinces(
        prov_codes=mincotur_client.DEFAULT_EH_PROVINCES,
        dry_run=dry_run,
    )


# ─────────────────────────────────────────────── queries (advisor wiring)


def _avg_price_eur_l(
    qs,
    fuel_key: str,
) -> Optional[Decimal]:
    """Average ``prices[fuel_key]`` across a queryset, in €/L.

    JSON values are stored as strings (see :func:`_upsert_record`); we average
    Python-side because there is no SQL aggregate over a JSON scalar that
    keeps Decimal precision portably.
    """
    values = []
    for row in qs.values_list("prices", flat=True).iterator():
        if not isinstance(row, dict):
            continue
        raw = row.get(fuel_key)
        if raw is None or raw == "":
            continue
        try:
            values.append(Decimal(str(raw)))
        except Exception:  # noqa: BLE001
            continue
    if not values:
        return None
    return (sum(values) / Decimal(len(values))).quantize(Decimal("0.001"))


def recent_avg_eur_l(
    *,
    fuel_key: str,
    freshness_hours: int = DEFAULT_FRESHNESS_HOURS,
    postal_code: Optional[str] = None,
    municipality_name: Optional[str] = None,
) -> Optional[Decimal]:
    """Average €/L for ``fuel_key`` across stations seen in the last window.

    Args:
        fuel_key: one of :data:`mincotur_client.FUEL_KEY_MAP` keys
            (e.g. ``"gasolina_95_e5"``, ``"gasoleo_a"``).
        freshness_hours: ignore stations whose ``last_seen_at`` is older.
        postal_code / municipality_name: optional locality filters. If both
            are given, postal code wins (more specific).

    Returns:
        Decimal €/L rounded to 3 decimals, or ``None`` if no station has the
        fuel within the freshness window.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=freshness_hours)
    qs = FuelStation.objects.filter(last_seen_at__gte=cutoff)
    if postal_code:
        qs = qs.filter(postal_code=postal_code)
    elif municipality_name:
        qs = qs.filter(municipality_name__iexact=municipality_name)
    return _avg_price_eur_l(qs, fuel_key)


def current_price_eur_l(
    *,
    fuel_key: str,
    postal_code: Optional[str] = None,
) -> Decimal:
    """The €/L the advisor should use right now for ``fuel_key``.

    Resolution order:

    1. Average of stations matching ``postal_code`` in the freshness window.
    2. Province-level average (whatever is in ``FuelStation``).
    3. Static ``DEFAULT_*`` constant from :mod:`price_defaults`.

    Falling back is critical — the advisor must keep producing numbers even if
    the cron is dead or MINCOTUR rejected the request.
    """
    if postal_code:
        local = recent_avg_eur_l(fuel_key=fuel_key, postal_code=postal_code)
        if local is not None:
            return local

    province_avg = recent_avg_eur_l(fuel_key=fuel_key)
    if province_avg is not None:
        return province_avg

    log.warning(
        "Fuel %s has no fresh rows in the last %dh — falling back to default.",
        fuel_key, DEFAULT_FRESHNESS_HOURS,
    )
    return _default_for(fuel_key)


def _default_for(fuel_key: str) -> Decimal:
    if fuel_key == "gasoleo_a":
        return DEFAULT_GASOLEO_A_EUR_L
    # Default catch-all is gasolina 95 — Premium / 98 fall back to it too. The
    # advisor only differentiates diesel vs gasoline, so this is acceptable.
    return DEFAULT_GASOLINA_95_EUR_L
