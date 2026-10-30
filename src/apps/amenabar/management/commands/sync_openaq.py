"""Sync OpenAQ air-quality stations for Spain into AirQualityStation.

Idempotent (uses update_or_create by openaq_id). Dataset is small (~500
stations); re-run on deploy and whenever you want to refresh readings.

Usage:
  docker compose exec web_maps python manage.py sync_openaq
  docker compose exec web_maps python manage.py sync_openaq --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.amenabar.services_openaq import sync_openaq_spain


class Command(BaseCommand):
    help = "Sync OpenAQ air-quality stations (Spain) into AirQualityStation."

    def add_arguments(self, parser):
        # Kept for API symmetry with the AEMET/PVGIS commands; the sync is
        # already idempotent so --force doesn't change behaviour today.
        parser.add_argument("--force", action="store_true", help="Reserved; sync is idempotent.")

    def handle(self, *args, **opts):
        try:
            n = sync_openaq_spain()
        except RuntimeError as e:
            self.stderr.write(f"ERR: {e}")
            return
        except Exception as e:
            self.stderr.write(f"ERR: {e}")
            return
        self.stdout.write(f"OK: {n} estaciones España persistidas")
