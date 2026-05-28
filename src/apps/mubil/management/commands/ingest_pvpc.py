"""Ad-hoc PVPC ingest from ESIOS indicator 1001.

Usage:
  python manage.py ingest_pvpc                       # last 48h (matches the Celery cron)
  python manage.py ingest_pvpc --hours 168           # last 7 days
  python manage.py ingest_pvpc --start 2026-05-01 --end 2026-05-08
  python manage.py ingest_pvpc --dry-run             # fetch + parse, no DB writes
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from apps.mubil.data import pvpc_ingest


def _parse_iso_date(s: str) -> datetime:
    try:
        d = datetime.fromisoformat(s)
    except ValueError as e:
        raise CommandError(f"Invalid date {s!r}: {e}")
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


class Command(BaseCommand):
    help = "Ingest PVPC hourly prices from ESIOS into EnergyPricePVPC."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=48,
            help="Rolling-window mode: pull the last N hours (default 48).",
        )
        parser.add_argument(
            "--start",
            help="Explicit-window mode: ISO date/datetime, inclusive (overrides --hours).",
        )
        parser.add_argument(
            "--end",
            help="Explicit-window mode: ISO date/datetime, exclusive on the hour.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch + parse, do not write to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if options["start"] or options["end"]:
            if not (options["start"] and options["end"]):
                raise CommandError("--start and --end must be used together.")
            start = _parse_iso_date(options["start"])
            end = _parse_iso_date(options["end"])
            self.stdout.write(
                f"Ingesting PVPC window {start.isoformat()} → {end.isoformat()} "
                f"(dry_run={dry_run})…"
            )
            stats = pvpc_ingest.ingest_window(start=start, end=end, dry_run=dry_run)
        else:
            hours = options["hours"]
            self.stdout.write(f"Ingesting PVPC last {hours}h (dry_run={dry_run})…")
            stats = pvpc_ingest.ingest_recent_hours(hours=hours, dry_run=dry_run)

        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
