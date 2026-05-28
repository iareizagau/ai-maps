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

from apps.mubil.data import pvpc_ingest

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
