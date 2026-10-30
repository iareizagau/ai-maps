"""
Ingest Amenabar promotions + their surrounding POIs.

Usage:
  docker compose exec web python manage.py ingest_amenabar           # scrape + geocode + POIs
  docker compose exec web python manage.py ingest_amenabar --skip-pois
  docker compose exec web python manage.py ingest_amenabar --only-pois
  docker compose exec web python manage.py ingest_amenabar --limit 3
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.amenabar import services
from apps.amenabar.models import Promocion


class Command(BaseCommand):
    help = "Scrape amenabarpromociones.com, geocode promotions, and cache nearby POIs."

    def add_arguments(self, parser):
        parser.add_argument("--skip-pois", action="store_true")
        parser.add_argument("--only-pois", action="store_true")
        parser.add_argument(
            "--missing-pois-only",
            action="store_true",
            help="Only fetch POIs for promotions that currently have 0 POIs.",
        )
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--via-celery",
            action="store_true",
            help=(
                "Dispatch one Celery task per promoción instead of running the "
                "fetches inline. Spaces them out so Overpass never sees a burst, "
                "retries each with exponential backoff, and frees memory between "
                "iterations. Requires the `worker` service to be running."
            ),
        )
        parser.add_argument(
            "--spacing-s",
            type=int,
            default=5,
            help="Seconds between enqueued tasks when --via-celery is set.",
        )

    def handle(self, *args, **opts):
        from django.db.models import Count

        skip_pois = opts["skip_pois"]
        only_pois = opts["only_pois"]
        missing_only = opts["missing_pois_only"]
        limit = opts["limit"]
        via_celery = opts["via_celery"]
        spacing_s = opts["spacing_s"]

        if not only_pois and not missing_only:
            self._scrape_and_upsert()

        if skip_pois:
            return

        qs = Promocion.objects.filter(location__isnull=False).order_by("nombre")
        if missing_only:
            qs = qs.annotate(n_pois=Count("pois")).filter(n_pois=0)
        if limit:
            qs = qs[:limit]

        if via_celery:
            from apps.amenabar.tasks import fetch_pois_for_promocion

            ids = list(qs.values_list("id", flat=True))
            for i, pk in enumerate(ids):
                fetch_pois_for_promocion.apply_async(
                    args=[pk],
                    countdown=i * spacing_s,
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enqueued {len(ids)} tasks (spacing {spacing_s}s). "
                    f"Total ETA: ~{len(ids) * spacing_s // 60} min. "
                    f"Watch with: docker compose logs -f worker"
                )
            )
            return

        for p in qs:
            self.stdout.write(f"POIs → {p.nombre} ({p.ciudad})")
            try:
                elements = services.fetch_pois_overpass(p.location.y, p.location.x)
                kept = services.store_pois(p, elements)
                self.stdout.write(self.style.SUCCESS(f"  {kept} POIs stored"))
            except Exception as e:
                self.stderr.write(f"  failed: {e}")
            # Overpass is shared infra; be polite.
            time.sleep(2.0)

    def _scrape_and_upsert(self):
        self.stdout.write("Scraping amenabarpromociones.com ...")
        scraped = services.scrape_amenabar_listado()
        self.stdout.write(f"  found {len(scraped)} promotions")

        for s in scraped:
            obj, created = Promocion.objects.update_or_create(
                slug=s.slug,
                defaults={
                    "nombre": s.nombre,
                    "ciudad": s.ciudad,
                    "provincia": "",
                    "estado": s.estado,
                    "porcentaje_vendido": s.porcentaje_vendido,
                    "nota": s.nota,
                    "source_url": s.source_url,
                    "detail_url": s.detail_url,
                    "image_url": s.image_url,
                },
            )
            if obj.location is None:
                pt = services.geocode_promocion(obj)
                if pt:
                    obj.location = pt
                    obj.save(update_fields=["location"])
                    self.stdout.write(
                        self.style.SUCCESS(f"  {'+' if created else '~'} {obj.nombre}  @ {pt.y:.4f},{pt.x:.4f}")
                    )
                else:
                    self.stderr.write(f"  ? {obj.nombre}  (no geocode)")
            else:
                self.stdout.write(f"  = {obj.nombre}  (already geocoded)")
            # Nominatim rate limit
            time.sleep(services.NOMINATIM_RATE_S)
