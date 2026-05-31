"""Capa 2: rellena `price_eur` por heurística para todo el catálogo IDAE.

Calibra `price_heuristic.calibrate()` desde las anclas verificadas
(`price_source='manual'`) y luego escribe predicciones en las filas con
`price_source IN ('unknown','mock','heuristic')`. Respeta `'manual'` y
`'gemini'` (este último porque Gemini puede ser más preciso que la
heurística genérica para modelos populares).

Uso:
    docker exec maps_web python manage.py seed_vehicle_prices_heuristic
    docker exec maps_web python manage.py seed_vehicle_prices_heuristic --dry-run
    docker exec maps_web python manage.py seed_vehicle_prices_heuristic --propulsion BEV
"""

from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.mubil.data import price_heuristic
from apps.mubil.models import Vehicle


class Command(BaseCommand):
    help = "Capa 2: rellena `price_eur` con heurística calibrada sobre anclas manuales."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Reporta sin escribir.")
        parser.add_argument("--propulsion", type=str, default=None,
                            help="Limitar a una propulsion (BEV/PHEV/HEV/ICE/DIESEL...).")
        parser.add_argument("--limit", type=int, default=None,
                            help="Limitar nº de filas a actualizar (debug).")

    @transaction.atomic
    def handle(self, *args, **opts):
        # 1. Calibrar contra anclas manuales
        anchors = list(
            Vehicle.objects
            .filter(price_source=Vehicle.PriceSource.MANUAL, price_eur__isnull=False)
        )
        if len(anchors) < 5:
            self.stderr.write(self.style.ERROR(
                f"Sólo {len(anchors)} anclas manuales — corre primero "
                "`seed_vehicle_prices_manual`."
            ))
            return

        table = price_heuristic.calibrate(anchors)
        mae = price_heuristic.mean_abs_error(table, anchors)
        mean_price = sum(v.price_eur for v in anchors) / len(anchors)
        rel_err = mae / mean_price * 100

        self.stdout.write(self.style.NOTICE(
            f"Calibración: {len(anchors)} anclas · MAE in-sample {mae:.0f} € "
            f"({rel_err:.1f}% del precio medio {mean_price:.0f} €)"
        ))
        self._print_calibration(table)

        # 2. Seleccionar candidatos a rellenar/sobrescribir
        overwritable = (
            Vehicle.PriceSource.UNKNOWN,
            Vehicle.PriceSource.MOCK,
            Vehicle.PriceSource.HEURISTIC,
        )
        qs = Vehicle.objects.filter(price_source__in=overwritable)
        if opts["propulsion"]:
            qs = qs.filter(propulsion=opts["propulsion"].upper())
        if opts["limit"]:
            qs = qs[:opts["limit"]]

        total = qs.count()
        self.stdout.write(f"Candidatos a rellenar: {total}")

        # 3. Iterar y aplicar
        now = datetime.now(timezone.utc)
        applied = 0
        per_propulsion: dict[str, int] = {}

        # bulk_update por chunks para no cargar 24k objetos en memoria
        CHUNK = 1000
        buf: list[Vehicle] = []
        for v in qs.iterator(chunk_size=CHUNK):
            pred = table.estimate(
                propulsion=v.propulsion, make=v.make, battery_kwh=v.battery_kwh,
            )
            v.price_eur = pred
            v.price_source = Vehicle.PriceSource.HEURISTIC
            v.price_updated_at = now
            buf.append(v)
            per_propulsion[v.propulsion] = per_propulsion.get(v.propulsion, 0) + 1
            applied += 1
            if len(buf) >= CHUNK:
                if not opts["dry_run"]:
                    Vehicle.objects.bulk_update(
                        buf, ["price_eur", "price_source", "price_updated_at"]
                    )
                buf.clear()

        if buf and not opts["dry_run"]:
            Vehicle.objects.bulk_update(
                buf, ["price_eur", "price_source", "price_updated_at"]
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Aplicado: {applied} filas"))
        for prop, n in sorted(per_propulsion.items()):
            self.stdout.write(f"  {prop:7s} {n:5d}")
        if opts["dry_run"]:
            self.stdout.write(self.style.NOTICE("(dry-run: no se escribió nada)"))

    def _print_calibration(self, table: price_heuristic.CalibrationTable):
        self.stdout.write("\nMedianas por cluster (propulsion × tier):")
        tiers = ("budget", "mid", "premium")
        self.stdout.write(
            f"  {'propulsion':10s} " + "".join(f"{t:>12s}" for t in tiers)
        )
        for prop in ("BEV", "PHEV", "HEV", "ICE", "DIESEL"):
            row = f"  {prop:10s} "
            for tier in tiers:
                v = table.cluster_median_price.get((prop, tier))
                row += f"{(str(v) + ' €' if v else '—'):>12s}"
            self.stdout.write(row)
        self.stdout.write("")
