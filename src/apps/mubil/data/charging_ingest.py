"""Charging-station data layer: ingest from MITECO CSV + OpenChargeMap.

Two responsibilities, mirroring :mod:`fuel_ingest`:

1. **Ingest** — two sources, both producing :class:`ChargingStation` rows:

   - :func:`ingest_miteco_csv` — one-shot import of the DGT/MITECO ``Puntos
     de Recarga`` snapshot (CSV in this repo). Coverage is global Spain;
     we filter to the EH provinces (Araba, Bizkaia, Gipuzkoa, Navarra) so
     the table stays focused on the advisor's use case.
   - :func:`ingest_openchargemap` — weekly refresh from OCM, scoped to the
     EH bounding box (see :mod:`openchargemap_client`).

2. **Convenience** — :func:`ingest_default` is what the cron hits. It runs
   OCM only (CSV is one-shot at first deploy), and short-circuits gracefully
   if no OCM API key is configured so a missing-key state never breaks the
   demo.

Natural key: ``(source, external_id)``. There is no UNIQUE constraint on the
model — cross-source dedup ("same physical station in MITECO and OCM") is a
post-MVP concern (PROPUESTA.md §3). Within one source the ingest is
idempotent via :func:`update_or_create`.

PROPUESTA.md §3.1, §5.1.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction
from django.db.models import Count

from apps.mubil.data import openchargemap_client
from apps.mubil.models import ChargingStation

log = logging.getLogger(__name__)


SOURCE_MITECO = "miteco"
SOURCE_OCM = "ocm"

# Provincia values used by MITECO in the CSV — uppercased, no accents.
EH_PROVINCES = frozenset({"BIZKAIA", "GIPUZKOA", "ARABA", "ALAVA", "NAVARRA"})

# The CSV ships under ``apps/mubil/data/PuntosCarga.csv``. Resolved relative to
# this file so it works in tests and in the container without env wiring.
DEFAULT_MITECO_CSV = Path(__file__).resolve().parent / "PuntosCarga.csv"


@dataclass
class ChargingIngestStats:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    source: str = ""

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "source": self.source,
        }


# ─────────────────────────────────────────────── MITECO CSV ingest


def _to_decimal_kw(value: object) -> Optional[Decimal]:
    """Parse ``"50.00"`` / ``"50,00"`` → Decimal. Empty/invalid → None."""
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _to_float_coord(value: object) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _strip_accents_upper(text: str) -> str:
    """ASCII-fold + uppercase, used to normalise provincia values from MITECO."""
    if not text:
        return ""
    table = str.maketrans("ÁÉÍÓÚÀÈÌÒÙÄËÏÖÜÑáéíóúàèìòùäëïöüñ",
                          "AEIOUAEIOUAEIOUNaeiouaeiouaeioun")
    return text.translate(table).upper().strip()


def ingest_miteco_csv(
    csv_path: Optional[Path] = None,
    *,
    eh_only: bool = True,
    dry_run: bool = False,
) -> ChargingIngestStats:
    """One-shot ingest of the MITECO ``PuntosCarga`` CSV.

    Args:
        csv_path: override the default snapshot path bundled with the repo.
        eh_only: filter to Euskal Herria provinces. Set ``False`` to load the
            whole Spain dataset (only useful for benchmarks).
        dry_run: parse + filter, do not write to DB. ``stats.fetched`` still
            reflects what would have been written.

    Returns:
        :class:`ChargingIngestStats` with per-row outcome counts.
    """
    path = Path(csv_path) if csv_path is not None else DEFAULT_MITECO_CSV
    stats = ChargingIngestStats(source=SOURCE_MITECO)
    now = datetime.now(tz=timezone.utc)

    if not path.is_file():
        log.error("MITECO CSV not found at %s", path)
        stats.errors += 1
        return stats

    # MITECO ships the file in ISO-8859-1 with CRLF line endings and ``|`` as
    # the separator. ``utf-8`` would explode on the first accented Provincia.
    with path.open("r", encoding="latin-1", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="|")
        for row in reader:
            outcome = _ingest_miteco_row(row, now, eh_only=eh_only, dry_run=dry_run)
            if outcome == "skipped":
                stats.skipped += 1
                continue
            stats.fetched += 1
            if dry_run:
                continue
            if outcome == "created":
                stats.created += 1
            elif outcome == "updated":
                stats.updated += 1
            elif outcome == "error":
                stats.errors += 1

    return stats


def _ingest_miteco_row(
    row: dict,
    now: datetime,
    *,
    eh_only: bool,
    dry_run: bool,
) -> str:
    """Process one CSV row. Returns one of: skipped/created/updated/error."""
    provincia = _strip_accents_upper(row.get("Provincia") or "")
    if eh_only and provincia not in EH_PROVINCES:
        return "skipped"

    external_id = (row.get("IdPuntoRecarga") or "").strip()
    if not external_id:
        return "skipped"

    lat = _to_float_coord(row.get("CoordenadaYDec"))
    lon = _to_float_coord(row.get("CoordenadaXDec"))
    if lat is None or lon is None:
        return "skipped"

    if dry_run:
        return "created"  # caller only uses this to bump `fetched`

    address_parts = [
        (row.get("Direccion") or "").strip(),
        (row.get("Localizacion") or "").strip(),
        (row.get("CodPostal") or "").strip(),
    ]
    address = ", ".join(p for p in address_parts if p)

    defaults = {
        "operator": (row.get("Operador") or "").strip()[:120],
        "address": address[:300],
        "geom": Point(lon, lat, srid=4326),
        "power_kw": _to_decimal_kw(row.get("PotenciaMaxima")),
        "connectors": [],  # CSV doesn't ship per-connector breakdown
        "last_seen_at": now,
    }

    try:
        with transaction.atomic():
            _obj, created = ChargingStation.objects.update_or_create(
                source=SOURCE_MITECO,
                external_id=external_id,
                defaults=defaults,
            )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "ChargingStation upsert failed (source=%s external_id=%s): %s",
            SOURCE_MITECO, external_id, e,
        )
        return "error"
    return "created" if created else "updated"


# ─────────────────────────────────────────────── OpenChargeMap ingest


def _upsert_ocm_record(
    rec: openchargemap_client.ChargingPOIRecord,
    now: datetime,
    stats: ChargingIngestStats,
) -> None:
    geom = Point(float(rec.longitude), float(rec.latitude), srid=4326)
    # If OCM gave us a verification date, prefer it as the freshness signal —
    # it reflects when a human last touched the record. Fall back to "now" so
    # the freshness filter still works for records OCM hasn't re-verified.
    last_seen = rec.last_verified_at or now

    defaults = {
        "operator": rec.operator[:120],
        "address": rec.address[:300],
        "geom": geom,
        "power_kw": rec.power_kw,
        "connectors": rec.connectors,
        "last_seen_at": last_seen,
    }
    try:
        with transaction.atomic():
            _obj, created = ChargingStation.objects.update_or_create(
                source=SOURCE_OCM,
                external_id=rec.external_id,
                defaults=defaults,
            )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "ChargingStation upsert failed (source=%s external_id=%s): %s",
            SOURCE_OCM, rec.external_id, e,
        )
        stats.errors += 1
        return
    if created:
        stats.created += 1
    else:
        stats.updated += 1


def ingest_openchargemap(
    *,
    api_key: Optional[str] = None,
    sw=openchargemap_client.EH_BBOX_SW,
    ne=openchargemap_client.EH_BBOX_NE,
    country_code: str = "ES",
    max_results: int = openchargemap_client.DEFAULT_MAX_RESULTS,
    dry_run: bool = False,
) -> ChargingIngestStats:
    """Fetch OCM POIs in the bounding box and upsert as ``source='ocm'``.

    Args:
        api_key: OCM API key. Falls back to ``settings.OPENCHARGEMAP_API_KEY``.
            If both are empty the ingest is a no-op and the stats reflect 0
            fetched / 0 errors — the cron is allowed to run without the key
            so we never crash a deploy on missing config.
        sw, ne, country_code, max_results: forwarded to
            :func:`openchargemap_client.fetch_bbox`.
        dry_run: fetch + parse, no DB writes.
    """
    stats = ChargingIngestStats(source=SOURCE_OCM)
    key = api_key if api_key is not None else getattr(settings, "OPENCHARGEMAP_API_KEY", "")
    if not key:
        log.warning(
            "OPENCHARGEMAP_API_KEY not configured — skipping OCM ingest. "
            "Set it in src/.env to enable weekly refresh."
        )
        return stats

    try:
        records = openchargemap_client.fetch_bbox(
            api_key=key,
            sw=sw,
            ne=ne,
            country_code=country_code,
            max_results=max_results,
        )
    except openchargemap_client.OpenChargeMapError as e:
        log.error("OCM fetch failed: %s", e)
        stats.errors += 1
        return stats

    stats.fetched = len(records)
    if dry_run:
        return stats

    now = datetime.now(tz=timezone.utc)
    for rec in records:
        _upsert_ocm_record(rec, now, stats)
    return stats


# ─────────────────────────────────────────────── cron entry point


def ingest_default(*, dry_run: bool = False) -> ChargingIngestStats:
    """Default cron payload: weekly OCM refresh of the EH bounding box.

    MITECO CSV is one-shot at first deploy (see :func:`ingest_miteco_csv`) —
    re-running it every week wastes I/O on a snapshot that hasn't changed.
    The CSV gets refreshed manually when DGT publishes a new ``PuntosCarga``
    drop (announced via datos.gob.es).
    """
    return ingest_openchargemap(dry_run=dry_run)


# ─────────────────────────────────────────────── queries (read side)


def count_by_source() -> dict:
    """Quick health check used by management commands and the admin."""
    out = {SOURCE_MITECO: 0, SOURCE_OCM: 0, "other": 0}
    for row in ChargingStation.objects.values("source").annotate(n=Count("id")):
        src = row["source"] or "other"
        bucket = src if src in out else "other"
        out[bucket] = out[bucket] + row["n"] if bucket == "other" else row["n"]
    return out


def iter_eh_sources() -> Iterable[str]:
    """Iterator over the source slugs we ingest. Useful for admin filters."""
    yield SOURCE_MITECO
    yield SOURCE_OCM
