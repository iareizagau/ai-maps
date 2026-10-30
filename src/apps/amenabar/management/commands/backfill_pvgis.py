"""Backfill SolarPotential for every Promocion with location.

Usage:
  docker compose exec web_maps python manage.py backfill_pvgis
  docker compose exec web_maps python manage.py backfill_pvgis --force
  docker compose exec web_maps python manage.py backfill_pvgis --slug aires-de-arganda
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.amenabar.models import Promocion
from apps.amenabar.services_pvgis import PVGIS_RATE_S, store_solar


class Command(BaseCommand):
    help = "Backfill PVGIS solar potential for Promocion rows with a location."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute even when a SolarPotential already exists.",
        )
        parser.add_argument(
            "--slug",
            help="Only this promocion (by slug).",
        )

    def handle(self, *args, force: bool = False, slug: str | None = None, **opts):
        qs = Promocion.objects.filter(location__isnull=False)
        if slug:
            qs = qs.filter(slug=slug)

        total = qs.count()
        ok = 0
        skipped = 0
        err = 0
        self.stdout.write(f"backfill_pvgis: {total} promociones candidatas")

        for p in qs.iterator():
            if not force and hasattr(p, "solar"):
                skipped += 1
                self.stdout.write(f"SKIP {p.slug} (ya tiene solar)")
                continue
            try:
                result = store_solar(p)
            except Exception as e:  # defensive: store_solar already swallows most
                err += 1
                self.stdout.write(f"ERR  {p.slug}: {e}")
                continue

            if result is None:
                err += 1
                self.stdout.write(f"ERR  {p.slug}: PVGIS devolvió None")
            else:
                ok += 1
                self.stdout.write(f"OK   {p.slug}: {result.kwh_kwp_year} kWh/kWp·año")

            time.sleep(PVGIS_RATE_S)

        self.stdout.write(f"Hecho. ok={ok} skipped={skipped} err={err}")
