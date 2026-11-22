"""Tests de avisos con IA (tareas 6.1-6.2; spec avisos-noticias). Gemini siempre simulado."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.quiniela import services_avisos
from apps.quiniela.models import Aviso, Jornada, Noticia, PartidoJornada, Pronostico, resolver_equipo
from apps.quiniela.services_gemini import GeminiNoDisponibleError, parsear_json

pytestmark = pytest.mark.django_db


@pytest.fixture
def jornada():
    j = Jornada.objects.create(
        temporada="2627", numero=20, fecha_cierre=datetime(2026, 11, 28, 18, tzinfo=ZoneInfo("Europe/Madrid"))
    )
    athletic, espanyol = resolver_equipo("Ath Bilbao"), resolver_equipo("Espanol")
    p1 = PartidoJornada.objects.create(jornada=j, posicion=1, local=athletic, visitante=espanyol)
    Pronostico.objects.create(partido=p1, fuente="cuotas", p1=0.6, px=0.25, p2=0.15)
    ahora = timezone.now()
    n1 = Noticia.objects.create(url="https://as.com/1", titulo="Nico Williams, baja por lesión", publicada_at=ahora)
    n1.equipos.add(athletic)
    n2 = Noticia.objects.create(url="https://md.com/2", titulo="El Espanyol recupera a Puado", publicada_at=ahora)
    n2.equipos.add(espanyol)
    vieja = Noticia.objects.create(
        url="https://as.com/old", titulo="Noticia vieja", publicada_at=ahora - timedelta(days=10)
    )
    vieja.equipos.add(athletic)
    return j, athletic, espanyol, p1


def simular_gemini(monkeypatch, respuesta=None, error=None):
    llamadas = []

    def falso(prompt, **kwargs):
        llamadas.append(prompt)
        if error:
            raise error
        return respuesta if isinstance(respuesta, str) else json.dumps(respuesta)

    monkeypatch.setattr(services_avisos, "call_gemini", falso)
    return llamadas


def test_prompt_numera_solo_noticias_recientes(jornada):
    j, *_ = jornada
    prompt, indice = services_avisos.construir_prompt(j, services_avisos.noticias_de_la_jornada(j))
    assert len(indice) == 2
    assert "Noticia vieja" not in prompt
    assert "[1]" in prompt and "equipo_id=" in prompt


def test_aviso_valido_se_guarda_en_su_partido(jornada, monkeypatch):
    j, athletic, _, p1 = jornada
    _, indice = services_avisos.construir_prompt(j, services_avisos.noticias_de_la_jornada(j))
    num = next(n for n, noticia in indice.items() if noticia.url == "https://as.com/1")
    simular_gemini(
        monkeypatch,
        [{"equipo_id": athletic.pk, "jugador": "Nico Williams", "tipo": "lesion", "resumen": "Baja", "noticia": num}],
    )
    res = services_avisos.extraer_avisos(j)
    assert (res.disponible, res.creados, res.descartados) == (True, 1, 0)
    aviso = Aviso.objects.get()
    assert (aviso.partido, aviso.equipo, aviso.tipo, aviso.noticia.url) == (p1, athletic, "lesion", "https://as.com/1")
    j.refresh_from_db()
    assert j.avisos_at is not None and j.avisos_error == ""


def test_aviso_con_noticia_inventada_o_equipo_ajeno_se_descarta(jornada, monkeypatch):
    j, athletic, *_ = jornada
    barca = resolver_equipo("Barcelona")
    simular_gemini(
        monkeypatch,
        [
            {"equipo_id": athletic.pk, "jugador": "X", "tipo": "lesion", "resumen": "Inventado", "noticia": 99},
            {"equipo_id": barca.pk, "jugador": "Y", "tipo": "lesion", "resumen": "Ajeno", "noticia": 1},
        ],
    )
    res = services_avisos.extraer_avisos(j)
    assert (res.creados, res.descartados) == (0, 2)
    assert not Aviso.objects.exists()


def test_tipo_desconocido_pasa_a_otro_y_duplicados_se_ignoran(jornada, monkeypatch):
    j, athletic, *_ = jornada
    aviso = {"equipo_id": athletic.pk, "jugador": "Sancet", "tipo": "molestias", "resumen": "Duda", "noticia": 1}
    simular_gemini(monkeypatch, "```json\n" + json.dumps([aviso, aviso]) + "\n```")
    services_avisos.extraer_avisos(j)
    assert list(Aviso.objects.values_list("tipo", flat=True)) == ["otro"]


def test_gemini_caido_marca_no_disponible_y_conserva_avisos_previos(jornada, monkeypatch):
    j, athletic, _, p1 = jornada
    previo = Aviso.objects.create(
        partido=p1, equipo=athletic, tipo="duda", resumen="Previo", noticia=Noticia.objects.get(url="https://as.com/1")
    )
    simular_gemini(monkeypatch, error=GeminiNoDisponibleError("429 quota"))
    res = services_avisos.extraer_avisos(j)
    assert not res.disponible
    j.refresh_from_db()
    assert "quota" in j.avisos_error
    assert list(Aviso.objects.all()) == [previo]


def test_respuesta_no_json_es_no_disponible(jornada, monkeypatch):
    j, *_ = jornada
    simular_gemini(monkeypatch, "Lo siento, no puedo ayudar con eso.")
    assert not services_avisos.extraer_avisos(j).disponible


def test_sin_noticias_no_llama_a_gemini(jornada, monkeypatch):
    j, *_ = jornada
    Noticia.objects.all().delete()
    llamadas = simular_gemini(monkeypatch, [])
    assert services_avisos.extraer_avisos(j).disponible
    assert llamadas == []


def test_avisos_no_alteran_probabilidades(jornada, monkeypatch):
    j, athletic, *_ = jornada
    antes = list(Pronostico.objects.values_list("fuente", "p1", "px", "p2"))
    simular_gemini(
        monkeypatch,
        [{"equipo_id": athletic.pk, "jugador": "Nico Williams", "tipo": "lesion", "resumen": "Baja", "noticia": 1}],
    )
    services_avisos.extraer_avisos(j)
    assert list(Pronostico.objects.values_list("fuente", "p1", "px", "p2")) == antes


def test_parsear_json_tolerante():
    assert parsear_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert parsear_json('Aquí tienes: [{"a": 1}] ¡listo!') == [{"a": 1}]
    with pytest.raises(ValueError):
        parsear_json("nada")
