"""Ad-hoc MINCOTUR fuel-station ingest.

Usage:
  python manage.py ingest_fuel                          # EH default (01, 20, 48)
  python manage.py ingest_fuel --spain                  # all 52 INE provinces
  python manage.py ingest_fuel --provinces 20           # only Gipuzkoa
  python manage.py ingest_fuel --provinces 01,20,48,31  # EH + Navarra
  python manage.py ingest_fuel --spain --workers 12     # parallel, 12 threads
  python manage.py ingest_fuel --spain --dry-run        # fetch + parse, no DB writes
  python manage.py ingest_fuel --spain --detail         # show per-province breakdown
"""

from __future__ import annotations

import json
import threading

from django.core.management.base import BaseCommand

from apps.mubil.data import fuel_ingest, mincotur_client


class Command(BaseCommand):
    help = "Ingest fuel-station snapshot from MINCOTUR into FuelStation."

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group()
        scope.add_argument(
            "--spain",
            action="store_true",
            help="Ingest all 52 INE provinces (España completa). Overrides --provinces.",
        )
        scope.add_argument(
            "--provinces",
            help=(
                "Comma-separated INE province codes "
                f"(default: {','.join(mincotur_client.DEFAULT_EH_PROVINCES)})."
            ),
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=fuel_ingest.DEFAULT_WORKERS,
            help=(
                f"Number of parallel HTTP workers (default: {fuel_ingest.DEFAULT_WORKERS}). "
                "Provinces are fetched concurrently; use 1 for serial execution."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch + parse, do not write to DB.",
        )
        parser.add_argument(
            "--detail",
            action="store_true",
            help="Print per-province breakdown at the end.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        workers: int = options["workers"]
        show_detail: bool = options["detail"]
        _lock = threading.Lock()
        completed = [0]

        if options["spain"]:
            total_provinces = len(fuel_ingest.ALL_SPAIN_PROVINCES)
            codes = None  # will call ingest_spain
        else:
            raw = options.get("provinces")
            if raw:
                codes = tuple(c.strip().zfill(2) for c in raw.split(",") if c.strip())
            else:
                codes = mincotur_client.DEFAULT_EH_PROVINCES
            total_provinces = len(codes)

        def progress_cb(code: str, fetched: int, created: int, errors: int) -> None:
            with _lock:
                completed[0] += 1
                pct = completed[0] * 100 // total_provinces
                name = fuel_ingest._PROVINCE_NAMES.get(code, code)
                status = self.style.SUCCESS("✓") if errors == 0 else self.style.ERROR("✗")
                self.stdout.write(
                    f"  [{pct:3d}%] {status} {code} {name:<22} "
                    f"fetched={fetched} created={created} errors={errors}"
                )

        if options["spain"]:
            self.stdout.write(
                f"Ingesting España completa ({total_provinces} provinces, "
                f"workers={workers}, dry_run={dry_run})…"
            )
            stats = fuel_ingest.ingest_spain(
                dry_run=dry_run,
                workers=workers,
                progress_cb=progress_cb,
            )
        else:
            self.stdout.write(
                f"Ingesting MINCOTUR provinces {list(codes)} "
                f"(workers={workers}, dry_run={dry_run})…"
            )
            stats = fuel_ingest.ingest_provinces(
                prov_codes=codes,
                dry_run=dry_run,
                workers=workers,
                progress_cb=progress_cb,
            )

        summary = stats.as_dict()
        self.stdout.write(self.style.SUCCESS("\n" + json.dumps(summary, indent=2)))

        if show_detail and stats.by_province:
            self.stdout.write("\nPer-province breakdown:")
            for code in sorted(stats.by_province):
                p = stats.by_province[code]
                line = (
                    f"  {code} {p['name']:<22} "
                    f"fetched={p['fetched']:4d} "
                    f"created={p['created']:4d} "
                    f"updated={p['updated']:4d} "
                    f"errors={p['errors']}"
                )
                if p["errors"]:
                    self.stdout.write(self.style.ERROR(line))
                else:
                    self.stdout.write(line)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
