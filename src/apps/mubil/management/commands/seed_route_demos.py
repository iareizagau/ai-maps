"""Seed the 5 precomputed EV route plans into :class:`EVRoutePlan`.

Idempotent — re-running overwrites the cached snapshot rather than
duplicating. Picks a sensible default vehicle (the seeded Kia Niro EV when
present) so the persisted `geojson` already has plausible energy / cost
numbers in the admin.

Usage:
  python manage.py seed_route_demos
  python manage.py seed_route_demos --vehicle-id 5
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.mubil.models import Vehicle
from apps.mubil.route import services


class Command(BaseCommand):
    help = "Persist the 5 precomputed mubil route demos into EVRoutePlan."

    def add_arguments(self, parser):
        parser.add_argument(
            "--vehicle-id",
            type=int,
            default=None,
            help=(
                "Use this Vehicle for the cached snapshot. "
                "Defaults to the first BEV named like 'Niro' (seeded demo)."
            ),
        )

    def handle(self, *args, **options):
        vehicle_id = options.get("vehicle_id")
        vehicle = self._resolve_vehicle(vehicle_id)
        n = services.upsert_demo_plans(default_vehicle=vehicle)
        label = (
            f"{vehicle.make} {vehicle.model}" if vehicle else "no vehicle (defaults)"
        )
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {n} route demos against: {label}")
        )

    def _resolve_vehicle(self, vehicle_id):
        if vehicle_id is not None:
            try:
                return Vehicle.objects.get(pk=vehicle_id)
            except Vehicle.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Vehicle id={vehicle_id} not found — seeding without vehicle."
                    )
                )
                return None
        # Prefer the demo Niro EV so the cached numbers are immediately useful.
        v = Vehicle.objects.filter(
            propulsion=Vehicle.Propulsion.BEV,
            model__icontains="Niro",
        ).first()
        if v is not None:
            return v
        return Vehicle.objects.filter(propulsion=Vehicle.Propulsion.BEV).first()
