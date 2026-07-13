"""Ingest the RAG corpus for the `ask` MUST module.

Usage:
  python manage.py ingest_ask_corpus                  # all sources, max 1k docs
  python manage.py ingest_ask_corpus --source=ckan
  python manage.py ingest_ask_corpus --max-pages=2 --dry-run

PROPUESTA.md §3.2.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.mubil.ask import ingest


class Command(BaseCommand):
    help = "Ingest CKAN + OpenData Euskadi datasets into MobilityDocument."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["ckan", "euskadi", "all"],
            default="all",
            help="Source to ingest (default: all).",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=20,
            help="Hard cap on pages per source (default: 20).",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=50,
            help="Page size per request (default: 50).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and parse but don't write to DB.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        max_pages = options["max_pages"]
        page_size = options["page_size"]
        dry_run = options["dry_run"]

        results = []

        if source in ("ckan", "all"):
            self.stdout.write(f"Ingesting CKAN datos.gob.es (max_pages={max_pages})…")
            stats = ingest.ingest_ckan(
                max_pages=max_pages,
                page_size=page_size,
                dry_run=dry_run,
            )
            self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
            results.append(stats.as_dict())

        if source in ("euskadi", "all"):
            self.stdout.write(
                self.style.WARNING(
                    "OpenData Euskadi ingest not yet implemented — skipping."
                )
            )

        if not results:
            self.stdout.write(self.style.WARNING("Nothing ingested."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
