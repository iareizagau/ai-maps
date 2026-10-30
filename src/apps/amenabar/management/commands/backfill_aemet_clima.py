"""Backfill PromocionClima for every Promocion with location.

Requires AemetStation inventory to be synced first (see
`backfill_aemet_stations`). Aborts cleanly if the inventory is empty.

Usage:
  docker compose exec web_maps python manage.py backfill_aemet_clima
  docker compose exec web_maps python manage.py backfill_aemet_clima --force
  docker compose exec web_maps python manage.py backfill_aemet_clima --slug aires-de-arganda
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.amenabar.models import AemetStation, Promocion
from apps.amenabar.services_aemet import AEMET_RATE_S, store_clima


class Command(BaseCommand):
    help = "Backfill AEMET monthly normals for every Promocion with a location."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute even when a PromocionClima already exists.",
        )
        parser.add_argument(
            "--slug",
            help="Only this promocion (by slug).",
        )

    def handle(self, *args, force: bool = False, slug: str | None = None, **opts):
        if not AemetStation.objects.exists():
            self.stderr.write(
                "ERR: inventario AEMET vacío. Ejecuta `backfill_aemet_stations` primero."
            )
            return

        qs = Promocion.objects.filter(location__isnull=False)
        if slug:
            qs = qs.filter(slug=slug)

        total = qs.count()
        ok = 0
        skipped = 0
        no_station = 0
        err = 0
        self.stdout.write(f"backfill_aemet_clima: {total} promociones candidatas")

        for p in qs.iterator():
            if not force and hasattr(p, "clima"):
                skipped += 1
                self.stdout.write(f"SKIP {p.slug} (ya tiene clima)")
                continue
            try:
                result = store_clima(p)
            except Exception as e:  # defensive: store_clima already swallows most
                err += 1
                self.stdout.write(f"ERR  {p.slug}: {e}")
                continue

            if result is None:
                no_station += 1
                self.stdout.write(f"NONE {p.slug}: sin estación ≤ 50 km o AEMET falló")
            else:
                ok += 1
                self.stdout.write(f"OK   {p.slug}: {result.station.nombre} ({result.distance_m} m)")

            time.sleep(AEMET_RATE_S)

        self.stdout.write(
            f"Hecho. ok={ok} skipped={skipped} sin_estacion_o_err={no_station} err={err}"
        )
