"""Ad-hoc IDAE catalog ingest (coches.idae.es).

Usage:
  python manage.py ingest_idae_catalog                       # full catalog (~23k)
  python manage.py ingest_idae_catalog --marca 134           # one marca id (TESLA=134)
  python manage.py ingest_idae_catalog --marca 134 --dry-run
  python manage.py ingest_idae_catalog --list-marcas         # print id → name and exit
  python manage.py ingest_idae_catalog --throttle 0.5        # speed up (default 1.0s)
  python manage.py ingest_idae_catalog --quiet               # sólo cabecera + resumen
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time

from django.core.management.base import BaseCommand

from apps.mubil.data import idae_client, idae_ingest


def _fmt_eta(seconds: float) -> str:
    """Formato human-friendly para un ETA en segundos."""
    if seconds <= 0 or seconds != seconds:  # NaN guard
        return "—"
    if seconds < 90:
        return f"{int(seconds)} s"
    if seconds < 5400:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


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
        parser.add_argument(
            "--quiet", action="store_true",
            help="Sin línea-por-marca; sólo cabecera y resumen final.",
        )

    def handle(self, *args, **options):
        if options["list_marcas"]:
            session = idae_client.IDAESession(throttle_s=options["throttle"])
            for m in session.marcas():
                self.stdout.write(f"{m.idae_id:>4}  {m.name}")
            return

        only_marcas = options["marca"] or None
        dry_run = options["dry_run"]
        quiet = options["quiet"]
        throttle = options["throttle"]

        scope = f"marcas={only_marcas}" if only_marcas else "FULL catalog"
        started_at = time.monotonic()
        wall_start = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stdout.write(self.style.HTTP_INFO(
            f"[{wall_start}] IDAE ingest — {scope} · throttle={throttle}s · dry_run={dry_run}"
        ))

        # Callbacks que escriben progreso a stdout. Encapsulados aquí para
        # cerrar sobre `self` y `started_at` (logger Python no llega aquí
        # sin configurar handlers — este patrón es más directo).
        state = {"total_marcas": 0}

        def on_marcas_listed(marcas):
            state["total_marcas"] = len(marcas)
            self.stdout.write(
                f"  → {len(marcas)} marcas a procesar "
                f"(estimación ~{_fmt_eta(len(marcas) * 7)} a este throttle)"
            )

        def on_marca_done(marca, delta, cumulative):
            if quiet:
                return
            elapsed = time.monotonic() - started_at
            done = cumulative.marcas_seen
            total = state["total_marcas"] or done
            remaining = total - done
            avg_per_marca = elapsed / max(done, 1)
            eta_s = avg_per_marca * remaining
            # Línea compacta — cabe en 100 cols
            self.stdout.write(
                f"  [{done:>3}/{total:<3}] {marca.name[:22]:22s} "
                f"fetched={delta.fetched_elec + delta.fetched_wltp:>4}  "
                f"new={delta.created:>3} upd={delta.updated:>3} err={delta.errors:>2}  "
                f"∑ created={cumulative.created} updated={cumulative.updated}  "
                f"eta={_fmt_eta(eta_s)}"
            )

        try:
            stats = idae_ingest.ingest_full(
                only_marcas=only_marcas,
                throttle_s=throttle,
                dry_run=dry_run,
                on_marcas_listed=on_marcas_listed,
                on_marca_done=on_marca_done,
            )
        except KeyboardInterrupt:
            elapsed = time.monotonic() - started_at
            self.stdout.write(self.style.WARNING(
                f"\n[INT] Interrumpido tras {_fmt_eta(elapsed)} — los upserts "
                "ya escritos quedan en BBDD (idempotente, puedes relanzar)."
            ))
            sys.exit(130)

        elapsed = time.monotonic() - started_at
        wall_end = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"[{wall_end}] Finalizado en {_fmt_eta(elapsed)}"
        ))
        self.stdout.write(self.style.SUCCESS(json.dumps(stats.as_dict(), indent=2)))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no DB writes."))
        if stats.errors:
            self.stdout.write(self.style.WARNING(
                f"{stats.errors} errores durante la ingesta — revisa logs Django "
                "(logger `apps.mubil.data.idae_ingest`)."
            ))
            sys.exit(1)
