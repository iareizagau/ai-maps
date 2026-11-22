"""Tests de las ayudas de alta: lista pegada, foto (Gemini simulado) y próximos partidos."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.quiniela import services_alta as sa, services_gemini, views
from apps.quiniela.models import cargar_catalogo

pytestmark = pytest.mark.django_db
HOST = {"HTTP_HOST": "localhost"}

LISTA_LOTERIAS = """\
JORNADA 20
1 Athletic - Espanyol
2. Alavés - Deportivo
3) Rayo Vallecano vs Valencia
4 Sevilla \u2013 Betis 1 X 2
5 Real Madrid - Celta 21:00
6 Barça - Villarreal
7 Racing de Santander - Real Sociedad
8 Osasuna - Málaga
9 Getafe - Atleti
10 Levante - Elche
11 Andorra - Leganés
12 Real Sociedad B - Cádiz
13 Sporting de Gijón - Las Palmas
14 Celta Fortuna - Valladolid
Pleno al 15: España - Georgia
"""


@pytest.fixture(autouse=True)
def catalogo():
    cargar_catalogo()


def nombres(partidos):
    return [
        (p.local.equipo.nombre if p.local.equipo else f"?{p.local.texto}",
         p.visitante.equipo.nombre if p.visitante.equipo else f"?{p.visitante.texto}")
        for p in partidos
    ]


def test_parsear_lista_tipica_de_loterias():
    partidos = sa.parsear_lista(LISTA_LOTERIAS)
    assert len(partidos) == 15  # la cabecera "JORNADA 20" se ignora
    n = nombres(partidos)
    assert n[0] == ("Athletic Club", "RCD Espanyol")
    assert n[1] == ("Deportivo Alavés", "Deportivo de La Coruña")
    assert n[2] == ("Rayo Vallecano", "Valencia CF")
    assert n[3] == ("Sevilla FC", "Real Betis")  # semirraya y signos al final
    assert n[4] == ("Real Madrid", "RC Celta")  # hora al final
    assert n[5] == ("FC Barcelona", "Villarreal CF")
    assert n[8] == ("Getafe CF", "Atlético de Madrid")
    assert n[11] == ("Real Sociedad B", "Cádiz CF")  # gana el alias más largo
    assert n[13] == ("Celta Fortuna", "Real Valladolid")
    assert n[14] == ("?España", "?Georgia")  # fuera del catálogo → texto libre


def test_abreviaturas_y_alias_del_boleto():
    partidos = sa.parsear_lista("1 R. Madrid - At. Madrid\n2 Dep. Coruña - Sp. Gijón\n3 Deportivo - Racing")
    assert nombres(partidos) == [
        ("Real Madrid", "Atlético de Madrid"),
        ("Deportivo de La Coruña", "Real Sporting de Gijón"),
        ("Deportivo de La Coruña", "Racing de Santander"),
    ]


def test_parecido_difuso_y_lineas_sin_separador():
    partidos = sa.parsear_lista("Osasnua - Mallorca\nesto no es un partido\n\nGirona-Eibar")
    # "Osasnua" (errata) se reconoce por parecido; "Girona-Eibar" sin espacios no se separa.
    assert nombres(partidos) == [("CA Osasuna", "RCD Mallorca")]


def test_initial_formset_rellena_15_filas():
    filas = sa.initial_formset(sa.parsear_lista("1 Athletic - España"))
    assert len(filas) == 15
    assert filas[0]["local"] is not None and filas[0]["local_texto"] == ""
    assert filas[0]["visitante"] is None and filas[0]["visitante_texto"] == "España"
    assert filas[1] == {}


def test_lista_desde_imagen_valida_y_limpia(monkeypatch):
    llamadas = []

    def falso(prompt, **kwargs):
        llamadas.append(kwargs)
        return "```\n1 Athletic - Espanyol\n2 Alavés - Deportivo\n```"

    monkeypatch.setattr(services_gemini, "call_gemini", falso)
    texto = sa.lista_desde_imagen(b"\x89PNG...", "image/png")
    assert texto == "1 Athletic - Espanyol\n2 Alavés - Deportivo"
    assert llamadas[0]["imagen"] == (b"\x89PNG...", "image/png")
    with pytest.raises(sa.ImagenNoValidaError):
        sa.lista_desde_imagen(b"%PDF", "application/pdf")
    with pytest.raises(sa.ImagenNoValidaError):
        sa.lista_desde_imagen(b"0" * (sa.MAX_BYTES_IMAGEN + 1), "image/jpeg")


def test_con_imagen_solo_se_usan_modelos_gemini(settings, monkeypatch):
    settings.GEMINI_API_KEY = "x"
    settings.GEMINI_GENERATION_FALLBACK_MODELS = ["gemma-4-31b-it"]
    with pytest.raises(services_gemini.GeminiNoDisponibleError, match="No hay modelos"):
        services_gemini.call_gemini("p", imagen=(b"x", "image/png"))


def test_proximos_partidos_filtra_fechas_y_divisiones():
    hoy = timezone.localtime()
    manana = (hoy + timedelta(days=1)).strftime("%d/%m/%Y")
    lejos = (hoy + timedelta(days=30)).strftime("%d/%m/%Y")
    csv = (
        "Div,Date,Time,HomeTeam,AwayTeam,AvgH,AvgD,AvgA\n"
        f"SP2,{manana},18:00,Sp Gijon,Las Palmas,2.0,3.3,3.3\n"
        f"SP1,{manana},16:00,Ath Bilbao,Espanol,1.5,4.4,6.2\n"
        f"E0,{manana},15:00,Arsenal,Chelsea,2,3,4\n"
        f"SP1,{lejos},16:00,Sevilla,Betis,2.9,3.4,2.3\n"
    )
    proximos = sa.proximos_partidos(csv)
    assert [(p.division, p.local.nombre) for p in proximos] == [
        ("SP1", "Athletic Club"),
        ("SP2", "Real Sporting de Gijón"),
    ]


# --------------------------------------------------------------------------- #
# Vistas
# --------------------------------------------------------------------------- #


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_user(username="yo", email="yo@example.com", password="x", is_staff=True)
    client.force_login(user)
    return client


def _post(**extra):
    datos = {
        "temporada": "2627",
        "numero": "",
        "fecha_cierre": "",
        "p-TOTAL_FORMS": "15",
        "p-INITIAL_FORMS": "0",
        "p-MIN_NUM_FORMS": "15",
        "p-MAX_NUM_FORMS": "15",
    }
    datos.update(extra)
    return datos


def test_vista_pegar_rellena_filas_sin_guardar(staff):
    resp = staff.post(reverse("quiniela:jornada_nueva"), _post(accion="pegar", lista=LISTA_LOTERIAS), **HOST)
    html = resp.content.decode()
    assert resp.status_code == 200
    assert "15 partidos leídos" in html
    assert "Revisa las filas marcadas" in html  # el Pleno (España - Georgia)
    assert 'value="España"' in html
    assert "selected" in html


def test_vista_foto_usa_el_texto_leido(staff, monkeypatch):
    monkeypatch.setattr(views, "lista_desde_imagen", lambda datos, mime: "1 Athletic - Espanyol")
    from django.core.files.uploadedfile import SimpleUploadedFile

    imagen = SimpleUploadedFile("boleto.png", b"\x89PNG", content_type="image/png")
    resp = staff.post(reverse("quiniela:jornada_nueva"), _post(accion="foto", imagen=imagen), **HOST)
    html = resp.content.decode()
    assert "1 partido leído de la imagen" in html
    assert "Faltan 14" in html


def test_vista_foto_sin_archivo_muestra_error(staff):
    resp = staff.post(reverse("quiniela:jornada_nueva"), _post(accion="foto"), **HOST)
    assert "Elige una foto" in resp.content.decode()


def test_vista_proximos(staff, monkeypatch):
    monkeypatch.setattr(views, "proximos_partidos", lambda: sa.proximos_partidos("Div,Date,HomeTeam,AwayTeam\n"))
    resp = staff.get(reverse("quiniela:proximos"), **HOST)
    assert resp.status_code == 200
    assert "No hay partidos" in resp.content.decode()
