"""Seed Vehicle 'ICE genérico medio'.

Lo usa Path C del Step 1 del advisor (modo "recomiéndame"): el usuario no
indica su coche actual, así que comparamos contra un ICE medio del catálogo
español 2020 (PVP ~22.000 €, 6,5 L/100 gasolina, etiqueta C).

Buscable por (make='Genérico', model='Coche ICE medio', variant='', year=2020)
gracias al constraint parcial `vehicle_manual_natural_unique` (idae_id NULL).
"""

from django.db import migrations
from django.utils import timezone

SENTINEL = dict(make="Genérico", model="Coche ICE medio", variant="", year=2020)


def seed(apps, schema_editor):
    Vehicle = apps.get_model("mubil", "Vehicle")
    Vehicle.objects.update_or_create(
        idae_id=None,
        **SENTINEL,
        defaults=dict(
            propulsion="ICE",
            dgt_label="C",
            category="M1",
            segment="medio",
            mtma_kg=1500,
            range_wltp_km=None,
            consumption_kwh_100km=None,
            consumption_l_100km=6.5,
            co2_g_km_min=148,
            co2_g_km_max=160,
            price_eur=22000,
            price_source="manual",
            price_updated_at=timezone.now(),
            source_url="",
        ),
    )


def unseed(apps, schema_editor):
    Vehicle = apps.get_model("mubil", "Vehicle")
    Vehicle.objects.filter(idae_id=None, **SENTINEL).delete()


class Migration(migrations.Migration):
    dependencies = [("mubil", "0011_vehicle_price_source")]
    operations = [migrations.RunPython(seed, reverse_code=unseed)]
