"""Tests de vistas (tarea 10.6): acceso staff, páginas principales y acciones HTMX."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.quiniela import views
from apps.quiniela.models import Boleto, Jornada, PartidoJornada, Pronostico, resolver_equipo

pytestmark = pytest.mark.django_db
HOST = {"HTTP_HOST": "localhost"}


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_user(username="yo", email="yo@example.com", password="x", is_staff=True)
    client.force_login(user)
    return client


@pytest.fixture
def jornada():
    j = Jornada.objects.create(temporada="2627", numero=22, fecha_cierre=timezone.now() + timedelta(days=2))
    for pos in range(1, 16):
        p = PartidoJornada.objects.create(jornada=j, posicion=pos, local_texto=f"L{pos}", visitante_texto=f"V{pos}")
        Pronostico.objects.create(partido=p, fuente="cuotas", p1=0.6, px=0.25, p2=0.15)
    return j


def test_no_staff_redirige_al_login(client, jornada):
    user = get_user_model().objects.create_user(username="otro", email="o@example.com", password="x")
    client.force_login(user)
    for url in (
        reverse("quiniela:index"),
        reverse("quiniela:jornada_detalle", args=[jornada.pk]),
        reverse("quiniela:seguimiento"),
    ):
        resp = client.get(url, **HOST)
        assert resp.status_code == 302 and "login" in resp["Location"]


def test_index_sin_jornadas_lleva_al_alta(staff):
    resp = staff.get(reverse("quiniela:index"), **HOST)
    assert resp.status_code == 302 and resp["Location"].endswith(reverse("quiniela:jornada_nueva"))


def test_paginas_principales_responden(staff, jornada):
    assert staff.get(reverse("quiniela:index"), **HOST).status_code == 302
    detalle = staff.get(reverse("quiniela:jornada_detalle", args=[jornada.pk]), **HOST)
    assert detalle.status_code == 200
    assert b"Elige configuraci" in detalle.content  # comparativa de configuraciones
    assert staff.get(reverse("quiniela:jornada_nueva"), **HOST).status_code == 200
    assert staff.get(reverse("quiniela:seguimiento"), **HOST).status_code == 200


def _datos_alta(**extra):
    datos = {
        "temporada": "2627",
        "numero": "23",
        "fecha_cierre": (timezone.localtime() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
        "p-TOTAL_FORMS": "15",
        "p-INITIAL_FORMS": "0",
        "p-MIN_NUM_FORMS": "15",
        "p-MAX_NUM_FORMS": "15",
    }
    athletic, espanyol = resolver_equipo("Ath Bilbao"), resolver_equipo("Espanol")
    for i in range(15):
        datos[f"p-{i}-local_texto"] = f"Local {i}"
        datos[f"p-{i}-visitante_texto"] = f"Visitante {i}"
    datos["p-0-local"], datos["p-0-local_texto"] = str(athletic.pk), ""
    datos["p-0-visitante"], datos["p-0-visitante_texto"] = str(espanyol.pk), ""
    datos.update(extra)
    return datos


def test_alta_de_jornada_completa(staff, monkeypatch):
    monkeypatch.setattr(views, "ingest_cuotas_jornada", lambda j: None)  # sin red
    resp = staff.post(reverse("quiniela:jornada_nueva"), _datos_alta(), **HOST)
    assert resp.status_code == 302
    jornada = Jornada.objects.get(numero=23)
    assert jornada.partidos.count() == 15
    assert jornada.partidos.get(posicion=1).local.nombre == "Athletic Club"
    assert Pronostico.objects.filter(partido__jornada=jornada).count() == 15  # todos uniforme sin histórico


def test_alta_con_fila_erronea_conserva_lo_escrito(staff):
    datos = _datos_alta(**{"p-4-visitante_texto": "Local 4"})  # local == visitante
    resp = staff.post(reverse("quiniela:jornada_nueva"), datos, **HOST)
    assert resp.status_code == 200
    assert "mismo equipo" in resp.content.decode()
    assert 'value="Local 7"' in resp.content.decode()
    assert not Jornada.objects.filter(numero=23).exists()


def test_acciones_htmx_devuelven_el_panel(staff, jornada):
    generar = staff.post(reverse("quiniela:generar", args=[jornada.pk]), {"configuracion": "1D"}, **HOST)
    assert generar.status_code == 200
    html = generar.content.decode()
    assert 'id="panel"' in html and "<html" not in html
    boleto = Boleto.objects.get(jornada=jornada)
    assert boleto.configuracion == "1D"

    simple = next(li["posicion"] for li in boleto.lineas if len(li["signos"]) == 1)
    resp = staff.post(
        reverse("quiniela:sobrescribir", args=[jornada.pk]), {"posicion": simple, "signos": ["1", "X", "2"]}, **HOST
    )
    assert "Supera el tope" not in resp.content.decode()  # 1D + 1T = 6 apuestas, cabe
    boleto.refresh_from_db()
    assert boleto.num_apuestas == 6

    otro = next(li["posicion"] for li in boleto.lineas if len(li["signos"]) == 1)
    resp = staff.post(
        reverse("quiniela:sobrescribir", args=[jornada.pk]), {"posicion": otro, "signos": ["1", "X", "2"]}, **HOST
    )
    assert "Supera el tope" in resp.content.decode()

    resp = staff.post(
        reverse("quiniela:pleno", args=[jornada.pk]), {"pleno_local": "1", "pleno_visitante": "M"}, **HOST
    )
    boleto.refresh_from_db()
    assert boleto.pleno == "1-M"

    resp = staff.post(reverse("quiniela:confirmar", args=[jornada.pk]), **HOST)
    assert "Boleto confirmado" in resp.content.decode()


def test_resultado_manual(staff, jornada):
    jornada.fecha_cierre = timezone.now() - timedelta(hours=1)
    jornada.save()
    url = reverse("quiniela:resultado_manual", args=[jornada.pk, 3])
    staff.post(url, {"goles_local": "2", "goles_visitante": "1"}, **HOST)
    partido = jornada.partidos.get(posicion=3)
    assert (partido.goles_local, partido.goles_visitante) == (2, 1)
    resp = staff.post(url, {"goles_local": "-1", "goles_visitante": "x"}, **HOST)
    assert "no válidos" in resp.content.decode()


def test_banner_de_avisos_no_disponibles(staff, jornada):
    jornada.avisos_error = "429 quota"
    jornada.save()
    html = staff.get(reverse("quiniela:jornada_detalle", args=[jornada.pk]), **HOST).content.decode()
    assert "Avisos no disponibles" in html
    assert "Elige configuraci" in html  # el boleto sigue disponible
