"""Tests de pronóstico (tareas 5.1-5.4; spec pronostico)."""

import math
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.quiniela.models import Equipo, Jornada, PartidoHistorico, PartidoJornada, Pronostico
from apps.quiniela.services_modelo import (
    PartidoModelo,
    ajustar_modelo,
    distribucion_pleno,
    matriz_goles,
    probs_1x2,
    probs_desde_cuotas,
)
from apps.quiniela.services_pronostico import calcular_pronostico_jornada

# --------------------------------------------------------------------------- #
# Cuotas
# --------------------------------------------------------------------------- #


def test_probs_desde_cuotas_suman_uno_y_respetan_orden():
    p1, px, p2 = probs_desde_cuotas(1.48, 4.38, 6.23)
    assert math.isclose(p1 + px + p2, 1.0)
    assert p1 > px > p2


def test_shin_sube_al_favorito_frente_a_proporcional():
    prop = probs_desde_cuotas(1.16, 7.68, 14.19)
    shin = probs_desde_cuotas(1.16, 7.68, 14.19, metodo="shin")
    assert math.isclose(sum(shin), 1.0)
    assert shin[0] > prop[0]
    assert shin[2] < prop[2]


def test_cuotas_invalidas():
    with pytest.raises(ValueError):
        probs_desde_cuotas(1.0, 3.0, 4.0)


# --------------------------------------------------------------------------- #
# Matriz de goles y Pleno
# --------------------------------------------------------------------------- #


def test_matriz_y_pleno_suman_uno():
    m = matriz_goles(1.6, 1.1)
    assert math.isclose(sum(map(sum, m)), 1.0)
    assert math.isclose(sum(probs_1x2(m)), 1.0)
    pleno = distribucion_pleno(m)
    assert len(pleno) == 16
    assert math.isclose(sum(pleno.values()), 1.0)
    assert max(pleno, key=pleno.get) == "1-1"


def test_rho_negativo_aumenta_empates():
    base = probs_1x2(matriz_goles(1.3, 1.1))
    dc = probs_1x2(matriz_goles(1.3, 1.1, rho=-0.1))
    assert dc[1] > base[1]


# --------------------------------------------------------------------------- #
# Ajuste del modelo
# --------------------------------------------------------------------------- #


def _poisson_muestra(rng: random.Random, lam: float) -> int:
    limite, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def liga_sintetica(jornadas: int = 40, semilla: int = 7) -> list[PartidoModelo]:
    """6 equipos; el 1 ataca mucho, el 6 defiende mal; ventaja local real."""
    rng = random.Random(semilla)
    ataque = {1: 0.5, 2: 0.1, 3: 0.0, 4: 0.0, 5: -0.2, 6: -0.4}
    defensa = {1: -0.3, 2: 0.0, 3: 0.0, 4: 0.1, 5: 0.0, 6: 0.4}
    partidos, inicio = [], date(2025, 8, 15)
    for j in range(jornadas):
        for local in ataque:
            for visitante in ataque:
                if local == visitante or (local + visitante + j) % 3:
                    continue
                lam_l = math.exp(0.2 + 0.25 + ataque[local] + defensa[visitante])
                lam_v = math.exp(0.2 + ataque[visitante] + defensa[local])
                partidos.append(
                    PartidoModelo(
                        inicio + timedelta(days=7 * j),
                        "SP1",
                        local,
                        visitante,
                        _poisson_muestra(rng, lam_l),
                        _poisson_muestra(rng, lam_v),
                    )
                )
    return partidos


def test_modelo_recupera_fuerzas_y_ventaja_local():
    datos = liga_sintetica()
    modelo = ajustar_modelo(datos, date(2027, 1, 1), xi=0.0)
    assert max(modelo.ataque, key=modelo.ataque.get) == 1
    assert max(modelo.defensa, key=modelo.defensa.get) == 6
    assert modelo.h > 0
    p1, _, p2 = modelo.predecir(1, 6)
    assert p1 > 0.6 and p2 < 0.15


def test_modelo_no_usa_partidos_en_o_despues_del_corte():
    datos = liga_sintetica()
    corte = date(2026, 1, 1)
    base = ajustar_modelo(datos, corte, xi=0.0019)
    trampa = [
        *datos,
        PartidoModelo(corte, "SP1", 6, 1, 9, 0),
        PartidoModelo(corte + timedelta(days=3), "SP1", 6, 1, 9, 0),
    ]
    con_trampa = ajustar_modelo(trampa, corte, xi=0.0019)
    assert con_trampa.ataque == base.ataque
    assert con_trampa.predecir(6, 1) == base.predecir(6, 1)


def test_modelo_sin_datos_previos_falla():
    with pytest.raises(ValueError):
        ajustar_modelo(liga_sintetica(), date(2000, 1, 1))


# --------------------------------------------------------------------------- #
# Servicio de pronóstico (BD)
# --------------------------------------------------------------------------- #


@pytest.fixture
def jornada_con_historico(db, settings):
    settings.QUINIELA_MIN_PARTIDOS = 5
    equipos = {i: Equipo.objects.create(nombre=f"Equipo {i}") for i in range(1, 7)}
    PartidoHistorico.objects.bulk_create(
        PartidoHistorico(
            division=p.division,
            temporada="2526",
            fecha=p.fecha,
            local=equipos[p.local],
            visitante=equipos[p.visitante],
            goles_local=p.goles_local,
            goles_visitante=p.goles_visitante,
        )
        for p in liga_sintetica(jornadas=30)
    )
    jornada = Jornada.objects.create(
        temporada="2627", numero=1, fecha_cierre=datetime(2026, 4, 1, 12, tzinfo=ZoneInfo("Europe/Madrid"))
    )
    con_cuotas = PartidoJornada.objects.create(
        jornada=jornada,
        posicion=1,
        local=equipos[1],
        visitante=equipos[2],
        cuota_1=Decimal("1.80"),
        cuota_x=Decimal("3.60"),
        cuota_2=Decimal("4.50"),
    )
    solo_modelo = PartidoJornada.objects.create(jornada=jornada, posicion=2, local=equipos[3], visitante=equipos[6])
    sin_datos = PartidoJornada.objects.create(
        jornada=jornada, posicion=3, local_texto="España", visitante_texto="Malta"
    )
    pleno = PartidoJornada.objects.create(jornada=jornada, posicion=15, local=equipos[4], visitante=equipos[5])
    return jornada, con_cuotas, solo_modelo, sin_datos, pleno


def test_precedencia_de_fuentes_en_la_jornada(jornada_con_historico):
    jornada, con_cuotas, solo_modelo, sin_datos, pleno = jornada_con_historico
    recuento = calcular_pronostico_jornada(jornada)
    assert recuento == {"cuotas": 1, "modelo": 2, "uniforme": 1}

    elegido = con_cuotas.pronostico_elegido
    assert elegido.fuente == "cuotas"
    assert math.isclose(elegido.p1 + elegido.px + elegido.p2, 1.0)
    assert con_cuotas.pronosticos.filter(fuente="modelo").exists()  # se guarda para seguimiento

    assert solo_modelo.pronostico_elegido.fuente == "modelo"
    assert sin_datos.pronostico_elegido.fuente == "uniforme"

    dist = pleno.pronostico_elegido.pleno_dist
    assert len(dist) == 16 and math.isclose(sum(dist.values()), 1.0)
    assert solo_modelo.pronostico_elegido.pleno_dist is None


def test_llegan_cuotas_despues_y_se_recalcula(jornada_con_historico):
    jornada, _, solo_modelo, sin_datos, _ = jornada_con_historico
    calcular_pronostico_jornada(jornada)
    antes = solo_modelo.pronostico_elegido.calculado_at

    solo_modelo.cuota_1, solo_modelo.cuota_x, solo_modelo.cuota_2 = Decimal("1.5"), Decimal("4.0"), Decimal("6.5")
    solo_modelo.save()
    calcular_pronostico_jornada(jornada)

    assert solo_modelo.pronostico_elegido.fuente == "cuotas"
    assert solo_modelo.pronostico_elegido.calculado_at > antes
    assert set(solo_modelo.pronosticos.values_list("fuente", flat=True)) == {"cuotas", "modelo"}
    assert set(sin_datos.pronosticos.values_list("fuente", flat=True)) == {"uniforme"}


def test_equipo_con_poco_historico_queda_sin_datos(jornada_con_historico, settings):
    jornada, *_ = jornada_con_historico
    settings.QUINIELA_MIN_PARTIDOS = 10_000
    calcular_pronostico_jornada(jornada)
    fuentes = dict(Pronostico.objects.filter(partido__jornada=jornada).values_list("partido__posicion", "fuente"))
    assert fuentes[1] == "cuotas"  # las cuotas no dependen del histórico
    assert fuentes[2] == "uniforme"
    assert not Pronostico.objects.filter(partido__jornada=jornada, fuente="modelo").exists()
