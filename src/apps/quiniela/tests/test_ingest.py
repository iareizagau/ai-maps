"""Tests de ingesta (tareas 4.1-4.6; spec datos-jornada y avisos-noticias: recogida)."""

import time as time_mod
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.quiniela import services_ingest as si
from apps.quiniela.models import Equipo, Jornada, Noticia, PartidoHistorico, PartidoJornada, resolver_equipo

pytestmark = pytest.mark.django_db

# Cabecera real recortada de SP1 26-27 (incluye xG, que se ignora).
CABECERA = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HxG,AxG,"
    "B365H,B365D,B365A,AvgH,AvgD,AvgA,B365CH,B365CD,B365CA,AvgCH,AvgCD,AvgCA"
)


def csv_temporada(*filas: str) -> bytes:
    return ("﻿" + "\n".join([CABECERA, *filas]) + "\n").encode("utf-8")


FILA_ATH = (
    "SP1,15/08/2026,18:30,Ath Bilbao,Espanol,2,0,H,1.9,0.6,"
    "1.5,4.2,6.0,1.48,4.38,6.23,1.45,4.5,6.5,1.47,4.40,6.30"
)
FILA_SOC = "SP1,16/08/2026,20:00,Sociedad,Sp Gijon,1,1,D,1.1,1.0,1.9,3.4,4.1,1.95,3.40,4.00,2.0,3.3,3.9,,,"
FILA_FUTURA = "SP1,29/11/2026,20:00,Celta,Getafe,,,,,,1.9,3.4,4.1,1.95,3.40,4.00,,,,,,"


def test_ingest_temporada_crea_partidos_con_alias_y_cuotas_de_cierre():
    res = si.ingest_temporada("SP1", "2627", csv_temporada(FILA_ATH, FILA_SOC, FILA_FUTURA))
    assert (res.creados, res.omitidos) == (2, 1)  # el partido futuro no tiene goles
    ath = PartidoHistorico.objects.get(local__nombre="Athletic Club")
    assert ath.visitante.nombre == "RCD Espanyol"
    assert ath.fecha == date(2026, 8, 15)
    assert (ath.cuota_1, ath.cuota_tipo) == (Decimal("1.470"), "AvgC")
    soc = PartidoHistorico.objects.get(local__nombre="Real Sociedad")
    assert soc.cuota_tipo == "B365C"  # AvgC vacío → respaldo
    assert soc.signo == "X"


def test_ingest_temporada_es_idempotente_y_actualiza():
    si.ingest_temporada("SP1", "2627", csv_temporada(FILA_ATH))
    corregida = FILA_ATH.replace(",2,0,H,", ",3,0,H,")
    res = si.ingest_temporada("SP1", "2627", csv_temporada(corregida))
    assert (res.creados, res.actualizados) == (0, 1)
    assert PartidoHistorico.objects.count() == 1
    assert PartidoHistorico.objects.get().goles_local == 3


def test_ingest_temporada_formato_invalido_no_escribe():
    with pytest.raises(si.IngestError):
        si.ingest_temporada("SP1", "2627", b"foo,bar\n1,2\n")
    with pytest.raises(si.IngestError):
        si.ingest_temporada("SP1", "2627", b"<html>Not found</html>")
    assert PartidoHistorico.objects.count() == 0


def test_ingest_temporada_error_a_mitad_no_deja_datos_parciales():
    mala = FILA_SOC.replace("16/08/2026", "32/13/2026")
    with pytest.raises(si.IngestError):
        si.ingest_temporada("SP1", "2627", csv_temporada(FILA_ATH, mala))
    assert PartidoHistorico.objects.count() == 0
    assert Equipo.objects.count() == 0


def test_descargar_error_http(monkeypatch):
    class Resp:
        status_code = 503
        content = b""

    monkeypatch.setattr(si.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(si.IngestError):
        si.descargar("https://football-data.co.uk/fixtures.csv")


def test_temporada_de():
    assert si.temporada_de(date(2026, 11, 22)) == "2627"
    assert si.temporada_de(date(2027, 3, 1)) == "2627"
    assert si.temporada_de(date(2026, 7, 1)) == "2627"


# --------------------------------------------------------------------------- #
# Jornada: cuotas y resultados
# --------------------------------------------------------------------------- #

FIXTURES = (
    "Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A,AvgH,AvgD,AvgA,AvgCH,AvgCD,AvgCA\n"
    "SP1,20/11/2026,20:00,Ath Bilbao,Espanol,1.5,4.2,6.0,1.48,4.38,6.23,,,\n"
    "E0,21/11/2026,15:00,Arsenal,Chelsea,2.0,3.4,3.6,2.0,3.4,3.6,,,\n"
)


@pytest.fixture
def jornada():
    j = Jornada.objects.create(
        temporada="2627", numero=20, fecha_cierre=datetime(2026, 11, 20, 18, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    )
    PartidoJornada.objects.create(
        jornada=j, posicion=1, local=resolver_equipo("Ath Bilbao"), visitante=resolver_equipo("Espanol")
    )
    PartidoJornada.objects.create(
        jornada=j, posicion=2, local=resolver_equipo("Sociedad"), visitante=resolver_equipo("Sp Gijon")
    )
    PartidoJornada.objects.create(jornada=j, posicion=3, local_texto="España", visitante_texto="Georgia")
    return j


def test_ingest_cuotas_asocia_por_equipos_y_fecha(jornada):
    res = si.ingest_cuotas_jornada(jornada, FIXTURES)
    assert (res.actualizados, res.omitidos) == (1, 2)
    p1 = jornada.partidos.get(posicion=1)
    assert p1.tiene_cuotas and p1.cuota_1 == Decimal("1.480")
    assert p1.cuotas_capturadas_at is not None
    assert p1.fecha.date() == date(2026, 11, 20)
    assert not jornada.partidos.get(posicion=2).tiene_cuotas


def test_ingest_cuotas_rechaza_fecha_fuera_de_ventana(jornada):
    lejana = FIXTURES.replace("20/11/2026", "20/01/2027")
    res = si.ingest_cuotas_jornada(jornada, lejana)
    assert res.actualizados == 0


def test_ingest_resultados_copia_goles_y_deja_manuales(jornada):
    sp1 = csv_temporada(FILA_ATH.replace("15/08/2026", "20/11/2026"))
    res = si.ingest_resultados_jornada(jornada, {"SP1": sp1, "SP2": csv_temporada()})
    assert res.actualizados == 1
    p1 = jornada.partidos.get(posicion=1)
    assert (p1.goles_local, p1.goles_visitante, p1.signo_resultado) == (2, 0, "1")
    assert not jornada.partidos.get(posicion=3).tiene_resultado  # fuera de SP1/SP2: manual


# --------------------------------------------------------------------------- #
# Noticias
# --------------------------------------------------------------------------- #


def entrada(titulo: str, link: str, hace: timedelta = timedelta(hours=3), summary: str = "") -> dict:
    cuando = timezone.now() - hace
    publicada = time_mod.gmtime(cuando.timestamp())
    return {"title": titulo, "link": link, "summary": summary, "published_parsed": publicada}


def test_ingest_noticias_filtra_por_equipo_fecha_y_deduplica(jornada):
    feeds = {
        "https://as.com/rss": [
            entrada("El Athletic pierde a Nico Williams por lesión", "https://as.com/1"),
            entrada("El Barça prepara la Champions", "https://as.com/2"),  # equipo fuera de la jornada
            entrada("El Espanyol recupera a su capitán", "https://as.com/3", hace=timedelta(days=9)),  # vieja
        ],
        "https://md.com/rss": [
            entrada("El Athletic pierde a Nico Williams por lesión", "https://as.com/1"),  # misma URL
            entrada("Sporting de Gijón: tres bajas para Anoeta", "https://md.com/4"),
        ],
    }
    res = si.ingest_noticias(jornada, feeds=feeds)
    assert Noticia.objects.count() == 2
    assert res.creados == 2
    athletic = Equipo.objects.get(nombre="Athletic Club")
    assert list(athletic.noticias.values_list("url", flat=True)) == ["https://as.com/1"]
    assert Noticia.objects.get(url="https://md.com/4").equipos.filter(nombre="Real Sporting de Gijón").exists()


def test_ingest_noticias_feed_por_equipo_asigna_aunque_no_lo_nombre(jornada):
    sociedad = Equipo.objects.get(nombre="Real Sociedad")
    url = si.url_google_news(sociedad)
    feeds = {url: [entrada("Aramburu juega con molestias en la cadera", "https://news.google.com/x")]}
    si.ingest_noticias(jornada, feeds=feeds, equipo_de_feed={url: sociedad.pk})
    assert Noticia.objects.get().equipos.get() == sociedad


def test_patrones_sin_acentos_y_palabra_completa():
    leganes = resolver_equipo("Leganes")
    patrones = {leganes.pk: si.patrones_equipo(leganes)}
    assert si.equipos_mencionados("El LEGANÉS gana", patrones) == {leganes.pk}
    assert si.equipos_mencionados("Leganesaurio", patrones) == set()
