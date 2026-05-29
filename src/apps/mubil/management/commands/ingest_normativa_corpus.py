"""Ingest the curated regulatory corpus into MobilityDocument.

Closes the gap that the CKAN-only corpus left for prompts about MOVES III,
DGT labels, PVPC, ZBE, etc. (see :mod:`apps.mubil.data.normativa_sources`).

Usage:
  python manage.py ingest_normativa_corpus
  python manage.py ingest_normativa_corpus --dry-run
  python manage.py ingest_normativa_corpus --only moves         # substring URL filter
  python manage.py ingest_normativa_corpus --throttle 0.5
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.mubil.data import normativa_ingest


class Command(BaseCommand):
    help = "Ingest the curated regulatory corpus into MobilityDocument."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            action="append",
            default=None,
            help="Substring URL filter; repeatable.",
        )
        parser.add_argument(
            "--throttle",
            type=float,
            default=normativa_ingest.DEFAULT_THROTTLE_S,
            help=f"Seconds between sources (default {normativa_ingest.DEFAULT_THROTTLE_S}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch + parse + chunk, do not write to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write(
            f"Normativa ingest — only={options['only']} dry_run={dry_run}…"
        )

        stats = normativa_ingest.ingest_normativa(
            only=options["only"],
            throttle_s=options["throttle"],
            dry_run=dry_run,
        )

        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
        self.stdout.write(
            "Run `manage.py embed_ask_corpus` next to embed the new chunks."
        )
