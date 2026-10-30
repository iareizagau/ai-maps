"""Tests for the AEMET integration (service + endpoint + commands)."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.test import Client

from apps.amenabar.models import AemetStation, Promocion, PromocionClima
from apps.amenabar.services_aemet import (
    _parse_aemet_coord,
    nearest_station,
    store_clima,
    sync_stations,
)

FIX = Path(__file__).parent / "fixtures"
STATIONS = json.loads((FIX / "aemet_stations_sample.json").read_text(encoding="utf-8"))
NORMALS = json.loads((FIX / "aemet_normals_sample.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fake_key(settings):
    settings.AEMET_API_KEY = "test-key"


@pytest.fixture
def promocion_donostia(db):
    # Close to station C001A (Igueldo).
    return Promocion.objects.create(
        slug="demo-donostia",
        nombre="Demo Donostia",
        ciudad="Donostia",
        estado=Promocion.Estado.EN_VENTA,
        source_url="https://example.test/donostia",
        location=Point(-1.984, 43.321, srid=4326),
    )


@pytest.fixture
def promocion_sin_location(db):
    return Promocion.objects.create(
        slug="sin-ubi-aemet",
        nombre="Sin ubicación",
        ciudad="Nada",
        estado=Promocion.Estado.EN_VENTA,
        source_url="https://example.test/sin",
    )


# --------------------------------------------------------------------------- #
# _parse_aemet_coord
# --------------------------------------------------------------------------- #


def test_parse_aemet_coord_latitude_north():
    assert _parse_aemet_coord("431833N") == pytest.approx(43 + 18 / 60 + 33 / 3600, rel=1e-6)


def test_parse_aemet_coord_longitude_west_is_negative():
    v = _parse_aemet_coord("020228W")
    assert v is not None and v < 0
    assert abs(v) == pytest.approx(2 + 2 / 60 + 28 / 3600, rel=1e-6)


def test_parse_aemet_coord_bad_input():
    assert _parse_aemet_coord("") is None
    assert _parse_aemet_coord("not a coord") is None


# --------------------------------------------------------------------------- #
# _aemet_get (envelope 2-step)
# --------------------------------------------------------------------------- #


def _mock_envelope(data_payload):
    """Return a side_effect for requests.get that follows AEMET's 2-step pattern."""
    envelope = {"estado": 200, "datos": "https://opendata.aemet.es/opendata/sh/mock.json", "metadatos": ""}
    calls = []

    def side_effect(url, **kwargs):
        resp = type("R", (), {})()
        resp.raise_for_status = lambda: None
        if url.startswith("https://opendata.aemet.es/opendata/api"):
            resp.json = lambda: envelope
        else:
            resp.json = lambda: data_payload
        calls.append(url)
        return resp

    return side_effect, calls


def test_aemet_get_follows_two_step_envelope(db):
    side_effect, calls = _mock_envelope(STATIONS)
    with patch("apps.amenabar.services_aemet.requests.get", side_effect=side_effect):
        n = sync_stations()

    assert n == 3
    # First call is to AEMET API, second to the signed "datos" URL
    assert calls[0].startswith("https://opendata.aemet.es/opendata/api")
    assert calls[1] == "https://opendata.aemet.es/opendata/sh/mock.json"


# --------------------------------------------------------------------------- #
# sync_stations
# --------------------------------------------------------------------------- #


def test_sync_stations_idempotent(db):
    side_effect, _ = _mock_envelope(STATIONS)
    with patch("apps.amenabar.services_aemet.requests.get", side_effect=side_effect):
        n1 = sync_stations()
        n2 = sync_stations()
    assert n1 == n2 == 3
    assert AemetStation.objects.count() == 3


def test_sync_stations_without_key(db, settings):
    settings.AEMET_API_KEY = ""
    with pytest.raises(RuntimeError, match="AEMET_API_KEY"):
        sync_stations()


# --------------------------------------------------------------------------- #
# nearest_station
# --------------------------------------------------------------------------- #


def test_nearest_station_within_50km_returns_closest(db):
    side_effect, _ = _mock_envelope(STATIONS)
    with patch("apps.amenabar.services_aemet.requests.get", side_effect=side_effect):
        sync_stations()
    # Point near Donostia (close to C001A, far from C002B / C003C)
    s = nearest_station(Point(-1.984, 43.321, srid=4326))
    assert s is not None
    assert s.idema == "C001A"


def test_nearest_station_beyond_50km_returns_none(db):
    AemetStation.objects.create(
        idema="LEJOS",
        nombre="Lejana",
        location=Point(0.0, 0.0, srid=4326),  # Golfo de Guinea
    )
    s = nearest_station(Point(-1.984, 43.321, srid=4326))  # Donostia
    assert s is None


# --------------------------------------------------------------------------- #
# store_clima
# --------------------------------------------------------------------------- #


def test_store_clima_persists_three_series(promocion_donostia):
    stations_side, _ = _mock_envelope(STATIONS)
    with patch("apps.amenabar.services_aemet.requests.get", side_effect=stations_side):
        sync_stations()

    normals_side, _ = _mock_envelope(NORMALS)
    with patch("apps.amenabar.services_aemet.requests.get", side_effect=normals_side):
        c = store_clima(promocion_donostia)

    assert c is not None
    assert len(c.temp_mean) == 12
    assert len(c.precipitation) == 12
    assert len(c.sun_hours) == 12
    assert c.temp_mean[0] == pytest.approx(8.2)
    assert c.precipitation[11] == pytest.approx(146.1)
    assert c.sun_hours[6] == pytest.approx(170.1)
    assert c.station.idema == "C001A"
    assert c.period_label == "1991-2020"


def test_store_clima_without_location_returns_none(promocion_sin_location):
    assert store_clima(promocion_sin_location) is None
    assert PromocionClima.objects.count() == 0


def test_store_clima_without_nearby_station_returns_none(promocion_donostia):
    # No stations in DB → nearest returns None
    assert AemetStation.objects.count() == 0
    assert store_clima(promocion_donostia) is None
    assert PromocionClima.objects.count() == 0


def test_store_clima_handles_network_error(promocion_donostia):
    stations_side, _ = _mock_envelope(STATIONS)
    with patch("apps.amenabar.services_aemet.requests.get", side_effect=stations_side):
        sync_stations()
    with patch(
        "apps.amenabar.services_aemet.requests.get",
        side_effect=requests.RequestException("boom"),
    ):
        assert store_clima(promocion_donostia) is None
    assert PromocionClima.objects.count() == 0


# --------------------------------------------------------------------------- #
# promocion_pois endpoint
# --------------------------------------------------------------------------- #


def _seed_clima(promocion):
    station = AemetStation.objects.create(
        idema="SEED",
        nombre="Seed Station",
        location=Point(-1.984, 43.321, srid=4326),
    )
    return PromocionClima.objects.create(
        promocion=promocion,
        station=station,
        distance_m=1500,
        temp_mean=[8.2] * 12,
        precipitation=[100.0] * 12,
        sun_hours=[120.0] * 12,
        period_label="1991-2020",
        raw_json={},
    )


def test_promocion_pois_includes_clima_block(promocion_donostia):
    _seed_clima(promocion_donostia)
    resp = Client(HTTP_HOST="localhost").get(
        f"/amenabar/promociones/{promocion_donostia.slug}/pois.json"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["clima"] is not None
    assert body["clima"]["station"] == "Seed Station"
    assert body["clima"]["distance_m"] == 1500
    assert body["clima"]["period"] == "1991-2020"
    assert len(body["clima"]["temp_mean"]) == 12
    # Base contract untouched
    assert "pois" in body and "nearest" in body and "promocion" in body and "solar" in body


def test_promocion_pois_clima_null_when_missing(promocion_donostia):
    resp = Client(HTTP_HOST="localhost").get(
        f"/amenabar/promociones/{promocion_donostia.slug}/pois.json"
    )
    assert resp.status_code == 200
    assert resp.json()["clima"] is None


# --------------------------------------------------------------------------- #
# backfill_aemet_clima command
# --------------------------------------------------------------------------- #


def test_backfill_aemet_clima_aborts_without_inventory(db, promocion_donostia):
    out = StringIO()
    err = StringIO()
    call_command("backfill_aemet_clima", stdout=out, stderr=err)
    assert "inventario AEMET vacío" in err.getvalue()
    assert PromocionClima.objects.count() == 0


def test_backfill_aemet_clima_skips_existing(promocion_donostia):
    _seed_clima(promocion_donostia)
    with (
        patch("apps.amenabar.services_aemet.store_clima") as store_mock,
        patch("apps.amenabar.management.commands.backfill_aemet_clima.time.sleep"),
    ):
        call_command("backfill_aemet_clima", stdout=StringIO())
    assert store_mock.call_count == 0


def test_backfill_aemet_clima_force_recomputes(promocion_donostia):
    seeded = _seed_clima(promocion_donostia)
    # Pre-seed inventory so the "empty inventory" guard passes.
    original_dist = seeded.distance_m

    # Build what store_clima would return on force
    def fake_store(promocion):
        pc, _ = PromocionClima.objects.update_or_create(
            promocion=promocion,
            defaults={
                "station": seeded.station,
                "distance_m": 9999,
                "temp_mean": [1.0] * 12,
                "precipitation": [1.0] * 12,
                "sun_hours": [1.0] * 12,
                "period_label": "1991-2020",
                "raw_json": {},
            },
        )
        return pc

    with (
        patch(
            "apps.amenabar.management.commands.backfill_aemet_clima.store_clima",
            side_effect=fake_store,
        ) as mock,
        patch("apps.amenabar.management.commands.backfill_aemet_clima.time.sleep"),
    ):
        call_command("backfill_aemet_clima", "--force", stdout=StringIO())

    assert mock.call_count == 1
    assert PromocionClima.objects.get(promocion=promocion_donostia).distance_m == 9999
    assert original_dist == 1500  # sanity
