"""Tests de seguimiento y backtest (tareas 8.1-8.3; spec seguimiento)."""

import math
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.quiniela.models import Boleto, Equipo, Jornada, PartidoHistorico, PartidoJornada, Pronostico
from apps.quiniela.services_seguimiento import (
    backtest,
    brier,
    calibracion,
    evaluar_boleto,
    ultimas_jornadas,
)
from apps.quiniela.tests.test_pronostico import liga_sintetica

pytestmark = pytest.mark.django_db


def test_brier_a_mano():
    assert math.isclose(brier({"1": 0.5, "X": 0.3, "2": 0.2}, "1"), 0.25 + 0.09 + 0.04)
    assert brier({"1": 1.0, "X": 0.0, "2": 0.0}, "1") == 0.0


@pytest.fixture
def jornada_jugada():
    """15 partidos: todos terminan 1-1 salvo el 1 (2-0) y el 2 (0-1)."""
    j = Jornada.objects.create(temporada="2627", numero=30, fecha_cierre=timezone.now() - timedelta(days=3))
    goles = {1: (2, 0), 2: (0, 1)}
    for pos in range(1, 16):
        gl, gv = goles.get(pos, (1, 1))
        p = PartidoJornada.objects.create(
            jornada=j,
            posicion=pos,
            local_texto=f"L{pos}",
            visitante_texto=f"V{pos}",
            goles_local=gl,
            goles_visitante=gv,
        )
        if pos <= 3:
            Pronostico.objects.create(partido=p, fuente="cuotas", p1=0.5, px=0.3, p2=0.2)
            Pronostico.objects.create(partido=p, fuente="modelo", p1=0.4, px=0.3, p2=0.3)
    return j


@pytest.fixture
def usuario():
    return get_user_model().objects.create_user(username="yo", email="yo@example.com", password="x", is_staff=True)


def crear_boleto(jornada, usuario, lineas, pleno="1-1"):
    return Boleto.objects.create(
        jornada=jornada,
        usuario=usuario,
        lineas=lineas,
        pleno=pleno,
        configuracion="1D",
        num_apuestas=2,
        coste=Decimal("1.50"),
        probabilidades_snapshot={str(p): {"1": 0.5, "X": 0.3, "2": 0.2} for p in range(1, 15)},
        confirmado_at=timezone.now() - timedelta(days=4),
    )


def test_doble_con_empate_cuenta_como_acierto(jornada_jugada, usuario):
    lineas = [{"posicion": p, "signos": "1", "origen": "modelo"} for p in range(1, 15)]
    lineas[2]["signos"] = "1X"  # partido 3 acabó 1-1
    crear_boleto(jornada_jugada, usuario, lineas)
    boleto = evaluar_boleto(jornada_jugada)
    # Aciertan: el 1 (2-0) y el 3 (doble 1X con empate). El resto son X y se marcó 1.
    assert boleto.aciertos == 2
    assert boleto.pleno_acertado is True


def test_sin_boleto_confirmado_no_evalua_pero_calibra(jornada_jugada):
    assert evaluar_boleto(jornada_jugada) is None
    cal = calibracion(Jornada.objects.all())
    cuotas = cal.fuentes["cuotas"]
    assert cuotas.n == 3
    # Resultados 1, 2, X con p = (0.5, 0.3, 0.2): Brier a mano.
    esperado = (brier({"1": 0.5, "X": 0.3, "2": 0.2}, r) for r in ("1", "2", "X"))
    assert math.isclose(cuotas.brier_medio, sum(esperado) / 3)
    assert math.isclose(cuotas.tasa_acierto, 1 / 3)


def test_sobrescrituras_del_usuario_frente_a_la_propuesta(jornada_jugada, usuario):
    lineas = [{"posicion": p, "signos": "1", "origen": "modelo"} for p in range(1, 15)]
    lineas[1] = {"posicion": 2, "signos": "2", "origen": "usuario"}  # acierta (0-1); la propuesta (1) no
    lineas[3] = {"posicion": 4, "signos": "2", "origen": "usuario"}  # falla (1-1); la propuesta tampoco
    crear_boleto(jornada_jugada, usuario, lineas)
    evaluar_boleto(jornada_jugada)
    cal = calibracion(ultimas_jornadas(10))
    assert (cal.sobrescrituras, cal.sobrescrituras_acertadas, cal.propuesta_habria_acertado) == (2, 1, 0)
    assert cal.gasto_total == Decimal("1.50")
    assert cal.jornadas[0]["aciertos"] == 2


def _cargar_liga(con_cuotas=True):
    equipos = {i: Equipo.objects.create(nombre=f"Equipo {i}") for i in range(1, 7)}
    PartidoHistorico.objects.bulk_create(
        PartidoHistorico(
            division="SP1",
            temporada="2526" if p.fecha.year == 2025 or p.fecha.month >= 7 else "2627",
            fecha=p.fecha,
            local=equipos[p.local],
            visitante=equipos[p.visitante],
            goles_local=p.goles_local,
            goles_visitante=p.goles_visitante,
            cuota_1=Decimal("2.0") if con_cuotas else None,
            cuota_x=Decimal("3.4") if con_cuotas else None,
            cuota_2=Decimal("3.8") if con_cuotas else None,
        )
        for p in liga_sintetica(jornadas=40)
    )


def test_backtest_es_determinista_y_compara_en_el_mismo_conjunto():
    _cargar_liga()
    a = backtest(["2526", "2627"], ["SP1"], minimo=5)
    b = backtest(["2526", "2627"], ["SP1"], minimo=5)
    assert a.total["modelo"].n == a.total["cuotas"].n > 0
    assert a.total["modelo"].brier == b.total["modelo"].brier
    assert a.ajustes == b.ajustes > 0
    # Las cuotas sintéticas son constantes: el modelo, que conoce las fuerzas, debe calibrar mejor.
    assert a.total["modelo"].brier_medio < a.total["cuotas"].brier_medio


def test_backtest_ignora_partidos_sin_cuotas():
    _cargar_liga(con_cuotas=False)
    res = backtest(["2526", "2627"], ["SP1"], minimo=5)
    assert res.total["modelo"].n == 0
