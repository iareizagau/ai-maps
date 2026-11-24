from datetime import date

import pytest
from django.urls import reverse

from apps.map30.models import MapEntry


@pytest.fixture
def day01(db):
    return MapEntry.objects.create(
        day=1,
        date=date(2026, 11, 1),
        category_slug="points",
        category_name="Points",
        title="Puntos de recarga EV",
        blurb="Test",
        library=MapEntry.Library.MAPLIBRE,
        basemap=MapEntry.Basemap.VOYAGER,
        status=MapEntry.Status.PUBLISHED,
    )


def test_index_renders(client, db):
    resp = client.get(reverse("map30:index"), HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert b"#30DayMapChallenge" in resp.content


def test_day_detail_renders(client, day01):
    resp = client.get(reverse("map30:day_detail", args=[1]), HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert b"Puntos de recarga EV" in resp.content


def test_day_detail_missing_template_404(client, db):
    MapEntry.objects.create(
        day=18,
        date=date(2026, 11, 18),
        category_slug="null",
        category_name="NULL",
        title="NULL",
        template_name="map30/days/__does_not_exist__.html",
    )
    resp = client.get(reverse("map30:day_detail", args=[18]), HTTP_HOST="localhost")
    assert resp.status_code == 404


def test_day01_points_geojson_shape(client, db):
    resp = client.get(reverse("map30:day01_points_geojson"), HTTP_HOST="localhost")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
