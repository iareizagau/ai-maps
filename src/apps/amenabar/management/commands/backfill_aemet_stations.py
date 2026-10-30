"""Sync AEMET station inventory into AemetStation.

Idempotent (uses update_or_create by idema). Dataset is stable; re-run
only when deploying or when AEMET publishes a new station.

Usage:
  docker compose exec web_maps python manage.py backfill_aemet_stations
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.amenabar.services_aemet import sync_stations


class Command(BaseCommand):
    help = "Sync the AEMET station inventory into AemetStation (idempotent)."

    def handle(self, *args, **opts):
        try:
            n = sync_stations()
        except Exception as e:
            self.stderr.write(f"ERR: {e}")
            return
        self.stdout.write(f"OK: {n} estaciones persistidas")
