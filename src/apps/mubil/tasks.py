"""Celery tasks hooked from n8n workflows (PROPUESTA.md §5.1, §17).

Cron suggestions (configure via django-celery-beat):
  - `ingest_fuel_stations` — daily 06:00, MINCOTUR `FiltroProvincia/20`.
  - `ingest_pvpc_hourly` — hourly, ESIOS indicator 1001 with token.
  - `ingest_charging_stations` — weekly, OpenData Euskadi + OpenChargeMap fallback.
  - `ingest_datos_gob_catalog` — weekly, datos.gob.es CKAN metadata for the `ask` corpus.
  - `ingest_mitma_od` — monthly, `pyspainmobility` Donostialdea last month.
  - `compute_demand_scores` — monthly, after MITMA + DGT ingest (mgmt command also runnable).

NOTE: no business logic implemented yet — see PROPUESTA.md §6 (MUST/MOCK split).
"""

# from celery import shared_task
#
# @shared_task
# def ingest_fuel_stations():
#     ...
