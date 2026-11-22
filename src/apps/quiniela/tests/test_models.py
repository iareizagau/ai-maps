"""Tests de modelos de la quiniela (tareas 3.1-3.7)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.quiniela.models import (
    Boleto,
    BoletoConfirmadoError,
    Equipo,
    EquipoAlias,
    Jornada,
    PartidoJornada,
    Pronostico,
    resolver_equipo,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def jornada():
    return Jornada.objects.create(temporada="2627", numero=20, fecha_cierre=timezone.now() + timedelta(days=1))


@pytest.fixture
def usuario():
    return get_user_model().objects.create_user(
        username="staff", email="staff@example.com", password="x", is_staff=True
    )


def test_alias_resuelve_mismo_equipo():
    athletic = Equipo.objects.create(nombre="Athletic Club")
    EquipoAlias.objects.create(texto="Ath Bilbao", equipo=athletic)
    assert resolver_equipo("ath  bilbao") == athletic
    assert resolver_equipo("Athletic Club") == athletic


def test_nombre_desconocido_crea_equipo_y_alias():
    equipo = resolver_equipo("Atletico Baleares")
    assert equipo.nombre == "Atletico Baleares"
    assert EquipoAlias.objects.filter(texto="atletico baleares", equipo=equipo).exists()
    assert resolver_equipo("Atletico Baleares") == equipo
    assert Equipo.objects.count() == 1


def test_nombre_del_catalogo_usa_nombre_canonico_y_alias_de_prensa():
    equipo = resolver_equipo("Sp Gijon")
    assert equipo.nombre == "Real Sporting de Gijón"
    assert resolver_equipo("Sporting de Gijón") == equipo
    assert resolver_equipo("sp gijon") == equipo
    assert Equipo.objects.count() == 1


def test_nombre_desconocido_sin_crear_devuelve_none():
    assert resolver_equipo("Inventado FC", crear=False) is None
    assert Equipo.objects.count() == 0


def test_posicion_unica_por_jornada(jornada):
    PartidoJornada.objects.create(jornada=jornada, posicion=1, local_texto="A", visitante_texto="B")
    with pytest.raises(IntegrityError):
        PartidoJornada.objects.create(jornada=jornada, posicion=1, local_texto="C", visitante_texto="D")


def test_posicion_fuera_de_rango_rechazada(jornada):
    with pytest.raises(IntegrityError):
        PartidoJornada.objects.create(jornada=jornada, posicion=16, local_texto="A", visitante_texto="B")


def test_local_igual_visitante_invalido(jornada):
    eq = Equipo.objects.create(nombre="Eibar")
    partido = PartidoJornada(jornada=jornada, posicion=2, local=eq, visitante=eq)
    with pytest.raises(ValidationError):
        partido.clean()


def test_partido_fuera_de_catalogo_marca_sin_historico(jornada):
    partido = PartidoJornada.objects.create(
        jornada=jornada, posicion=3, local_texto="España", visitante_texto="Georgia"
    )
    partido.clean()
    assert partido.sin_historico


def test_resultado_y_pleno(jornada):
    partido = PartidoJornada.objects.create(
        jornada=jornada, posicion=15, local_texto="A", visitante_texto="B", goles_local=4, goles_visitante=1
    )
    assert partido.signo_resultado == "1"
    assert partido.pleno_resultado == "M-1"


def test_precedencia_cuotas_modelo_uniforme(jornada):
    partido = PartidoJornada.objects.create(jornada=jornada, posicion=4, local_texto="A", visitante_texto="B")
    Pronostico.objects.create(partido=partido, fuente="uniforme", p1=1 / 3, px=1 / 3, p2=1 / 3)
    assert partido.pronostico_elegido.fuente == "uniforme"
    Pronostico.objects.create(partido=partido, fuente="modelo", p1=0.5, px=0.3, p2=0.2)
    assert partido.pronostico_elegido.fuente == "modelo"
    Pronostico.objects.create(partido=partido, fuente="cuotas", p1=0.6, px=0.25, p2=0.15)
    assert partido.pronostico_elegido.fuente == "cuotas"
    assert partido.pronostico_elegido.signo_favorito == "1"


def test_boleto_confirmado_es_inmutable(jornada, usuario):
    boleto = Boleto.objects.create(jornada=jornada, usuario=usuario, configuracion="1D")
    boleto.confirmado_at = timezone.now()
    boleto.save()  # la confirmación en sí está permitida
    boleto.configuracion = "1T"
    with pytest.raises(BoletoConfirmadoError):
        boleto.save()


def test_boleto_confirmado_admite_evaluacion(jornada, usuario):
    boleto = Boleto.objects.create(jornada=jornada, usuario=usuario, confirmado_at=timezone.now())
    boleto.aciertos = 9
    boleto.pleno_acertado = False
    boleto.save(update_fields=["aciertos", "pleno_acertado"])
    boleto.refresh_from_db()
    assert boleto.aciertos == 9
