"""Smoke tests for mubil models. PROPUESTA.md §18 — write real tests in F1."""

from django.test import TestCase

from apps.mubil.models import Vehicle


class VehicleModelTests(TestCase):
    def test_str_format(self):
        v = Vehicle(make='Kia', model='Niro EV', year=2025, propulsion=Vehicle.Propulsion.BEV)
        self.assertEqual(str(v), 'Kia Niro EV (2025)')
