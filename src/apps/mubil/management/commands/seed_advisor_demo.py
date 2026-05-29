"""Seed del demo `advisor`.

~36 vehículos representativos del top de matriculaciones DGT 2024-25 + segmento
EH relevante (gasolina, diésel, HEV, PHEV, BEV) — suficiente profundidad para
que el jurado vea varios escenarios de payback.

Datos de consumo / precio son representativos pero NO oficiales. Sustituir
por seed desde DGT + investigacoches.es + OpenData Euskadi cuando esté
wireado.

Uso:
    docker exec maps_web python manage.py seed_advisor_demo
"""

from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.mubil.models import ChargingStation, Vehicle


# ──────────────────────────── gasolina ────────────────────────────
ICE_VEHICLES = [
    {
        "make": "Volkswagen", "model": "Golf 1.6 TDI", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("4.9"), "price_eur": 28_500,
    },
    {
        "make": "Seat", "model": "Ibiza 1.0 TSI", "year": 2024,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.6"), "price_eur": 19_900,
    },
    {
        "make": "Dacia", "model": "Sandero 1.0 TCe", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.4"), "price_eur": 13_900,
    },
    {
        "make": "Renault", "model": "Captur 1.0 TCe", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.9"), "price_eur": 22_300,
    },
    {
        "make": "Peugeot", "model": "208 PureTech 100", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.2"), "price_eur": 20_500,
    },
    {
        "make": "Citroën", "model": "C3 PureTech 83", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.5"), "price_eur": 17_900,
    },
    {
        "make": "Hyundai", "model": "Tucson 1.6 T-GDI", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("7.2"), "price_eur": 30_900,
    },
    {
        "make": "Kia", "model": "Sportage 1.6 T-GDI", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("7.0"), "price_eur": 29_500,
    },
    {
        "make": "Seat", "model": "Arona 1.0 TSI", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.7"), "price_eur": 22_900,
    },
    {
        "make": "Toyota", "model": "Yaris 1.5 VVT-i", "year": 2025,
        "propulsion": Vehicle.Propulsion.ICE,
        "consumption_l_100km": Decimal("5.3"), "price_eur": 19_800,
    },
]

# ──────────────────────────── diésel ────────────────────────────
DIESEL_VEHICLES = [
    {
        "make": "Volkswagen", "model": "Tiguan 2.0 TDI", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("6.1"), "price_eur": 38_900,
    },
    {
        "make": "Skoda", "model": "Octavia 2.0 TDI", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("4.7"), "price_eur": 28_900,
    },
    {
        "make": "Ford", "model": "Focus 1.5 EcoBlue", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("4.6"), "price_eur": 26_500,
    },
    {
        "make": "BMW", "model": "320d", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("5.0"), "price_eur": 48_900,
    },
    {
        "make": "Peugeot", "model": "3008 BlueHDi 130", "year": 2024,
        "propulsion": Vehicle.Propulsion.DIESEL,
        "consumption_l_100km": Decimal("5.2"), "price_eur": 33_500,
    },
]

# ──────────────────────────── híbridos (HEV) ────────────────────────────
HEV_VEHICLES = [
    {
        "make": "Toyota", "model": "Corolla 1.8 Hybrid", "year": 2024,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("4.5"), "price_eur": 27_500,
    },
    {
        "make": "Toyota", "model": "Yaris Cross 1.5 Hybrid", "year": 2025,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("4.4"), "price_eur": 24_500,
    },
    {
        "make": "Toyota", "model": "C-HR 1.8 Hybrid", "year": 2025,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("4.8"), "price_eur": 32_500,
    },
    {
        "make": "Renault", "model": "Clio E-Tech Hybrid", "year": 2025,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("4.3"), "price_eur": 22_900,
    },
    {
        "make": "Honda", "model": "CR-V e:HEV", "year": 2024,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("6.4"), "price_eur": 42_900,
    },
    {
        "make": "Hyundai", "model": "Kona Hybrid", "year": 2025,
        "propulsion": Vehicle.Propulsion.HEV,
        "consumption_l_100km": Decimal("4.7"), "price_eur": 26_900,
    },
]

# ──────────────────────────── PHEV ────────────────────────────
PHEV_VEHICLES = [
    {
        "make": "Volkswagen", "model": "Tiguan eHybrid", "year": 2025,
        "propulsion": Vehicle.Propulsion.PHEV,
        "battery_kwh": Decimal("19.7"), "range_wltp_km": 100,
        "consumption_l_100km": Decimal("1.4"), "consumption_kwh_100km": Decimal("19.5"),
        "price_eur": 46_900,
    },
    {
        "make": "Hyundai", "model": "Tucson PHEV", "year": 2025,
        "propulsion": Vehicle.Propulsion.PHEV,
        "battery_kwh": Decimal("13.8"), "range_wltp_km": 62,
        "consumption_l_100km": Decimal("1.6"), "consumption_kwh_100km": Decimal("17.7"),
        "price_eur": 39_500,
    },
    {
        "make": "BMW", "model": "330e", "year": 2025,
        "propulsion": Vehicle.Propulsion.PHEV,
        "battery_kwh": Decimal("19.5"), "range_wltp_km": 95,
        "consumption_l_100km": Decimal("1.7"), "consumption_kwh_100km": Decimal("18.3"),
        "price_eur": 56_900,
    },
    {
        "make": "Cupra", "model": "Formentor VZ e-Hybrid", "year": 2025,
        "propulsion": Vehicle.Propulsion.PHEV,
        "battery_kwh": Decimal("19.7"), "range_wltp_km": 100,
        "consumption_l_100km": Decimal("1.5"), "consumption_kwh_100km": Decimal("19.9"),
        "price_eur": 50_500,
    },
]

# ──────────────────────────── BEV ────────────────────────────
BEV_VEHICLES = [
    {
        "make": "Dacia", "model": "Spring 65", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("26.8"), "range_wltp_km": 220,
        "consumption_kwh_100km": Decimal("13.2"), "price_eur": 18_500,
    },
    {
        "make": "Kia", "model": "Niro EV", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("64.8"), "range_wltp_km": 460,
        "consumption_kwh_100km": Decimal("16.2"), "price_eur": 41_500,
    },
    {
        "make": "Tesla", "model": "Model Y RWD", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("60.0"), "range_wltp_km": 455,
        "consumption_kwh_100km": Decimal("15.8"), "price_eur": 45_000,
    },
    {
        "make": "Tesla", "model": "Model 3 RWD", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("60.0"), "range_wltp_km": 513,
        "consumption_kwh_100km": Decimal("13.2"), "price_eur": 42_990,
    },
    {
        "make": "Volkswagen", "model": "ID.3 Pro", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("58.0"), "range_wltp_km": 426,
        "consumption_kwh_100km": Decimal("15.0"), "price_eur": 39_900,
    },
    {
        "make": "Volkswagen", "model": "ID.4 Pro", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("77.0"), "range_wltp_km": 533,
        "consumption_kwh_100km": Decimal("16.2"), "price_eur": 47_900,
    },
    {
        "make": "Hyundai", "model": "Kona Electric 65", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("65.4"), "range_wltp_km": 514,
        "consumption_kwh_100km": Decimal("14.7"), "price_eur": 38_900,
    },
    {
        "make": "Hyundai", "model": "Ioniq 5 RWD", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("77.4"), "range_wltp_km": 507,
        "consumption_kwh_100km": Decimal("16.7"), "price_eur": 45_900,
    },
    {
        "make": "Cupra", "model": "Born 58", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("58.0"), "range_wltp_km": 424,
        "consumption_kwh_100km": Decimal("15.5"), "price_eur": 38_900,
    },
    {
        "make": "Renault", "model": "Mégane E-Tech EV60", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("60.0"), "range_wltp_km": 470,
        "consumption_kwh_100km": Decimal("14.4"), "price_eur": 36_900,
    },
    {
        "make": "Peugeot", "model": "e-208 GT 50", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("50.0"), "range_wltp_km": 362,
        "consumption_kwh_100km": Decimal("15.0"), "price_eur": 33_900,
    },
    {
        "make": "MG", "model": "MG4 Long Range", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("64.0"), "range_wltp_km": 450,
        "consumption_kwh_100km": Decimal("15.5"), "price_eur": 29_990,
    },
    {
        "make": "BYD", "model": "Atto 3", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("60.5"), "range_wltp_km": 420,
        "consumption_kwh_100km": Decimal("16.0"), "price_eur": 35_500,
    },
    {
        "make": "BMW", "model": "i4 eDrive40", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("83.9"), "range_wltp_km": 590,
        "consumption_kwh_100km": Decimal("16.1"), "price_eur": 60_900,
    },
    {
        "make": "Mercedes-Benz", "model": "EQA 250", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("66.5"), "range_wltp_km": 426,
        "consumption_kwh_100km": Decimal("17.8"), "price_eur": 51_900,
    },
    {
        "make": "Citroën", "model": "ë-C4 50", "year": 2025,
        "propulsion": Vehicle.Propulsion.BEV,
        "battery_kwh": Decimal("50.0"), "range_wltp_km": 357,
        "consumption_kwh_100km": Decimal("16.6"), "price_eur": 31_900,
    },
]

VEHICLES = ICE_VEHICLES + DIESEL_VEHICLES + HEV_VEHICLES + PHEV_VEHICLES + BEV_VEHICLES

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
    help = "Seed demo data for the advisor module (~36 vehicles + 6 chargers)."

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
