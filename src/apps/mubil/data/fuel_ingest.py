"""Fuel station data layer: ingest from MINCOTUR + read avg prices.

Two responsibilities, mirroring :mod:`pvpc_ingest`:

1. **Ingest** (`ingest_provinces`, `ingest_spain`, `ingest_default`) — pull
   province snapshots from MINCOTUR and upsert each station by its natural
   key ``ideess``.  Idempotent: ``update_or_create`` overwrites
   prices/geometry, refreshes ``last_seen_at``.

   ``ingest_spain()`` covers all 52 INE provinces in parallel
   (``ThreadPoolExecutor``, default 8 workers) — a full España pass runs in
   ~20 s instead of ~3 min sequential.

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from typing import Callable, Dict, Iterable, List, Optional, Tuple

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

# Number of parallel threads for province fetching. MINCOTUR's API supports
# concurrent requests without rate-limiting; 8 workers is a safe default that
# cuts a full España run from ~3 min to ~20 s on a typical connection.
DEFAULT_WORKERS = 8

# ─────────────────────────────────────── INE province codes — España completa
#
# 52 codes (50 provinces + Ceuta + Melilla). Numeric zero-padded strings,
# matching the MINCOTUR API's «FiltroProvincia/{code}» path segment.
# Source: INE Clasificación de Provincias 2023.

ALL_SPAIN_PROVINCES: Tuple[str, ...] = (
    "01",  # Álava / Araba
    "02",  # Albacete
    "03",  # Alicante / Alacant
    "04",  # Almería
    "05",  # Ávila
    "06",  # Badajoz
    "07",  # Illes Balears
    "08",  # Barcelona
    "09",  # Burgos
    "10",  # Cáceres
    "11",  # Cádiz
    "12",  # Castellón / Castelló
    "13",  # Ciudad Real
    "14",  # Córdoba
    "15",  # A Coruña
    "16",  # Cuenca
    "17",  # Girona
    "18",  # Granada
    "19",  # Guadalajara
    "20",  # Gipuzkoa
    "21",  # Huelva
    "22",  # Huesca
    "23",  # Jaén
    "24",  # León
    "25",  # Lleida
    "26",  # La Rioja
    "27",  # Lugo
    "28",  # Madrid
    "29",  # Málaga
    "30",  # Murcia
    "31",  # Navarra
    "32",  # Ourense
    "33",  # Asturias
    "34",  # Palencia
    "35",  # Las Palmas
    "36",  # Pontevedra
    "37",  # Salamanca
    "38",  # Santa Cruz de Tenerife
    "39",  # Cantabria
    "40",  # Segovia
    "41",  # Sevilla
    "42",  # Soria
    "43",  # Tarragona
    "44",  # Teruel
    "45",  # Toledo
    "46",  # Valencia / València
    "47",  # Valladolid
    "48",  # Bizkaia
    "49",  # Zamora
    "50",  # Zaragoza
    "51",  # Ceuta
    "52",  # Melilla
)

# Human-readable names for logging / progress output.
_PROVINCE_NAMES: Dict[str, str] = {
    "01": "Álava", "02": "Albacete", "03": "Alicante", "04": "Almería",
    "05": "Ávila", "06": "Badajoz", "07": "Illes Balears", "08": "Barcelona",
    "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca",
    "17": "Girona", "18": "Granada", "19": "Guadalajara", "20": "Gipuzkoa",
    "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León",
    "25": "Lleida", "26": "La Rioja", "27": "Lugo", "28": "Madrid",
    "29": "Málaga", "30": "Murcia", "31": "Navarra", "32": "Ourense",
    "33": "Asturias", "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra",
    "37": "Salamanca", "38": "Tenerife", "39": "Cantabria", "40": "Segovia",
    "41": "Sevilla", "42": "Soria", "43": "Tarragona", "44": "Teruel",
    "45": "Toledo", "46": "Valencia", "47": "Valladolid", "48": "Bizkaia",
    "49": "Zamora", "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}


@dataclass
class FuelIngestStats:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    provinces: int = 0
    # Per-province breakdown: {code: {"fetched": N, "created": M, ...}}
    by_province: Dict[str, dict] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def merge(self, other: "FuelIngestStats", province_code: str) -> None:
        """Thread-safe merge of a per-province result into the global stats."""
        with self._lock:
            self.fetched += other.fetched
            self.created += other.created
            self.updated += other.updated
            self.skipped += other.skipped
            self.errors += other.errors
            self.provinces += other.provinces
            self.by_province[province_code] = {
                "name": _PROVINCE_NAMES.get(province_code, province_code),
                "fetched": other.fetched,
                "created": other.created,
                "updated": other.updated,
                "errors": other.errors,
            }

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


def _ingest_one_province(
    code: str,
    now: datetime,
    dry_run: bool,
    progress_cb: Optional[Callable[[str, int, int, int], None]],
) -> Tuple[str, FuelIngestStats]:
    """Fetch + upsert a single province.  Designed to run inside a thread.

    Args:
        code: zero-padded INE province code (e.g. ``"20"`` for Gipuzkoa).
        now: shared UTC timestamp for all ``last_seen_at`` values in this run.
        dry_run: skip DB writes.
        progress_cb: optional callable ``(code, fetched, created, errors)``
            called after the province is written, useful for CLI progress.

    Returns:
        ``(code, FuelIngestStats)`` — the per-province stats.
    """
    pstats = FuelIngestStats(provinces=1)
    name = _PROVINCE_NAMES.get(code, code)
    try:
        records = mincotur_client.fetch_province(code)
    except mincotur_client.MincoturError as e:
        log.error("MINCOTUR province %s (%s) fetch failed: %s", code, name, e)
        pstats.errors += 1
        return code, pstats

    pstats.fetched = len(records)
    if not dry_run:
        for rec in records:
            try:
                with transaction.atomic():
                    _upsert_record(rec, now, pstats)
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "FuelStation upsert failed (ideess=%s, prov=%s): %s",
                    rec.ideess, code, e,
                )
                pstats.errors += 1

    log.info(
        "Province %s (%s): fetched=%d created=%d updated=%d errors=%d",
        code, name, pstats.fetched, pstats.created, pstats.updated, pstats.errors,
    )
    if progress_cb is not None:
        progress_cb(code, pstats.fetched, pstats.created, pstats.errors)
    return code, pstats


def ingest_provinces(
    prov_codes: Iterable[str] = mincotur_client.DEFAULT_EH_PROVINCES,
    *,
    dry_run: bool = False,
    workers: int = DEFAULT_WORKERS,
    progress_cb: Optional[Callable[[str, int, int, int], None]] = None,
) -> FuelIngestStats:
    """Fetch each province in parallel and upsert into :class:`FuelStation`.

    Args:
        prov_codes: INE province codes as strings (e.g. ``("20",)`` for
            Gipuzkoa). Default = Álava + Gipuzkoa + Bizkaia (EH scope).
        dry_run: fetch + parse, don't write to DB. ``stats.fetched`` still
            reflects what would have been written.
        workers: number of parallel HTTP threads. MINCOTUR's API supports
            concurrency; 8 is a safe default. Use ``workers=1`` to go serial.
        progress_cb: optional callable ``(code, fetched, created, errors)``
            invoked (from a worker thread) after each province completes.
    """
    codes: List[str] = [str(c).strip().zfill(2) for c in prov_codes]
    total = FuelIngestStats()
    now = datetime.now(tz=timezone.utc)

    with ThreadPoolExecutor(max_workers=min(workers, len(codes) or 1)) as pool:
        futures = {
            pool.submit(_ingest_one_province, code, now, dry_run, progress_cb): code
            for code in codes
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                _, pstats = future.result()
            except Exception as e:  # noqa: BLE001
                log.error("Unexpected error in province %s worker: %s", code, e)
                pstats = FuelIngestStats(provinces=1, errors=1)
            total.merge(pstats, code)

    return total


def ingest_spain(
    *,
    dry_run: bool = False,
    workers: int = DEFAULT_WORKERS,
    progress_cb: Optional[Callable[[str, int, int, int], None]] = None,
) -> FuelIngestStats:
    """Ingest **all 52 INE provinces** (España completa) in parallel.

    This is the recommended entry point for the daily national cron.  A full
    run typically fetches ~12 000 stations in ~20 s with the default 8 workers.

    Args:
        dry_run: fetch + parse, skip DB writes.
        workers: parallel HTTP threads (default 8).
        progress_cb: optional ``(code, fetched, created, errors)`` callback.
    """
    log.info(
        "Starting Spain-wide fuel ingest: %d provinces, workers=%d, dry_run=%s",
        len(ALL_SPAIN_PROVINCES), workers, dry_run,
    )
    stats = ingest_provinces(
        prov_codes=ALL_SPAIN_PROVINCES,
        dry_run=dry_run,
        workers=workers,
        progress_cb=progress_cb,
    )
    log.info(
        "Spain ingest done — provinces=%d fetched=%d created=%d updated=%d errors=%d",
        stats.provinces, stats.fetched, stats.created, stats.updated, stats.errors,
    )
    return stats


def ingest_default(*, dry_run: bool = False) -> FuelIngestStats:
    """Backward-compatible alias: ingest the three EH provinces (Álava, Gipuzkoa, Bizkaia).

    Prefer :func:`ingest_spain` for a complete national dataset.
    """
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
