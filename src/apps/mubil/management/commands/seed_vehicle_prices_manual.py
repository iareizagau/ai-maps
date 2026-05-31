"""Capa 1 de la pipeline `price_eur` — seed manual verificado.

~30 vehículos representativos cuyo PVP base 2026 verifico a mano (fuentes:
web fabricante / km77.com / motor.es a fecha 2026-05-31). Estos forman:
  1) un anclaje de calibración para la regresión heurística (Capa 2),
  2) una verdad de validación cruzada para los precios de Gemini (Capa 3),
  3) el contenido visible "verificado" en el catálogo cuando el usuario
     teclea modelos populares.

Política de escritura:
- Hace UPDATE sobre filas IDAE existentes (busca por make + keyword en
  model + propulsion). Nunca crea filas nuevas para evitar duplicar el
  catálogo IDAE de 24k.
- Sobrescribe price_eur si la fila previa tiene `price_source` en
  ('unknown', 'mock', 'heuristic', 'gemini'). Respeta 'manual' anterior
  (idempotencia: re-correr no machaca curaciones manuales posteriores).
- Marca price_source='manual' y price_updated_at=now().

Uso:
    docker exec maps_web python manage.py seed_vehicle_prices_manual
    docker exec maps_web python manage.py seed_vehicle_prices_manual --dry-run
"""

from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.mubil.models import Vehicle


# ───────────────────── Catálogo de anclas verificadas ─────────────────────
# Cada entrada: (make, model_keyword, propulsion, price_eur, note)
# - model_keyword: substring case-insensitive contra Vehicle.model.
# - Se prefiere la fila con year más alto cuando hay varias.
# - El precio es PVP base (sin opciones) verificado en fuente pública 2026-05.

ANCHORS = [
    # ────────── BEV budget ──────────
    ("Dacia",         "Spring",                "BEV",     18500, "Spring 65 Expression — dacia.es"),
    ("MG",            "MG4",                   "BEV",     25990, "MG4 Standard 51 kWh — mgmotor.es"),
    ("Renault",       "Zoe",                   "BEV",     28500, "ZOE E-Tech R110 50 kWh — renault.es (last MY)"),

    # ────────── BEV mid ──────────
    ("Peugeot",       "e-208",                 "BEV",     31500, "e-208 Active 51 kWh — peugeot.es"),
    ("MG",            "ZS",                    "BEV",     31490, "MG ZS EV Standard — mgmotor.es"),
    ("Hyundai",       "Kona",                  "BEV",     35500, "Kona Electric 65 kWh Maxx — hyundai.es"),
    ("Renault",       "Megane",                "BEV",     36500, "Megane E-Tech EV60 220 — renault.es"),
    ("Tesla",         "Model 3",               "BEV",     39990, "Model 3 RWD — tesla.com/es"),
    ("Kia",           "Niro",                  "BEV",     41500, "Niro EV 64.8 kWh Drive — kia.com/es"),

    # ────────── BEV premium ──────────
    ("Tesla",         "Model Y",               "BEV",     45000, "Model Y RWD — tesla.com/es"),
    ("Hyundai",       "Ioniq 5",               "BEV",     45900, "Ioniq 5 RWD 58 kWh — hyundai.es"),
    ("Volkswagen",    "ID.4",                  "BEV",     47900, "ID.4 Pro 286 CV — volkswagen.es"),
    ("Mercedes-Benz", "EQA",                   "BEV",     51900, "EQA 250 — mercedes-benz.es"),
    ("BMW",           "i4",                    "BEV",     60900, "i4 eDrive40 — bmw.es"),

    # ────────── ICE budget ──────────
    ("Dacia",         "Sandero",               "ICE",     13900, "Sandero 1.0 TCe 90 Expression — dacia.es"),
    ("Renault",       "Clio",                  "ICE",     18500, "Clio TCe 90 Evolution — renault.es"),
    ("Seat",          "Ibiza",                 "ICE",     18900, "Ibiza 1.0 TSI 95 Style — seat.es"),
    ("Toyota",        "Yaris",                 "ICE",     19500, "Yaris 1.5 VVT-i Active Tech — toyota.es"),

    # ────────── ICE/HEV mid ──────────
    ("Seat",          "Leon",                  "ICE",     25500, "León 1.5 TSI 130 Style — seat.es"),
    ("Volkswagen",    "Golf",                  "ICE",     28500, "Golf 1.5 TSI 150 Life — volkswagen.es"),
    ("Hyundai",       "Tucson",                "ICE",     28900, "Tucson 1.6 T-GDi 150 Klass — hyundai.es"),
    ("Toyota",        "Corolla",               "HEV",     26500, "Corolla 1.8 HEV Active Tech — toyota.es"),
    ("Toyota",        "RAV4",                  "HEV",     38500, "RAV4 2.5 HEV Advance — toyota.es"),
    ("Hyundai",       "Tucson",                "HEV",     32500, "Tucson 1.6 HEV Klass — hyundai.es"),

    # ────────── DIESEL ──────────
    ("Volkswagen",    "Golf",                  "DIESEL",  30500, "Golf 2.0 TDI 115 Life — volkswagen.es"),
    ("Audi",          "A4",                    "DIESEL",  47500, "A4 35 TDI 163 S line — audi.es"),
    ("BMW",           "320",                   "DIESEL",  48900, "320d Berlina — bmw.es"),
    ("Volkswagen",    "Touareg",               "DIESEL",  75500, "Touareg 3.0 V6 TDI 231 — volkswagen.es"),

    # ────────── PHEV ──────────
    ("Kia",           "Niro",                  "PHEV",    35500, "Niro PHEV Drive — kia.com/es"),
    ("Hyundai",       "Tucson",                "PHEV",    41500, "Tucson PHEV 265 Klass — hyundai.es"),
    ("Volkswagen",    "Tiguan",                "PHEV",    46900, "Tiguan eHybrid Life — volkswagen.es"),
    ("Cupra",         "Formentor",             "PHEV",    50500, "Formentor VZ e-Hybrid 272 — cupra.com"),
    ("BMW",           "330",                   "PHEV",    56900, "330e Berlina — bmw.es"),
]


class Command(BaseCommand):
    help = "Capa 1: marca como 'manual' el PVP verificado de ~30 anclas del catálogo IDAE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Sólo reportar matches sin escribir en BD.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        now = datetime.now(timezone.utc)
        protected = (Vehicle.PriceSource.MANUAL,)
        overwritable = (
            Vehicle.PriceSource.UNKNOWN,
            Vehicle.PriceSource.MOCK,
            Vehicle.PriceSource.HEURISTIC,
            Vehicle.PriceSource.GEMINI,
        )

        matched = 0
        skipped_protected = 0
        not_found = []

        for make, kw, prop, price, note in ANCHORS:
            # icontains en make porque IDAE tiene "Volkswagen Canarias" como
            # marca separada para ciertos modelos (importadora regional).
            qs = (
                Vehicle.objects
                .filter(make__icontains=make, model__icontains=kw, propulsion=prop)
                .order_by("-year", "id")
            )
            row = qs.first()
            if row is None:
                not_found.append((make, kw, prop, note))
                continue

            if row.price_source == Vehicle.PriceSource.MANUAL and row.price_eur:
                skipped_protected += 1
                self.stdout.write(
                    f"  · {make:14s} {kw:14s} {prop:6s} → SKIP (ya manual, "
                    f"id={row.id}, price={row.price_eur} €)"
                )
                continue

            if not dry_run:
                row.price_eur = price
                row.price_source = Vehicle.PriceSource.MANUAL
                row.price_updated_at = now
                row.save(update_fields=["price_eur", "price_source", "price_updated_at"])

            matched += 1
            self.stdout.write(
                f"  ✓ {make:14s} {kw:14s} {prop:6s} → "
                f"id={row.id:5d}  y={row.year}  {price:6d} €  ({note})"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Resumen: {matched} actualizados · {skipped_protected} protegidos · "
            f"{len(not_found)} sin match"
        ))
        if not_found:
            self.stdout.write(self.style.WARNING("Anclas sin match en IDAE:"))
            for make, kw, prop, note in not_found:
                self.stdout.write(f"  - {make} | {kw} | {prop} | {note}")
        if dry_run:
            self.stdout.write(self.style.NOTICE("(dry-run: no se escribió nada)"))
