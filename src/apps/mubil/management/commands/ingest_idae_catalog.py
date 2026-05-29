"""Ad-hoc IDAE catalog ingest (coches.idae.es).

Usage:
  python manage.py ingest_idae_catalog                       # full catalog (~23k)
  python manage.py ingest_idae_catalog --marca 134           # one marca id (TESLA=134)
  python manage.py ingest_idae_catalog --marca 134 --dry-run
  python manage.py ingest_idae_catalog --list-marcas         # print id → name and exit
  python manage.py ingest_idae_catalog --throttle 0.5        # speed up (default 1.0s)
"""

from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand

from apps.mubil.data import idae_client, idae_ingest


class Command(BaseCommand):
    help = "Ingest the IDAE vehicle catalog into Vehicle (upsert by idae_id)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--marca",
            type=int,
            action="append",
            default=None,
            help="Restrict to one or more IDAE marca IDs (repeatable).",
        )
        parser.add_argument(
            "--throttle",
            type=float,
            default=idae_client.DEFAULT_THROTTLE_S,
            help=f"Seconds between requests (default {idae_client.DEFAULT_THROTTLE_S}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch + merge, don't write to DB.",
        )
        parser.add_argument(
            "--list-marcas",
            action="store_true",
            help="Print the (id, name) marca catalog and exit.",
        )

    def handle(self, *args, **options):
        if options["list_marcas"]:
            session = idae_client.IDAESession(throttle_s=options["throttle"])
            for m in session.marcas():
                self.stdout.write(f"{m.idae_id:>4}  {m.name}")
            return

        only_marcas = options["marca"] or None
        dry_run = options["dry_run"]

        scope = f"marcas={only_marcas}" if only_marcas else "FULL catalog"
        self.stdout.write(f"IDAE ingest — {scope} (dry_run={dry_run})…")

        stats = idae_ingest.ingest_full(
            only_marcas=only_marcas,
            throttle_s=options["throttle"],
            dry_run=dry_run,
        )

        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
        if stats.errors:
            self.stdout.write(self.style.WARNING(f"{stats.errors} errors during ingest."))
            sys.exit(1)
