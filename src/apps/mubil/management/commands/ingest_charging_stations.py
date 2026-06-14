"""Ad-hoc charging-station ingest (MITECO snapshot + OpenChargeMap + DGT NAP).

Usage:
  # One-shot import of the bundled MITECO CSV, filtered to EH provinces:
  python manage.py ingest_charging_stations --source miteco

  # Weekly refresh from OpenChargeMap (uses settings.OPENCHARGEMAP_API_KEY):
  python manage.py ingest_charging_stations --source ocm

  # Stream DGT NAP DATEX II feed (~85 MB, all Spain ~12k sites):
  python manage.py ingest_charging_stations --source dgt_nap

  # All three, in order — what you want on first deploy:
  python manage.py ingest_charging_stations --source all

  # Parse only, no DB writes:
  python manage.py ingest_charging_stations --source all --dry-run

  # Override the CSV path (useful when DGT publishes a new snapshot):
  python manage.py ingest_charging_stations --source miteco \
        --csv-path /tmp/PuntosCarga-2026Q2.csv
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.mubil.data import charging_ingest


SOURCE_CHOICES = ("miteco", "ocm", "dgt_nap", "all")


class Command(BaseCommand):
    help = "Ingest EV charging stations into ChargingStation (MITECO + OCM)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=SOURCE_CHOICES,
            default="all",
            help="Which source to pull from (default: all).",
        )
        parser.add_argument(
            "--csv-path",
            help="Override MITECO CSV path (default: bundled PuntosCarga.csv).",
        )
        parser.add_argument(
            "--all-spain",
            action="store_true",
            help="Do not filter MITECO CSV to EH provinces (load whole Spain).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch + parse, do not write to DB.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        dry_run = options["dry_run"]
        eh_only = not options["all_spain"]
        csv_path = Path(options["csv_path"]) if options.get("csv_path") else None

        results: dict[str, dict] = {}

        if source in ("miteco", "all"):
            self.stdout.write(
                f"Ingesting MITECO CSV (eh_only={eh_only}, dry_run={dry_run})…"
            )
            stats = charging_ingest.ingest_miteco_csv(
                csv_path=csv_path, eh_only=eh_only, dry_run=dry_run,
            )
            results["miteco"] = stats.as_dict()
            self.stdout.write(self.style.SUCCESS(json.dumps(results["miteco"], indent=2)))

        if source in ("ocm", "all"):
            self.stdout.write(f"Ingesting OpenChargeMap (dry_run={dry_run})…")
            stats = charging_ingest.ingest_openchargemap(dry_run=dry_run)
            results["ocm"] = stats.as_dict()
            self.stdout.write(self.style.SUCCESS(json.dumps(results["ocm"], indent=2)))

        if source in ("dgt_nap", "all"):
            # DGT NAP defaults to all-Spain — the feed is the canonical
            # nationwide source and the EH filter has no production use.
            self.stdout.write(
                f"Ingesting DGT NAP DATEX II (all-Spain, dry_run={dry_run})…"
            )
            stats = charging_ingest.ingest_dgt_nap(dry_run=dry_run)
            results["dgt_nap"] = stats.as_dict()
            self.stdout.write(self.style.SUCCESS(json.dumps(results["dgt_nap"], indent=2)))

        if not results:
            raise CommandError(f"Unknown source: {source}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
