"""Province-level EV-registration ingest (DGT matriculaciones → EVRegistration).

The DGT microdata download sits behind a JSF portal with no clean static URL, so
this is a one-shot CSV seed like the other CSVs in `apps/mubil/data/`. Obtain a
province × month × propulsion CSV for Araba/Bizkaia/Gipuzkoa (DGT IEST portal
export or Eustat) and point this command at it. See
`apps.mubil.data.ev_registration_ingest` for the CSV column contract.

Usage:
  python manage.py ingest_ev_registrations                       # default data/MatriculacionesEV_EH.csv
  python manage.py ingest_ev_registrations --csv /path/to/file.csv
  python manage.py ingest_ev_registrations --dry-run             # parse + validate, no DB writes
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.mubil.data import ev_registration_ingest as ingest


class Command(BaseCommand):
    help = "Ingest province-level EV registrations from a CSV into EVRegistration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            help="Path to the matriculaciones CSV (default: data/MatriculacionesEV_EH.csv).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse + validate, do not write to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        path = options.get("csv")
        self.stdout.write(f"Ingesting EV registrations (csv={path or 'default'}, dry_run={dry_run})…")
        stats = ingest.ingest_csv(path=path, dry_run=dry_run)
        out = json.dumps(stats.as_dict(), indent=2, ensure_ascii=False)
        if stats.errors:
            self.stdout.write(self.style.ERROR(out))
        else:
            self.stdout.write(self.style.SUCCESS(out))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
