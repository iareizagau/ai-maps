"""Tests for the OpenAQ integration (service + endpoint + command + constraint)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction
from django.test import Client

from apps.amenabar.models import AirQualityStation
from apps.amenabar.services_openaq import (
    OPENAQ_BBOX_SPAIN,
    fetch_openaq_locations_page,
    sync_openaq_spain,
)

FIX = Path(__file__).parent / "fixtures"
PAGE1 = json.loads((FIX / "openaq_locations_page1.json").read_text(encoding="utf-8"))
PAGE2 = json.loads((FIX / "openaq_locations_page2.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fake_key(settings):
    settings.OPENAQ_API_KEY = "test-key"


def _mock_pages(pages: list[dict]):
    """Return a side_effect for requests.get that returns each page in order,
    then empty pages forever (so sync_openaq_spain stops naturally)."""
    calls = []
    seq = list(pages)
    empty = {"meta": {"found": sum(len(p.get("results", [])) for p in pages)}, "results": []}

    def side_effect(url, **kwargs):
        calls.append({"url": url, "params": kwargs.get("params", {}), "headers": kwargs.get("headers", {})})
        resp = type("R", (), {})()
        resp.raise_for_status = lambda: None
        resp.status_code = 200
        payload = seq.pop(0) if seq else empty
        resp.json = lambda: payload
        return resp

    return side_effect, calls


# --------------------------------------------------------------------------- #
# fetch_openaq_locations_page
# --------------------------------------------------------------------------- #


def test_fetch_openaq_locations_page_sends_api_key_header():
    side_effect, calls = _mock_pages([PAGE1])
    with patch("apps.amenabar.services_openaq.requests.get", side_effect=side_effect):
        data = fetch_openaq_locations_page(OPENAQ_BBOX_SPAIN, page=1)

    assert data == PAGE1
    assert calls[0]["headers"]["X-API-Key"] == "test-key"
    assert "bbox" in calls[0]["params"]
    assert calls[0]["params"]["page"] == 1


def test_fetch_openaq_locations_page_without_key(db, settings):
    settings.OPENAQ_API_KEY = ""
    with pytest.raises(RuntimeError, match="OPENAQ_API_KEY"):
        fetch_openaq_locations_page(OPENAQ_BBOX_SPAIN, page=1)


# --------------------------------------------------------------------------- #
# sync_openaq_spain
# --------------------------------------------------------------------------- #


def test_sync_openaq_spain_filters_non_spain(db):
    side_effect, _ = _mock_pages([PAGE1])
    with (
        patch("apps.amenabar.services_openaq.requests.get", side_effect=side_effect),
        patch("apps.amenabar.services_openaq.time.sleep"),
    ):
        n = sync_openaq_spain()
    # PAGE1 has 2 ES + 1 FR; the FR one must be rejected.
    assert n == 2
    assert AirQualityStation.objects.count() == 2
    assert set(AirQualityStation.objects.values_list("country", flat=True)) == {"ES"}


def test_sync_openaq_spain_persists_latest_readings(db):
    side_effect, _ = _mock_pages([PAGE1])
    with (
        patch("apps.amenabar.services_openaq.requests.get", side_effect=side_effect),
        patch("apps.amenabar.services_openaq.time.sleep"),
    ):
        sync_openaq_spain()
    donostia = AirQualityStation.objects.get(openaq_id="1001")
    assert donostia.pm25 == Decimal("7.4")
    assert donostia.no2 == Decimal("18.2")
    assert donostia.pm10 is None
    assert donostia.measurements_at is not None  # read from PM2.5 / NO2 timestamp

    madrid = AirQualityStation.objects.get(openaq_id="1002")
    assert madrid.pm25 == Decimal("42.1")
    assert madrid.pm10 == Decimal("65.0")


def test_sync_openaq_spain_paginates(db):
    # Two pages, first full-sized would require pagination; here we trust that
    # the service stops once a smaller page arrives (see len < limit break).
    side_effect, calls = _mock_pages([PAGE1, PAGE2])
    with (
        patch("apps.amenabar.services_openaq.requests.get", side_effect=side_effect),
        patch("apps.amenabar.services_openaq.time.sleep"),
    ):
        n = sync_openaq_spain()
    # First page returns 3 results (< limit 1000) → service stops. We expect
    # it NOT to fetch page 2 under the current stopping condition. 2 ES rows.
    assert n == 2
    assert len(calls) == 1


def test_sync_openaq_spain_idempotent(db):
    side_effect1, _ = _mock_pages([PAGE1])
    with (
        patch("apps.amenabar.services_openaq.requests.get", side_effect=side_effect1),
        patch("apps.amenabar.services_openaq.time.sleep"),
    ):
        n1 = sync_openaq_spain()
    side_effect2, _ = _mock_pages([PAGE1])
    with (
        patch("apps.amenabar.services_openaq.requests.get", side_effect=side_effect2),
        patch("apps.amenabar.services_openaq.time.sleep"),
    ):
        n2 = sync_openaq_spain()
    assert n1 == n2 == 2
    assert AirQualityStation.objects.count() == 2


def test_sync_openaq_spain_without_key_raises(db, settings):
    settings.OPENAQ_API_KEY = ""
    with pytest.raises(RuntimeError, match="OPENAQ_API_KEY"):
        sync_openaq_spain()


def test_sync_openaq_spain_handles_network_error(db):
    with (
        patch(
            "apps.amenabar.services_openaq.requests.get",
            side_effect=requests.RequestException("boom"),
        ),
        patch("apps.amenabar.services_openaq.time.sleep"),
    ):
        n = sync_openaq_spain()
    assert n == 0
    assert AirQualityStation.objects.count() == 0


# --------------------------------------------------------------------------- #
# Model constraint
# --------------------------------------------------------------------------- #


def test_country_check_constraint_rejects_non_es(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        AirQualityStation.objects.create(
            openaq_id="FR-X",
            name="Bordeaux",
            country="FR",
            location=Point(-0.579, 44.837, srid=4326),
        )


# --------------------------------------------------------------------------- #
# airquality endpoint
# --------------------------------------------------------------------------- #


def _seed_station(**kw):
    defaults = {
        "openaq_id": "ES-SEED",
        "name": "Seed",
        "city": "Donostia",
        "country": "ES",
        "location": Point(-1.985, 43.321, srid=4326),
        "pm25": Decimal("8.5"),
    }
    defaults.update(kw)
    return AirQualityStation.objects.create(**defaults)


def test_airquality_endpoint_returns_stations(db):
    _seed_station()
    _seed_station(openaq_id="ES-SEED2", name="Otra", pm25=None, pm10=Decimal("30.0"))
    resp = Client(HTTP_HOST="localhost").get("/amenabar/airquality.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "stations" in body
    assert len(body["stations"]) == 2
    first = body["stations"][0]
    assert set(first.keys()) >= {"id", "name", "city", "lat", "lon", "pm25", "pm10", "no2", "o3", "measurements_at"}


def test_airquality_endpoint_empty_cache_returns_empty_list(db):
    resp = Client(HTTP_HOST="localhost").get("/amenabar/airquality.json")
    assert resp.status_code == 200
    assert resp.json() == {"stations": []}


# --------------------------------------------------------------------------- #
# promocion_pois unchanged
# --------------------------------------------------------------------------- #


def test_promocion_pois_does_not_include_air_quality(db):
    from apps.amenabar.models import Promocion

    p = Promocion.objects.create(
        slug="demo-air",
        nombre="Demo",
        ciudad="Donostia",
        estado=Promocion.Estado.EN_VENTA,
        source_url="https://example.test/demo",
        location=Point(-1.985, 43.321, srid=4326),
    )
    _seed_station()  # should NOT appear in the per-promocion payload
    resp = Client(HTTP_HOST="localhost").get(f"/amenabar/promociones/{p.slug}/pois.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "air_quality" not in body
    assert "airquality" not in body
    assert "stations" not in body
