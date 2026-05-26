"""Seed mínimo para el demo de `advisor` en F0.

- 3 vehículos EV (entry, mid, premium) + 3 combustión (gasolina, híbrido, diésel).
- ~6 cargadores en Donostia y entorno (cubre CP 20018).

Datos representativos pero NO oficiales. Sustituir por seed desde DGT
matriculaciones + investigacoches.es + OpenData Euskadi cuando esté wireado.

Uso:
    docker exec maps_web python manage.py seed_advisor_demo
"""

from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.mubil.models import ChargingStation, Vehicle


VEHICLES = [
    # Combustión
    {
        "make": "Volkswagen", "model": "Golf 1.6 TDI", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("4.9"),
        "price_eur": 28_500,
        "source_url": "https://investigacoches.es",
    },
    {
        "make": "Seat", "model": "Ibiza 1.0 TSI", "year": 2024,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.6"),
        "price_eur": 19_900,
        "source_url": "https://investigacoches.es",
    },
    {
        "make": "Toyota", "model": "Corolla 1.8 Hybrid", "year": 2024,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("4.5"),
        "price_eur": 27_500,
        "source_url": "https://investigacoches.es",
    },
    # Eléctricos
    {
        "make": "Dacia", "model": "Spring 65", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("26.8"),
        "range_wltp_km": 220,
        "consumption_kwh_100km": Decimal("13.2"),
        "price_eur": 18_500,
        "source_url": "https://investigacoches.es",
    },
    {
        "make": "Kia", "model": "Niro EV", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("64.8"),
        "range_wltp_km": 460,
        "consumption_kwh_100km": Decimal("16.2"),
        "price_eur": 41_500,
        "source_url": "https://investigacoches.es",
    },
    {
        "make": "Tesla", "model": "Model Y RWD", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("60.0"),
        "range_wltp_km": 455,
        "consumption_kwh_100km": Decimal("15.8"),
        "price_eur": 45_000,
        "source_url": "https://investigacoches.es",
    },
]

# Cargadores demo cerca de Donostia (CP 20018)
CHARGERS = [
    {
        "external_id": "demo-ocm-001", "source": "demo",
        "operator": "Repsol", "address": "Aiete, Donostia",
        "lat": 43.296, "lon": -1.999, "power_kw": Decimal("22"),
        "connectors": [{"type": "Type 2", "kw": 22}],
    },
    {
        "external_id": "demo-ocm-002", "source": "demo",
        "operator": "Iberdrola bP", "address": "Plaza Pío XII, Donostia",
        "lat": 43.301, "lon": -1.985, "power_kw": Decimal("50"),
        "connectors": [{"type": "CCS2", "kw": 50}],
    },
    {
        "external_id": "demo-ocm-003", "source": "demo",
        "operator": "Endesa X", "address": "Anoeta, Donostia",
        "lat": 43.302, "lon": -1.989, "power_kw": Decimal("150"),
        "connectors": [{"type": "CCS2", "kw": 150}],
    },
    {
        "external_id": "demo-ocm-004", "source": "demo",
        "operator": "Ionity", "address": "AP-8 km 8 — Astigarraga",
        "lat": 43.286, "lon": -1.948, "power_kw": Decimal("350"),
        "connectors": [{"type": "CCS2", "kw": 350}],
    },
    {
        "external_id": "demo-ocm-005", "source": "demo",
        "operator": "Wenea", "address": "Ondarreta parking, Donostia",
        "lat": 43.318, "lon": -2.025, "power_kw": Decimal("22"),
        "connectors": [{"type": "Type 2", "kw": 22}],
    },
    {
        "external_id": "demo-ocm-006", "source": "demo",
        "operator": "Tesla Supercharger", "address": "Centro Comercial Garbera",
        "lat": 43.305, "lon": -1.973, "power_kw": Decimal("250"),
        "connectors": [{"type": "CCS2", "kw": 250}],
    },
]


class Command(BaseCommand):
    help = "Seed demo data for the advisor module (6 vehicles + 6 chargers)."

    @transaction.atomic
    def handle(self, *args, **options):
        for spec in VEHICLES:
            obj, created = Vehicle.objects.update_or_create(
                make=spec["make"], model=spec["model"], year=spec["year"],
                defaults={k: v for k, v in spec.items() if k not in ("make", "model", "year")},
            )
            self.stdout.write(f"{'+' if created else '='} Vehicle {obj}")

        for spec in CHARGERS:
            geom = Point(float(spec["lon"]), float(spec["lat"]), srid=4326)
            obj, created = ChargingStation.objects.update_or_create(
                external_id=spec["external_id"], source=spec["source"],
                defaults={
                    "operator": spec["operator"],
                    "address": spec["address"],
                    "geom": geom,
                    "power_kw": spec["power_kw"],
                    "connectors": spec["connectors"],
                },
            )
            self.stdout.write(f"{'+' if created else '='} Charger {obj}")

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete — {Vehicle.objects.count()} vehicles, "
            f"{ChargingStation.objects.count()} chargers."
        ))
