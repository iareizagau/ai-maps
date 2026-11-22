"""Tests del boleto (tareas 7.1-7.6; spec boleto)."""

import itertools
import math
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.quiniela import services_boleto as sb
from apps.quiniela.models import Boleto, BoletoConfirmadoError, Jornada, PartidoJornada, Pronostico
from apps.quiniela.services_gemini import GeminiNoDisponibleError

FAVORITO = {"1": 0.70, "X": 0.20, "2": 0.10}
# Algo más incierto que un partido sin datos para un doble (0,70 > 2/3 cubiertos)
# pero menos para un triple: así el triple va al "sin datos" y el doble aquí.
INCIERTO = {"1": 0.36, "X": 0.34, "2": 0.30}
ESPEC = {"1": 0.40, "X": 0.32, "2": 0.28}  # ejemplo literal de la spec


# --------------------------------------------------------------------------- #
# Capa pura
# --------------------------------------------------------------------------- #


def etiquetas(configs):
    return [(c.etiqueta, c.apuestas) for c in configs]


def test_configuraciones_con_tope_5():
    configs = sb.configuraciones_validas(Decimal("0.75"), 2, Decimal("5.00"))
    assert etiquetas(configs) == [("1D", 2), ("1T", 3), ("2D", 4), ("1T+1D", 6)]
    assert [c.coste(Decimal("0.75")) for c in configs] == [Decimal(x) for x in ("1.50", "2.25", "3.00", "4.50")]


def test_configuraciones_con_tope_3():
    assert etiquetas(sb.configuraciones_validas(Decimal("0.75"), 2, Decimal("3.00"))) == [
        ("1D", 2),
        ("1T", 3),
        ("2D", 4),
    ]


def test_configuraciones_con_precio_1():
    assert etiquetas(sb.configuraciones_validas(Decimal("1.00"), 2, Decimal("5.00"))) == [
        ("1D", 2),
        ("1T", 3),
        ("2D", 4),
    ]


def test_dp_coincide_con_fuerza_bruta():
    cob = [0.7, 0.55, 0.9, 0.4, 0.65]
    dist = sb.prob_aciertos(cob)
    bruta = [0.0] * 6
    for aciertos in itertools.product([0, 1], repeat=5):
        bruta[sum(aciertos)] += math.prod(p if a else 1 - p for p, a in zip(cob, aciertos, strict=True))
    assert all(math.isclose(a, b) for a, b in zip(dist, bruta, strict=True))
    assert math.isclose(sum(dist), 1.0)


def test_el_doble_va_al_partido_mas_incierto():
    probs = [dict(FAVORITO) for _ in range(14)]
    probs[6] = dict(ESPEC)
    opcion = sb.optimizar(probs, sb.Configuracion(apuestas=2, triples=0, dobles=1), objetivo=11)
    assert opcion.signos[6] == "1X"
    assert all(s == "1" for i, s in enumerate(opcion.signos) if i != 6)


def test_optimizador_es_exacto_frente_a_enumeracion():
    probs = [{"1": 0.5 + 0.03 * (i % 5), "X": 0.3 - 0.02 * (i % 4), "2": 0.0} for i in range(14)]
    for p in probs:
        p["2"] = 1 - p["1"] - p["X"]
    config = sb.Configuracion(apuestas=6, triples=1, dobles=1)
    opcion = sb.optimizar(probs, config, objetivo=11)
    mejor = 0.0
    for t in range(14):
        for d in range(14):
            if t == d:
                continue
            cob = [max(p.values()) for p in probs]
            cob[d] = sum(sorted(probs[d].values())[-2:])
            cob[t] = 1.0
            mejor = max(mejor, sb.p_al_menos(sb.prob_aciertos(cob), 11))
    assert math.isclose(opcion.valor_objetivo, mejor)


def test_recomendada_es_la_de_mayor_probabilidad_dentro_del_tope(settings):
    settings.QUINIELA_TOPE_EUR = Decimal("5.00")
    probs = [dict(INCIERTO) for _ in range(14)]
    opciones = sb.proponer_desde_probs(probs, objetivo=11)
    assert [o.config.etiqueta for o in opciones] == ["1D", "1T", "2D", "1T+1D"]
    recomendada = [o for o in opciones if o.recomendada]
    assert len(recomendada) == 1 and recomendada[0].config.etiqueta == "1T+1D"
    assert all({"p10", "p11", "p12", "p14"} <= o.probs.keys() for o in opciones)


# --------------------------------------------------------------------------- #
# Capa ORM
# --------------------------------------------------------------------------- #


@pytest.fixture
def jornada(db):
    j = Jornada.objects.create(temporada="2627", numero=21, fecha_cierre=timezone.now() + timedelta(days=2))
    for pos in range(1, 16):
        partido = PartidoJornada.objects.create(
            jornada=j, posicion=pos, local_texto=f"L{pos}", visitante_texto=f"V{pos}"
        )
        if pos == 5:
            Pronostico.objects.create(partido=partido, fuente="uniforme", p1=1 / 3, px=1 / 3, p2=1 / 3)
            continue
        probs = INCIERTO if pos == 9 else FAVORITO
        Pronostico.objects.create(partido=partido, fuente="cuotas", p1=probs["1"], px=probs["X"], p2=probs["2"])
        if pos == 15:
            dist = {f"{a}-{b}": 0.0 for a in "012M" for b in "012M"}
            dist["1-0"], dist["1-1"] = 0.6, 0.4
            Pronostico.objects.create(partido=partido, fuente="modelo", p1=0.5, px=0.3, p2=0.2, pleno_dist=dist)
    return j


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(username="yo", email="yo@example.com", password="x", is_staff=True)


def lineas(boleto):
    return {linea["posicion"]: linea["signos"] for linea in boleto.lineas}


def test_generar_boleto_recomendado(jornada, usuario, settings):
    settings.QUINIELA_TOPE_EUR = Decimal("5.00")
    boleto = sb.generar_boleto(jornada, usuario)
    assert boleto.configuracion == "1T+1D"
    assert (boleto.num_apuestas, boleto.coste) == (6, Decimal("4.50"))
    assert lineas(boleto)[5] == "1X2"  # el sin datos es el más incierto → triple
    assert lineas(boleto)[9] == "1X"
    assert boleto.pleno == "1-0"
    assert 0 < boleto.p14 < boleto.p12 < boleto.p11 < boleto.p10 < 1


def test_sobrescritura_dentro_del_tope_recalcula(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1D")
    antes = boleto.p11
    sb.aplicar_sobrescritura(boleto, 1, "x")
    assert lineas(boleto)[1] == "X"
    assert next(li for li in boleto.lineas if li["posicion"] == 1)["origen"] == "usuario"
    assert boleto.p11 < antes  # cambiar el favorito por la X baja la probabilidad


def test_sobrescritura_que_supera_el_tope_se_rechaza(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1T+1D")
    with pytest.raises(sb.BoletoError, match=r"13\.50"):
        sb.aplicar_sobrescritura(boleto, 1, "1X2")
    boleto.refresh_from_db()
    assert boleto.configuracion == "1T+1D"


def test_sobrescritura_por_debajo_del_minimo_se_rechaza(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1D")
    pos_doble = next(p for p, s in lineas(boleto).items() if len(s) == 2)
    with pytest.raises(sb.BoletoError, match="Mínimo"):
        sb.aplicar_sobrescritura(boleto, pos_doble, "1")


def test_pleno_con_dos_signos_se_rechaza(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario)
    with pytest.raises(sb.BoletoError, match="duplicaría"):
        sb.fijar_pleno(boleto, "1M-0")
    sb.fijar_pleno(boleto, "m-2")
    assert boleto.pleno == "M-2"


def test_confirmar_exige_signo_en_partido_sin_datos(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1D")  # el doble no cae en el 5
    assert len(lineas(boleto)[5]) < 3
    with pytest.raises(sb.BoletoError, match=r"\[5\]"):
        sb.confirmar(boleto)
    sb.aplicar_sobrescritura(boleto, 5, "2")
    sb.confirmar(boleto)
    assert boleto.confirmado and boleto.probabilidades_snapshot["9"] == INCIERTO


def test_triple_en_partido_sin_datos_permite_confirmar(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1T+1D")
    assert lineas(boleto)[5] == "1X2"
    sb.confirmar(boleto)
    assert boleto.confirmado


def test_no_se_confirma_ni_modifica_con_jornada_cerrada(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1T+1D")
    jornada.fecha_cierre = timezone.now() - timedelta(minutes=1)
    jornada.save()
    boleto.jornada.refresh_from_db()
    with pytest.raises(sb.BoletoError, match="cerrada"):
        sb.confirmar(boleto)
    with pytest.raises(sb.BoletoError, match="cerrada"):
        sb.aplicar_sobrescritura(boleto, 1, "X")


def test_boleto_confirmado_es_inmutable(jornada, usuario):
    boleto = sb.generar_boleto(jornada, usuario, etiqueta="1T+1D")
    sb.confirmar(boleto)
    with pytest.raises(sb.BoletoError, match="confirmado"):
        sb.aplicar_sobrescritura(boleto, 1, "X")
    with pytest.raises(sb.BoletoError, match="confirmado"):
        sb.generar_boleto(jornada, usuario)
    boleto.pleno = "0-0"
    with pytest.raises(BoletoConfirmadoError):
        boleto.save()


def test_explicacion_usa_solo_datos_calculados(jornada, usuario, monkeypatch):
    boleto = sb.generar_boleto(jornada, usuario)
    prompts = []

    def falso(prompt, **kwargs):
        prompts.append(prompt)
        return "El triple va al partido 5 porque no hay datos."

    monkeypatch.setattr(sb, "call_gemini", falso)
    assert sb.explicar(boleto).startswith("El triple")
    assert '"partido": 9' in prompts[0] and "L9 - V9" in prompts[0]
    assert Boleto.objects.get(pk=boleto.pk).explicacion.startswith("El triple")


def test_explicacion_falla_devuelve_none(jornada, usuario, monkeypatch):
    boleto = sb.generar_boleto(jornada, usuario)

    def falso(prompt, **kwargs):
        raise GeminiNoDisponibleError("timeout")

    monkeypatch.setattr(sb, "call_gemini", falso)
    assert sb.explicar(boleto) is None
    assert Boleto.objects.get(pk=boleto.pk).explicacion == ""
