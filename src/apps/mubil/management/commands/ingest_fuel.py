"""Ad-hoc MINCOTUR fuel-station ingest.

Usage:
  python manage.py ingest_fuel                          # EH default (01, 20, 48)
  python manage.py ingest_fuel --provinces 20           # only Gipuzkoa
  python manage.py ingest_fuel --provinces 01,20,48,31  # full EH incl. Navarra
  python manage.py ingest_fuel --dry-run                # fetch + parse, no DB writes
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.mubil.data import fuel_ingest, mincotur_client


class Command(BaseCommand):
    help = "Ingest fuel-station snapshot from MINCOTUR into FuelStation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provinces",
            help=(
                "Comma-separated INE province codes "
                f"(default: {','.join(mincotur_client.DEFAULT_EH_PROVINCES)})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch + parse, do not write to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        raw = options.get("provinces")
        if raw:
            codes = tuple(c.strip().zfill(2) for c in raw.split(",") if c.strip())
        else:
            codes = mincotur_client.DEFAULT_EH_PROVINCES

        self.stdout.write(
            f"Ingesting MINCOTUR provinces {list(codes)} (dry_run={dry_run})…"
        )
        stats = fuel_ingest.ingest_provinces(prov_codes=codes, dry_run=dry_run)
        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
