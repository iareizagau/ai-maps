"""Tests for the PVGIS integration (service + endpoint + command)."""

from __future__ import annotations

import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import Client

from apps.amenabar.models import Promocion, SolarPotential
from apps.amenabar.services_pvgis import fetch_pvgis, store_solar

FIXTURE = Path(__file__).parent / "fixtures" / "pvgis_sample.json"


@pytest.fixture
def pvgis_payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def promocion_with_location(db):
    return Promocion.objects.create(
        slug="aires-de-arganda",
        nombre="Aires de Arganda",
        ciudad="Arganda del Rey",
        estado=Promocion.Estado.EN_VENTA,
        source_url="https://example.test/aires",
        location=Point(-1.984, 43.321, srid=4326),
    )


@pytest.fixture
def promocion_without_location(db):
    return Promocion.objects.create(
        slug="sin-ubicacion",
        nombre="Sin ubicación",
        ciudad="Ninguna",
        estado=Promocion.Estado.EN_VENTA,
        source_url="https://example.test/sin",
    )


# --------------------------------------------------------------------------- #
# fetch_pvgis
# --------------------------------------------------------------------------- #


def test_fetch_pvgis_parses_monthly(pvgis_payload):
    with patch("apps.amenabar.services_pvgis.requests.get") as m:
        m.return_value.status_code = 200
        m.return_value.json.return_value = pvgis_payload
        m.return_value.raise_for_status.return_value = None

        data = fetch_pvgis(43.321, -1.984)

    assert data == pvgis_payload
    assert len(data["outputs"]["monthly"]["fixed"]) == 12
    # Pass-through: the service does not transform here.
    _, kwargs = m.call_args
    assert kwargs["params"]["lat"] == 43.321
    assert kwargs["params"]["lon"] == -1.984
    assert kwargs["params"]["peakpower"] == 1


# --------------------------------------------------------------------------- #
# store_solar
# --------------------------------------------------------------------------- #


def test_store_solar_idempotent(promocion_with_location, pvgis_payload):
    with patch("apps.amenabar.services_pvgis.fetch_pvgis", return_value=pvgis_payload):
        first = store_solar(promocion_with_location)
        second = store_solar(promocion_with_location)

    assert first is not None and second is not None
    assert SolarPotential.objects.filter(promocion=promocion_with_location).count() == 1
    assert first.pk == second.pk
    assert first.kwh_kwp_year == Decimal("1388.78")
    assert len(first.monthly_json) == 12
    assert first.monthly_json[0] == 70.1


def test_store_solar_without_location_returns_none(promocion_without_location):
    assert store_solar(promocion_without_location) is None
    assert SolarPotential.objects.count() == 0


def test_store_solar_handles_network_error(promocion_with_location):
    with patch(
        "apps.amenabar.services_pvgis.fetch_pvgis",
        side_effect=requests.RequestException("boom"),
    ):
        assert store_solar(promocion_with_location) is None
    assert SolarPotential.objects.count() == 0


# --------------------------------------------------------------------------- #
# promocion_pois endpoint
# --------------------------------------------------------------------------- #


def test_promocion_pois_includes_solar_block(promocion_with_location, pvgis_payload):
    with patch("apps.amenabar.services_pvgis.fetch_pvgis", return_value=pvgis_payload):
        store_solar(promocion_with_location)

    resp = Client(HTTP_HOST="localhost").get(
        f"/amenabar/promociones/{promocion_with_location.slug}/pois.json"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["solar"] is not None
    assert body["solar"]["kwh_kwp_year"] == pytest.approx(1388.78)
    assert len(body["solar"]["monthly"]) == 12
    # Base contract untouched
    assert "pois" in body and "nearest" in body and "promocion" in body


def test_promocion_pois_null_when_missing(promocion_with_location):
    resp = Client(HTTP_HOST="localhost").get(
        f"/amenabar/promociones/{promocion_with_location.slug}/pois.json"
    )
    assert resp.status_code == 200
    assert resp.json()["solar"] is None


# --------------------------------------------------------------------------- #
# backfill_pvgis command
# --------------------------------------------------------------------------- #


def test_backfill_pvgis_skips_existing(promocion_with_location, pvgis_payload):
    # Seed a SolarPotential directly so the command sees it as "already done".
    SolarPotential.objects.create(
        promocion=promocion_with_location,
        kwh_kwp_year=Decimal("999.99"),
        irradiation_year=Decimal("1000.00"),
        monthly_json=[0] * 12,
        raw_json={},
    )
    with (
        patch("apps.amenabar.services_pvgis.fetch_pvgis") as fetch_mock,
        patch("apps.amenabar.management.commands.backfill_pvgis.time.sleep"),
    ):
        call_command("backfill_pvgis", stdout=StringIO())

    assert fetch_mock.call_count == 0
    # Value preserved
    sp = SolarPotential.objects.get(promocion=promocion_with_location)
    assert sp.kwh_kwp_year == Decimal("999.99")


def test_backfill_pvgis_force_recomputes(promocion_with_location, pvgis_payload):
    SolarPotential.objects.create(
        promocion=promocion_with_location,
        kwh_kwp_year=Decimal("999.99"),
        irradiation_year=Decimal("1000.00"),
        monthly_json=[0] * 12,
        raw_json={},
    )
    with (
        patch(
            "apps.amenabar.services_pvgis.fetch_pvgis",
            return_value=pvgis_payload,
        ) as fetch_mock,
        patch("apps.amenabar.management.commands.backfill_pvgis.time.sleep"),
    ):
        call_command("backfill_pvgis", "--force", stdout=StringIO())

    assert fetch_mock.call_count == 1
    sp = SolarPotential.objects.get(promocion=promocion_with_location)
    assert sp.kwh_kwp_year == Decimal("1388.78")
