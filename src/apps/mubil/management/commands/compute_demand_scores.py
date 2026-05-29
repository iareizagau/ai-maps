"""Pre-compute :class:`DemandHex` rows for the ``plan`` module (PROPUESTA.md §3.4).

The score is `pop * 0.4 + od * 0.4 - supply * 0.2` per grid cell over
Gipuzkoa (≈ 600 cells at 2.5 km). Heuristics live in
:mod:`apps.mubil.plan.services`; this command is just orchestration.

Idempotent — re-running upserts cells by their ``h3_index`` slug. Cells
outside the current bbox are pruned unless ``--keep-stale`` is passed.

Usage:
  python manage.py compute_demand_scores
  python manage.py compute_demand_scores --dry-run
  python manage.py compute_demand_scores --keep-stale
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.mubil.plan import services


class Command(BaseCommand):
    help = "Pre-compute demand scores per grid cell for the plan module."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-stale",
            action="store_true",
            help="Do not delete previously stored cells outside the current bbox.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Score cells in memory; do not write to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        keep_stale = options["keep_stale"]
        self.stdout.write(
            f"Computing demand scores (dry_run={dry_run}, keep_stale={keep_stale})…"
        )
        stats = services.compute_demand_scores(
            dry_run=dry_run,
            prune_outside_bbox=not keep_stale,
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
