"""Tests for the match-maker (extract → rank → explain)."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.gis.geos import Point
from django.test import Client

from apps.amenabar.models import POI, AirQualityStation, Promocion, SolarPotential
from apps.amenabar.services_match import (
    MatchPreferences,
    _extract_keyword_fallback,
    extract_preferences,
    generate_explanation,
    rank_promociones,
)


@pytest.fixture(autouse=True)
def _fake_gemini_key(settings):
    settings.GEMINI_API_KEY = "test-key"
    # Ensure ladder is non-empty regardless of local .env
    settings.GEMINI_GENERATION_FALLBACK_MODELS = ["gemini-test-model"]


def _mk_promo(slug, estado=Promocion.Estado.EN_VENTA, lat=43.321, lon=-1.985, ciudad="Donostia", **kw):
    return Promocion.objects.create(
        slug=slug,
        nombre=slug.replace("-", " ").title(),
        ciudad=ciudad,
        estado=estado,
        source_url=f"https://example.test/{slug}",
        location=Point(lon, lat, srid=4326),
        **kw,
    )


def _mk_solar(promocion, kwh):
    return SolarPotential.objects.create(
        promocion=promocion,
        kwh_kwp_year=Decimal(str(kwh)),
        irradiation_year=Decimal("1500.00"),
        monthly_json=[kwh / 12] * 12,
        raw_json={},
    )


def _mk_poi(promocion, categoria, subtipo, lat, lon, osm_id):
    return POI.objects.create(
        promocion=promocion,
        osm_type="node",
        osm_id=osm_id,
        nombre=f"{categoria}-{osm_id}",
        categoria=categoria,
        subtipo=subtipo,
        tags={},
        location=Point(lon, lat, srid=4326),
    )


# --------------------------------------------------------------------------- #
# MatchPreferences normalisation
# --------------------------------------------------------------------------- #


def test_preferences_dataclass_normalises_out_of_range():
    prefs = MatchPreferences(
        climate_preference="exotic",
        bedrooms_min=-1,
        budget_eur_min=-100,
        must_near=("EDUCACION", "BOGUS", "SALUD"),
        cities=("DONOSTIA ", " Bilbao", "donostia"),
    )
    assert prefs.climate_preference == "any"
    assert prefs.bedrooms_min == 0
    assert prefs.budget_eur_min == 0
    assert "BOGUS" not in prefs.must_near
    assert set(prefs.must_near) == {"EDUCACION", "SALUD"}
    # cities lower-cased and deduped
    assert prefs.cities == ("donostia", "bilbao")


# --------------------------------------------------------------------------- #
# extract_preferences
# --------------------------------------------------------------------------- #


def test_extract_preferences_schema_closed_drops_extra_fields():
    payload = {
        "budget_eur_max": 400000,
        "bedrooms_min": 3,
        "climate_preference": "exotic",  # inválido → normalise to 'any'
        "prefers_sunny": True,
        "must_near": ["EDUCACION"],
        "cities": ["Donostia"],
        "summary": "pareja con dos niños",
        "evil_extra_field": "x",  # debe ignorarse
    }
    with patch("apps.amenabar.services_match._call_gemini_json", return_value=json.dumps(payload)):
        prefs = extract_preferences("pareja con dos niños, 400k, soleado, cerca de colegio")
    assert prefs.budget_eur_max == 400000
    assert prefs.bedrooms_min == 3
    assert prefs.climate_preference == "any"  # normalised
    assert prefs.prefers_sunny is True
    assert prefs.must_near == ("EDUCACION",)
    assert prefs.cities == ("donostia",)
    assert prefs.summary == "pareja con dos niños"


def test_extract_preferences_falls_back_on_gemini_error():
    with patch("apps.amenabar.services_match._call_gemini_json", side_effect=RuntimeError("quota exceeded")):
        prefs = extract_preferences("400k, 3 dormitorios, cerca de colegio, costa")
    assert prefs.budget_eur_max == 400000
    assert prefs.bedrooms_min == 3
    assert "EDUCACION" in prefs.must_near
    assert prefs.climate_preference == "coastal"


def test_extract_keyword_fallback_detects_budget_and_bedrooms(db):
    prefs = _extract_keyword_fallback("Quiero algo de 300-400 mil con 3 dormitorios en la costa, soleado")
    assert prefs.budget_eur_min == 300000
    assert prefs.budget_eur_max == 400000
    assert prefs.bedrooms_min == 3
    assert prefs.climate_preference == "coastal"
    assert prefs.prefers_sunny is True


# --------------------------------------------------------------------------- #
# rank_promociones
# --------------------------------------------------------------------------- #


def test_rank_promociones_respects_estado(db):
    _mk_promo("a", estado=Promocion.Estado.EN_VENTA)
    _mk_promo("b", estado=Promocion.Estado.VENDIDA)
    _mk_promo("c", estado=Promocion.Estado.PROXIMA)
    _mk_promo("d", estado=Promocion.Estado.FINALIZADA)
    scored = rank_promociones(MatchPreferences(), limit=10)
    slugs = {s.promocion.slug for s in scored}
    assert slugs == {"a", "c"}


def test_rank_promociones_sunny_prefers_higher_kwh(db):
    low = _mk_promo("low", lat=43.321, lon=-1.985)
    high = _mk_promo("high", lat=43.322, lon=-1.986)
    _mk_solar(low, 1100)
    _mk_solar(high, 1600)
    prefs = MatchPreferences(prefers_sunny=True)
    scored = rank_promociones(prefs, limit=2)
    assert scored[0].promocion.slug == "high"
    assert scored[1].promocion.slug == "low"
    assert scored[0].breakdown["kwh_kwp_year"] == 1600.0


def test_rank_promociones_clean_air_uses_nearest_station(db):
    # Two promotions, each with a close AQ station of very different PM2.5.
    _mk_promo("donostia-promo", lat=43.321, lon=-1.985, ciudad="Donostia")
    _mk_promo("madrid-promo", lat=40.423, lon=-3.712, ciudad="Madrid")
    AirQualityStation.objects.create(
        openaq_id="S1", name="Donostia", country="ES",
        location=Point(-1.985, 43.322, srid=4326),
        pm25=Decimal("5.0"),
    )
    AirQualityStation.objects.create(
        openaq_id="S2", name="Madrid", country="ES",
        location=Point(-3.712, 40.424, srid=4326),
        pm25=Decimal("60.0"),
    )
    prefs = MatchPreferences(prefers_clean_air=True)
    scored = rank_promociones(prefs, limit=2)
    assert scored[0].promocion.slug == "donostia-promo"
    assert scored[0].breakdown["pm25_latest"] == 5.0
    assert scored[1].breakdown["pm25_latest"] == 60.0


def test_rank_promociones_handles_missing_optional_metrics(db):
    _mk_promo("plain", lat=43.321, lon=-1.985)
    prefs = MatchPreferences(prefers_sunny=True, prefers_clean_air=True, climate_preference="warm")
    scored = rank_promociones(prefs, limit=1)
    # No solar/clima/air cached → score degrades but doesn't crash
    assert len(scored) == 1
    assert 0.0 <= scored[0].score <= 1.0
    assert scored[0].breakdown["kwh_kwp_year"] is None
    assert scored[0].breakdown["pm25_latest"] is None


def test_rank_promociones_must_near_prefers_closer_pois(db):
    close = _mk_promo("close-school", lat=43.321, lon=-1.985)
    far = _mk_promo("far-school", lat=43.421, lon=-1.885)
    # School 100 m from `close`, 2 km from `far`
    _mk_poi(close, POI.Categoria.EDUCACION, "school", 43.3215, -1.985, osm_id=1)
    _mk_poi(far, POI.Categoria.EDUCACION, "school", 43.420, -1.900, osm_id=2)
    prefs = MatchPreferences(must_near=("EDUCACION",))
    scored = rank_promociones(prefs, limit=2)
    assert scored[0].promocion.slug == "close-school"


# --------------------------------------------------------------------------- #
# generate_explanation
# --------------------------------------------------------------------------- #


def test_generate_explanation_only_cites_breakdown(db):
    """The prompt sent to Gemini must contain ONLY the breakdown of the
    scored promocion we pass in, never other data from the catalogue."""
    from apps.amenabar.services_match import ScoredPromocion

    # Seed noise in the DB — it must NOT reach the prompt.
    _mk_promo("other-noise-promo", lat=42.0, lon=-5.0, ciudad="OtherCity")
    _mk_solar(Promocion.objects.get(slug="other-noise-promo"), 1700)

    target = _mk_promo("target-promo-x", lat=43.321, lon=-1.985)
    scored = ScoredPromocion(
        promocion=target,
        score=0.85,
        breakdown={"kwh_kwp_year": 1540, "educacion_m": 320},
    )

    captured_prompts: list[str] = []

    def _capture(prompt, max_output_tokens=200):
        captured_prompts.append(prompt)
        return "Encaja porque tiene buena producción solar y colegio cerca."

    with patch("apps.amenabar.services_match._call_gemini_json", side_effect=_capture):
        out = generate_explanation(MatchPreferences(prefers_sunny=True), scored, timeout_s=5.0)

    assert out is not None
    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    # Target data IS in the prompt
    assert "Target Promo X" in prompt
    assert "1540" in prompt
    assert "320" in prompt
    # Noise data is NOT in the prompt
    assert "other-noise-promo" not in prompt.lower()
    assert "Other Noise Promo" not in prompt
    assert "1700" not in prompt
    assert "OtherCity" not in prompt


def test_generate_explanation_returns_none_on_timeout(db):
    _mk_promo("timeout-promo")
    scored = rank_promociones(MatchPreferences(), limit=1)[0]
    import time as _time

    def _slow(prompt, max_output_tokens=200):
        _time.sleep(5)
        return "never"

    with patch("apps.amenabar.services_match._call_gemini_json", side_effect=_slow):
        out = generate_explanation(MatchPreferences(), scored, timeout_s=0.2)
    assert out is None


def test_generate_explanation_returns_none_on_error(db):
    _mk_promo("error-promo")
    scored = rank_promociones(MatchPreferences(), limit=1)[0]
    with patch("apps.amenabar.services_match._call_gemini_json", side_effect=RuntimeError("boom")):
        out = generate_explanation(MatchPreferences(), scored, timeout_s=5.0)
    assert out is None


# --------------------------------------------------------------------------- #
# HTMX endpoint
# --------------------------------------------------------------------------- #


def test_match_endpoint_returns_top3_partial(db):
    _mk_promo("promo-a", lat=43.321, lon=-1.985)
    _mk_promo("promo-b", lat=43.322, lon=-1.986)
    _mk_promo("promo-c", lat=43.323, lon=-1.987)
    _mk_promo("promo-d", lat=43.324, lon=-1.988)

    from apps.amenabar import services_match
    fake_prefs = MatchPreferences(summary="demo")
    with (
        patch.object(services_match, "extract_preferences", return_value=fake_prefs),
        patch.object(services_match, "generate_explanation", return_value="Encaja."),
    ):
        resp = Client(HTTP_HOST="localhost").post("/amenabar/match/results/", {"query": "test"})
    assert resp.status_code == 200
    body = resp.content.decode()
    # 3 articles rendered
    assert body.count("<article") == 3


def test_match_endpoint_empty_query_message(db):
    resp = Client(HTTP_HOST="localhost").post("/amenabar/match/results/", {"query": ""})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Escribe algo primero" in body


def test_match_endpoint_no_results_message(db):
    # No promociones at all → no coincidencias
    from apps.amenabar import services_match
    with patch.object(services_match, "extract_preferences", return_value=MatchPreferences(summary="x")):
        resp = Client(HTTP_HOST="localhost").post("/amenabar/match/results/", {"query": "nada"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Sin coincidencias" in body
