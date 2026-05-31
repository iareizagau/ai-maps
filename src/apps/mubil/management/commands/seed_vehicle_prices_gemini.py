"""Capa 3: refina PVP heurístico con Gemini para los top-N vehículos.

Selecciona vehículos con `price_source='heuristic'` priorizando los más
relevantes (BEV/PHEV recientes con datos completos), llama a Gemini con
few-shot anclas, y sólo sobrescribe si:
  - confidence >= MIN_CONFIDENCE
  - el precio Gemini está dentro del ±50 % del heurístico (sanity check)
  - el precio cae dentro de [5.000, 250.000] €

Memoria: Gemini free tier tiene cuotas RPD ajustadas (50 RPD para flash,
1.500 para flash-lite). Empezar con --limit 20 y subir en sesiones
sucesivas. --dry-run NO llama a Gemini (no quema cuota).

Uso:
    docker exec maps_web python manage.py seed_vehicle_prices_gemini --limit 20
    docker exec maps_web python manage.py seed_vehicle_prices_gemini --limit 20 --dry-run
    docker exec maps_web python manage.py seed_vehicle_prices_gemini --limit 50 --propulsion BEV
"""

import time
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.mubil.data import gemini_price_lookup
from apps.mubil.models import Vehicle


MIN_CONFIDENCE = 0.6
SLEEP_BETWEEN_CALLS_S = 0.5  # respiro entre requests para no saturar RPM


class Command(BaseCommand):
    help = "Capa 3: refina PVP de top-N vehículos heurísticos vía Gemini."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20,
                            help="Nº máximo de vehículos a consultar (default 20).")
        parser.add_argument("--propulsion", type=str, default=None,
                            help="Filtrar por propulsion (BEV/PHEV/HEV/ICE/DIESEL).")
        parser.add_argument("--min-year", type=int, default=2024,
                            help="Sólo vehículos year >= min-year (default 2024).")
        parser.add_argument("--dry-run", action="store_true",
                            help="No llama a Gemini ni escribe — sólo lista.")
        parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE,
                            help=f"Umbral confianza Gemini (default {MIN_CONFIDENCE}).")

    def handle(self, *args, **opts):
        # Selección: heurísticos recientes con specs decentes.
        qs = (
            Vehicle.objects
            .filter(price_source=Vehicle.PriceSource.HEURISTIC)
            .filter(year__gte=opts["min_year"])
            .order_by("-year", "-battery_kwh", "id")
        )
        if opts["propulsion"]:
            qs = qs.filter(propulsion=opts["propulsion"].upper())
        qs = qs[: opts["limit"]]

        candidates = list(qs)
        if not candidates:
            self.stdout.write(self.style.WARNING("Sin candidatos. ¿Has corrido la Capa 2 (heurística)?"))
            return

        self.stdout.write(
            f"Procesando {len(candidates)} vehículos (limit={opts['limit']}, "
            f"min_year={opts['min_year']}, propulsion={opts['propulsion'] or 'all'})"
        )
        if opts["dry_run"]:
            for v in candidates:
                self.stdout.write(
                    f"  · {v.id:5d}  {v.make[:14]:14s} {v.model[:35]:35s} "
                    f"{v.propulsion:5s}  heurística={v.price_eur} €"
                )
            self.stdout.write(self.style.NOTICE("(dry-run: no se llamó a Gemini)"))
            return

        now = datetime.now(timezone.utc)
        accepted = 0
        rejected_conf = 0
        rejected_outlier = 0
        errored = 0
        min_conf = opts["min_confidence"]

        for i, v in enumerate(candidates, start=1):
            heur = v.price_eur
            try:
                est = gemini_price_lookup.estimate_price(v)
            except Exception as e:  # noqa: BLE001
                errored += 1
                self.stderr.write(self.style.ERROR(
                    f"  [{i}/{len(candidates)}] {v.make[:14]} {v.model[:30]} → ERROR: {e}"
                ))
                continue

            if est.price_eur is None or est.confidence < min_conf:
                rejected_conf += 1
                self.stdout.write(
                    f"  [{i}/{len(candidates)}] {v.make[:14]:14s} {v.model[:30]:30s} → "
                    f"SKIP confianza {est.confidence:.2f} (heur={heur} €)"
                )
                time.sleep(SLEEP_BETWEEN_CALLS_S)
                continue

            if not gemini_price_lookup.validate_against_heuristic(
                gemini_price=est.price_eur, heuristic_price=heur,
            ):
                rejected_outlier += 1
                self.stdout.write(self.style.WARNING(
                    f"  [{i}/{len(candidates)}] {v.make[:14]:14s} {v.model[:30]:30s} → "
                    f"OUTLIER gem={est.price_eur} € heur={heur} € (revisar)"
                ))
                time.sleep(SLEEP_BETWEEN_CALLS_S)
                continue

            if not (5_000 <= est.price_eur <= 250_000):
                rejected_outlier += 1
                self.stdout.write(self.style.WARNING(
                    f"  [{i}/{len(candidates)}] {v.make[:14]:14s} → "
                    f"OUT-OF-RANGE {est.price_eur} €"
                ))
                time.sleep(SLEEP_BETWEEN_CALLS_S)
                continue

            # Acepta y escribe en su propia transacción (no perder lote completo si una falla)
            with transaction.atomic():
                v.price_eur = est.price_eur
                v.price_source = Vehicle.PriceSource.GEMINI
                v.price_updated_at = now
                v.save(update_fields=["price_eur", "price_source", "price_updated_at"])
            accepted += 1
            self.stdout.write(self.style.SUCCESS(
                f"  [{i}/{len(candidates)}] {v.make[:14]:14s} {v.model[:30]:30s} → "
                f"{est.price_eur} € (conf {est.confidence:.2f}, heur={heur} €)"
            ))
            time.sleep(SLEEP_BETWEEN_CALLS_S)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Resumen: {accepted} aceptados · {rejected_conf} baja confianza · "
            f"{rejected_outlier} outliers · {errored} errores"
        ))
