"""IDAE catalog data layer: ingest into Vehicle + read for the advisor.

Responsibility split mirrors :mod:`fuel_ingest` / :mod:`pvpc_ingest`:

1. **Ingest** (`ingest_marca`, `ingest_full`) — fetch both `ciclo=elec` and
   `ciclo=wltp` from :mod:`idae_client`, merge by `idae_id`, and upsert into
   :class:`Vehicle`. Per-marca pagination keeps payloads bounded (avg ~85
   vehicles/marca vs 23,945 globally) and produces clearer progress output.

2. **Mapping** — IDAE doesn't publish DGT energy labels directly, but they
   are inferable from `Motorización` + `co2_g_km_min`: BEV/PHEV → '0'/'ECO',
   ICE/Diesel → 'C'/'B' depending on CO₂. The mapping is intentionally
   conservative; rows we can't classify go in with `dgt_label=''` rather
   than being mis-labeled.

This module does **not** delete stale rows — IDAE history is append-only by
design (a discontinued model stays in the database), and a hard reset would
strip out the hand-curated seed rows that have `idae_id=NULL`.

PROPUESTA.md §3.1.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from decimal import Decimal

from django.db import transaction

from apps.mubil.data import idae_client
from apps.mubil.models import Vehicle

log = logging.getLogger(__name__)


# Callback invocado tras cada marca con (marca, delta_stats, cumulative_stats).
# `delta` aísla lo aportado por esta marca para que el cliente pueda mostrar
# "78 nuevos en BMW" sin recalcular acumulados.
MarcaCallback = Callable[
    [idae_client.Marca, "IDAEIngestStats", "IDAEIngestStats"], None
]


# ─────────────────────────────────────────────── stats


@dataclass
class IDAEIngestStats:
    marcas_seen: int = 0
    fetched_elec: int = 0
    fetched_wltp: int = 0
    merged: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict:
        return {
            "marcas_seen": self.marcas_seen,
            "fetched_elec": self.fetched_elec,
            "fetched_wltp": self.fetched_wltp,
            "merged": self.merged,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }

    def __sub__(self, other: IDAEIngestStats) -> IDAEIngestStats:
        """Delta entre dos snapshots — útil para reportar lo aportado por una marca."""
        return IDAEIngestStats(
            marcas_seen=self.marcas_seen - other.marcas_seen,
            fetched_elec=self.fetched_elec - other.fetched_elec,
            fetched_wltp=self.fetched_wltp - other.fetched_wltp,
            merged=self.merged - other.merged,
            created=self.created - other.created,
            updated=self.updated - other.updated,
            skipped=self.skipped - other.skipped,
            errors=self.errors - other.errors,
        )


# ─────────────────────────────────────────────── dgt-label inference


def _infer_dgt_label(
    *,
    propulsion: str | None,
    co2_min: int | None,
) -> str:
    """Best-effort DGT environmental label from propulsion + CO₂ min.

    Reference: DGT distintivo ambiental table. The official assignment also
    factors in NOx and Euro standard, which IDAE doesn't expose — these are
    therefore approximations good enough for "filter by label" UX but not
    legally authoritative. Returns "" when uncertain.
    """
    if propulsion == Vehicle.Propulsion.BEV:
        return Vehicle.DGTLabel.CERO
    if propulsion == Vehicle.Propulsion.PHEV:
        # PHEVs need ≥40 km electric range for Cero. IDAE has range_wltp_km
        # but we don't pass it here; default ECO is the safe call.
        return Vehicle.DGTLabel.ECO
    if propulsion == Vehicle.Propulsion.HEV:
        return Vehicle.DGTLabel.ECO
    if propulsion in (Vehicle.Propulsion.CNG, Vehicle.Propulsion.LPG):
        return Vehicle.DGTLabel.ECO
    # ICE / Diesel — needs Euro standard, which IDAE doesn't expose. Leave
    # empty; users can filter by propulsion instead.
    return ""


# ─────────────────────────────────────────────── merge + upsert


def _merge_pair(
    elec: idae_client.IDAEElecRow | None,
    wltp: idae_client.IDAEWLTPRow | None,
) -> dict:
    """Build the kwargs dict for `Vehicle.objects.update_or_create`.

    The elec row is canonical for identification (make/model/propulsion/
    category) when present, because the wltp table has no Motorización
    column. The wltp row contributes combustion specs.
    """
    src = elec or wltp
    if src is None:
        return {}

    make = src.make
    model = src.model
    energy_class = src.energy_class

    propulsion = elec.propulsion if elec else None
    # Default to ICE for combustion-only rows when motorización is unknown —
    # ECO/HEV/Diesel rows will already have been classified via the elec pass.
    if propulsion is None and wltp is not None:
        propulsion = Vehicle.Propulsion.ICE

    co2_min = wltp.co2_g_km_min if wltp else None
    co2_max = wltp.co2_g_km_max if wltp else None
    # BEVs have 0 tailpipe emissions; IDAE leaves the wltp cell empty.
    if propulsion == Vehicle.Propulsion.BEV and co2_min is None:
        co2_min = 0
        co2_max = 0

    # Average min/max combustion consumption — the advisor only knows one l/100
    # number, so collapse the WLTP range to its midpoint.
    cons_l = None
    if (
        wltp
        and wltp.consumption_l_100km_min is not None
        and wltp.consumption_l_100km_max is not None
    ):
        cons_l = (
            (wltp.consumption_l_100km_min + wltp.consumption_l_100km_max) / Decimal("2")
        ).quantize(Decimal("0.01"))
    elif wltp and wltp.consumption_l_100km_max is not None:
        cons_l = wltp.consumption_l_100km_max

    defaults = {
        "make": make,
        "model": model,
        "year": 0,  # IDAE doesn't carry a release year per row. Updated below if found.
        "variant": "",
        "propulsion": propulsion or Vehicle.Propulsion.ICE,
        "energy_class": energy_class,
        "dgt_label": _infer_dgt_label(propulsion=propulsion, co2_min=co2_min),
        "category": elec.category if elec else "",
        "mtma_kg": elec.mtma_kg if elec else None,
        "battery_kwh": elec.battery_kwh if elec else None,
        "range_wltp_km": elec.range_wltp_km if elec else None,
        "consumption_kwh_100km": elec.consumption_kwh_100km if elec else None,
        "consumption_l_100km": cons_l,
        "co2_g_km_min": co2_min,
        "co2_g_km_max": co2_max,
        "source_url": f"https://coches.idae.es/base-datos/ficha/{src.idae_id}",
    }
    return defaults


def _upsert(defaults: dict, idae_id: int, stats: IDAEIngestStats) -> None:
    """Idempotent upsert keyed on idae_id."""
    try:
        with transaction.atomic():
            _obj, created = Vehicle.objects.update_or_create(
                idae_id=idae_id,
                defaults=defaults,
            )
        if created:
            stats.created += 1
        else:
            stats.updated += 1
    except Exception as e:
        log.warning("Vehicle upsert failed (idae_id=%s): %s", idae_id, e)
        stats.errors += 1


# ─────────────────────────────────────────────── public API


def ingest_marca(
    marca_id: int,
    *,
    session: idae_client.IDAESession | None = None,
    stats: IDAEIngestStats | None = None,
    dry_run: bool = False,
) -> IDAEIngestStats:
    """Ingest every vehicle for one IDAE `marca_id`.

    Both `ciclo=elec` and `ciclo=wltp` are paginated, merged by idae_id, and
    upserted. Caller can pass an existing :class:`IDAESession` to amortise
    the Laravel handshake across marcas.
    """
    stats = stats or IDAEIngestStats()
    session = session or idae_client.IDAESession()

    elec_by_id: dict[int, idae_client.IDAEElecRow] = {}
    wltp_by_id: dict[int, idae_client.IDAEWLTPRow] = {}

    try:
        for row in idae_client.iter_elec(session, marca_id=marca_id):
            elec_by_id[row.idae_id] = row
            stats.fetched_elec += 1
        for row in idae_client.iter_wltp(session, marca_id=marca_id):
            wltp_by_id[row.idae_id] = row
            stats.fetched_wltp += 1
    except idae_client.IDAEError as e:
        log.error("IDAE fetch failed for marca %s: %s", marca_id, e)
        stats.errors += 1
        return stats

    all_ids = set(elec_by_id) | set(wltp_by_id)
    stats.merged += len(all_ids)
    if dry_run:
        return stats

    for idae_id in all_ids:
        defaults = _merge_pair(elec_by_id.get(idae_id), wltp_by_id.get(idae_id))
        if not defaults:
            stats.skipped += 1
            continue
        _upsert(defaults, idae_id, stats)

    return stats


def ingest_full(
    *,
    only_marcas: Iterable[int] | None = None,
    throttle_s: float = idae_client.DEFAULT_THROTTLE_S,
    dry_run: bool = False,
    on_marcas_listed: Callable[[list[idae_client.Marca]], None] | None = None,
    on_marca_done: MarcaCallback | None = None,
) -> IDAEIngestStats:
    """Ingest the entire IDAE catalog, marca by marca.

    Args:
        only_marcas: if provided, restrict to these IDAE marca IDs. Useful
            for incremental ingests or smoke tests.
        throttle_s: seconds to sleep between requests (rate-limit guard).
        dry_run: parse + merge but don't write.
        on_marcas_listed: invocado una vez con la lista resuelta de marcas
            (ya filtrada por `only_marcas`) — permite al cliente mostrar el
            total antes de empezar.
        on_marca_done: invocado tras cada marca con (marca, delta, acumulado).
            El callback NO debería levantar; cualquier excepción se traga
            con log.warning para no abortar la ingesta global.
    """
    session = idae_client.IDAESession(throttle_s=throttle_s)
    marcas: list[idae_client.Marca] = session.marcas()

    if only_marcas is not None:
        wanted = set(only_marcas)
        marcas = [m for m in marcas if m.idae_id in wanted]

    if on_marcas_listed is not None:
        try:
            on_marcas_listed(marcas)
        except Exception as e:
            log.warning("on_marcas_listed callback failed: %s", e)

    stats = IDAEIngestStats()
    for marca in marcas:
        snapshot = replace(stats)  # copia inmutable previa a la marca
        stats.marcas_seen += 1
        log.info("IDAE ingest marca %s (id=%s)…", marca.name, marca.idae_id)
        ingest_marca(marca.idae_id, session=session, stats=stats, dry_run=dry_run)
        if on_marca_done is not None:
            try:
                on_marca_done(marca, stats - snapshot, stats)
            except Exception as e:
                log.warning("on_marca_done callback failed for %s: %s", marca.name, e)

    return stats
