"""Celery tasks hooked from n8n workflows (PROPUESTA.md §5.1, §17).

Cron suggestions (configure via django-celery-beat):
  - `ingest_pvpc_hourly` — hourly, ESIOS indicator 1001 with token.
  - `ingest_fuel_stations` — daily 06:00, MINCOTUR `FiltroProvincia/20`.
  - `ingest_charging_stations` — weekly, OpenData Euskadi + OpenChargeMap fallback.
  - `ingest_datos_gob_catalog` — weekly, datos.gob.es CKAN metadata for the `ask` corpus.
  - `ingest_mitma_od` — monthly, `pyspainmobility` Donostialdea last month.
  - `compute_demand_scores` — monthly, after MITMA + DGT ingest (mgmt command also runnable).
"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.mubil.data import charging_ingest, fuel_ingest, pvpc_ingest
from apps.mubil.plan import services as plan_services

log = logging.getLogger(__name__)


@shared_task(name="mubil.ingest_pvpc_hourly")
def ingest_pvpc_hourly(hours: int = 48) -> dict:
    """Pull the last `hours` hours of PVPC into EnergyPricePVPC.

    Defaults to 48h so a missed run self-heals on the next tick. ESIOS publishes
    next-day PVPC around 20:00 Madrid; this is picked up on the next hourly
    cron without any cursor tracking on our side.
    """
    stats = pvpc_ingest.ingest_recent_hours(hours=hours)
    log.info("ingest_pvpc_hourly stats=%s", stats.as_dict())
    return stats.as_dict()


@shared_task(name="mubil.ingest_fuel_stations")
def ingest_fuel_stations() -> dict:
    """Snapshot all EH fuel stations from MINCOTUR.

    Idempotent upsert by `ideess`; refreshes `last_seen_at` so the advisor's
    freshness filter can ignore province snapshots that stopped updating.
    MINCOTUR refreshes ~daily (afternoon) — a 06:30 Madrid cron picks up the
    previous day's snapshot reliably.
    """
    stats = fuel_ingest.ingest_default()
    log.info("ingest_fuel_stations stats=%s", stats.as_dict())
    return stats.as_dict()


@shared_task(name="mubil.compute_demand_scores")
def compute_demand_scores() -> dict:
    """Monthly recompute of `DemandHex` scores for the `plan` heatmap.

    Score is a pure function of (population proxy, corridor proxy, current
    charger density). Only the charger density changes meaningfully month
    to month, so a monthly cadence is enough — see
    `apps.mubil.plan.services` for the heuristic and PROPUESTA.md §3.4 for
    the weight rationale.
    """
    stats = plan_services.compute_demand_scores()
    log.info("compute_demand_scores stats=%s", stats.as_dict())
    return stats.as_dict()


@shared_task(name="mubil.ingest_charging_stations")
def ingest_charging_stations() -> dict:
    """Weekly OpenChargeMap refresh of EV charging POIs in the EH bbox.

    The MITECO CSV is one-shot on first deploy (`ingest_charging_stations`
    management command with `--source miteco`). This task only hits OCM —
    re-running the bundled CSV every week wastes I/O on an unchanging file.

    No-ops with a warning log if `OPENCHARGEMAP_API_KEY` is unset, so a
    missing-key state doesn't mark the task as failed in Celery beat.
    """
    stats = charging_ingest.ingest_default()
    log.info("ingest_charging_stations stats=%s", stats.as_dict())
    return stats.as_dict()
