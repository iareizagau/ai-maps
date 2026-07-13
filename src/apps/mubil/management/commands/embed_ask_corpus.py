"""Embed pending MobilityDocument rows with Gemini text-embedding-004.

Usage:
  python manage.py embed_ask_corpus                 # all pending
  python manage.py embed_ask_corpus --limit=10      # batch test
  python manage.py embed_ask_corpus --dry-run       # count only
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.mubil.ask import embeddings


class Command(BaseCommand):
    help = "Embed pending MobilityDocument rows with Gemini text-embedding-004."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=embeddings.DEFAULT_BATCH_SIZE,
            help=f"Rows fetched per DB iteration (default {embeddings.DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--throttle",
            type=float,
            default=embeddings.DEFAULT_THROTTLE_S,
            help="Sleep seconds between API calls (default 0.1 = 10 RPS).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Hard cap on rows processed (default: no cap).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Walk the queryset and count, no Gemini calls, no writes.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Embedding MobilityDocument rows with Gemini…")
        stats = embeddings.embed_corpus(
            batch_size=options["batch_size"],
            throttle_s=options["throttle"],
            limit=options["limit"],
            dry_run=options["dry_run"],
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("Dry run — no API calls, no DB writes.")
            )
