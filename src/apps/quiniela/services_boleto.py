"""Boleto semanal ≤ tope (tarea 7; spec boleto; design.md D5).

Capa pura (configuraciones, DP de aciertos, optimizador exacto) más capa ORM
(proponer, generar, sobrescribir, confirmar, explicar).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations

from django.conf import settings
from django.utils import timezone

from .models import SIGNOS_1X2, SIGNOS_PLENO, Boleto, Jornada, Pronostico
from .services_gemini import GeminiNoDisponibleError, call_gemini

logger = logging.getLogger(__name__)

N_COMBINABLES = 14
MAX_COMBINACIONES = 200_000  # salvaguarda si alguien sube mucho el tope


class BoletoError(ValueError):
    """Operación no permitida sobre el boleto (tope, mínimo, cierre…)."""


# --------------------------------------------------------------------------- #
# Configuraciones válidas
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, order=True)
class Configuracion:
    apuestas: int
    triples: int
    dobles: int

    @property
    def etiqueta(self) -> str:
        partes = [f"{self.triples}T"] if self.triples else []
        partes += [f"{self.dobles}D"] if self.dobles else []
        return "+".join(partes) or "sencilla"

    def coste(self, precio: Decimal) -> Decimal:
        return (precio * self.apuestas).quantize(Decimal("0.01"))


def configuraciones_validas(
    precio: Decimal | None = None, minimo: int | None = None, tope: Decimal | None = None
) -> list[Configuracion]:
    """Combinaciones de dobles y triples (Método Directo) con mínimo ≤ apuestas ≤ tope/precio."""
    precio = settings.QUINIELA_PRECIO_APUESTA if precio is None else Decimal(precio)
    minimo = settings.QUINIELA_MIN_APUESTAS if minimo is None else minimo
    tope = settings.QUINIELA_TOPE_EUR if tope is None else Decimal(tope)
    maximo = int(tope // precio)
    configs = []
    for t in range(N_COMBINABLES + 1):
        for d in range(N_COMBINABLES + 1 - t):
            if t == d == 0:
                continue
            apuestas = 2**d * 3**t
            if minimo <= apuestas <= maximo:
                configs.append(Configuracion(apuestas=apuestas, triples=t, dobles=d))
    return sorted(configs)


# --------------------------------------------------------------------------- #
# Probabilidad de aciertos
# --------------------------------------------------------------------------- #


def prob_aciertos(coberturas: list[float]) -> list[float]:
    """Distribución exacta de nº de aciertos (Poisson-binomial) con partidos independientes."""
    dist = [1.0]
    for p in coberturas:
        nueva = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            nueva[k] += q * (1 - p)
            nueva[k + 1] += q * p
        dist = nueva
    return dist


def p_al_menos(dist: list[float], k: int) -> float:
    return sum(dist[k:]) if k < len(dist) else 0.0


def resumen_probs(dist: list[float]) -> dict[str, float]:
    return {f"p{k}": p_al_menos(dist, k) for k in (10, 11, 12, 14)}


def ordenar_signos(signos: str) -> str:
    return "".join(s for s in SIGNOS_1X2 if s in signos)


def signos_por_prob(probs: dict[str, float]) -> list[str]:
    return sorted(SIGNOS_1X2, key=lambda s: -probs[s])


def cobertura(probs: dict[str, float], signos: str) -> float:
    return sum(probs[s] for s in signos)


# --------------------------------------------------------------------------- #
# Optimizador exacto
# --------------------------------------------------------------------------- #


@dataclass
class Opcion:
    config: Configuracion
    signos: list[str]  # 14 strings, p. ej. ["1", "1X", "1X2", ...]
    coste: Decimal
    probs: dict[str, float]
    valor_objetivo: float  # P(≥ objetivo)
    recomendada: bool = False


def optimizar(probs: list[dict[str, float]], config: Configuracion, objetivo: int) -> Opcion:
    """Coloca ``config.triples`` triples y ``config.dobles`` dobles maximizando P(≥ objetivo)."""
    if len(probs) != N_COMBINABLES:
        raise BoletoError(f"Hacen falta {N_COMBINABLES} partidos con pronóstico, hay {len(probs)}.")
    orden = [signos_por_prob(p) for p in probs]
    simple = [cobertura(p, o[0]) for p, o in zip(probs, orden, strict=True)]
    doble = [cobertura(p, "".join(o[:2])) for p, o in zip(probs, orden, strict=True)]

    posiciones = range(N_COMBINABLES)
    total = math.comb(N_COMBINABLES, config.triples) * math.comb(N_COMBINABLES - config.triples, config.dobles)
    if total > MAX_COMBINACIONES:
        raise BoletoError(f"Demasiadas combinaciones ({total}); baja el tope.")

    mejor: tuple[float, tuple, tuple] | None = None
    for triples in combinations(posiciones, config.triples):
        resto = [i for i in posiciones if i not in triples]
        for dobles in combinations(resto, config.dobles):
            cob = list(simple)
            for i in dobles:
                cob[i] = doble[i]
            for i in triples:
                cob[i] = 1.0
            valor = p_al_menos(prob_aciertos(cob), objetivo)
            if mejor is None or valor > mejor[0] + 1e-15:
                mejor = (valor, triples, dobles)

    assert mejor is not None
    _, triples, dobles = mejor
    signos = []
    for i, o in enumerate(orden):
        if i in triples:
            signos.append("1X2")
        elif i in dobles:
            signos.append(ordenar_signos("".join(o[:2])))
        else:
            signos.append(o[0])
    dist = prob_aciertos([cobertura(p, s) for p, s in zip(probs, signos, strict=True)])
    return Opcion(
        config=config,
        signos=signos,
        coste=config.coste(settings.QUINIELA_PRECIO_APUESTA),
        probs=resumen_probs(dist),
        valor_objetivo=p_al_menos(dist, objetivo),
    )


def proponer_desde_probs(probs: list[dict[str, float]], objetivo: int | None = None) -> list[Opcion]:
    """Todas las configuraciones válidas optimizadas; marca la mejor P(≥ objetivo)."""
    objetivo = settings.QUINIELA_OBJETIVO_ACIERTOS if objetivo is None else objetivo
    opciones = [optimizar(probs, c, objetivo) for c in configuraciones_validas()]
    if opciones:
        max(opciones, key=lambda o: (o.valor_objetivo, -o.config.apuestas)).recomendada = True
    return opciones


# --------------------------------------------------------------------------- #
# Capa ORM
# --------------------------------------------------------------------------- #


@dataclass
class Propuesta:
    opciones: list[Opcion]
    pleno: str | None  # combinación más probable, None si no hay modelo para el 15
    pleno_prob: float | None
    sin_datos: list[int] = field(default_factory=list)  # posiciones 1-14 con fuente uniforme


def probs_jornada(jornada: Jornada) -> tuple[list[dict[str, float]], list[int], Pronostico | None]:
    """Probabilidades elegidas de 1-14, posiciones sin datos y pronóstico del 15."""
    partidos = list(jornada.partidos.prefetch_related("pronosticos").order_by("posicion"))
    combinables = [p for p in partidos if p.posicion <= N_COMBINABLES]
    probs, sin_datos = [], []
    for p in combinables:
        elegido = p.pronostico_elegido
        if elegido is None:
            raise BoletoError(f"El partido {p.posicion} no tiene pronóstico: calcúlalo primero.")
        probs.append(elegido.probs)
        if elegido.fuente == Pronostico.Fuente.UNIFORME:
            sin_datos.append(p.posicion)
    pleno = next((p.pronostico_elegido for p in partidos if p.es_pleno), None)
    return probs, sin_datos, pleno


def proponer(jornada: Jornada) -> Propuesta:
    probs, sin_datos, pleno = probs_jornada(jornada)
    pleno_sugerido, pleno_prob = None, None
    if pleno is not None:
        modelo = pleno.partido.pronosticos.filter(fuente=Pronostico.Fuente.MODELO).first()
        if modelo and modelo.pleno_dist:
            pleno_sugerido = max(modelo.pleno_dist, key=modelo.pleno_dist.get)
            pleno_prob = modelo.pleno_dist[pleno_sugerido]
    return Propuesta(proponer_desde_probs(probs), pleno_sugerido, pleno_prob, sin_datos)


def _comprobar_editable(boleto: Boleto) -> None:
    if boleto.confirmado:
        raise BoletoError("El boleto ya está confirmado.")
    if boleto.jornada.cerrada:
        raise BoletoError("La jornada ya está cerrada.")


def _recalcular(boleto: Boleto, probs: list[dict[str, float]]) -> None:
    signos = [linea["signos"] for linea in sorted(boleto.lineas, key=lambda x: x["posicion"])]
    triples = sum(len(s) == 3 for s in signos)
    dobles = sum(len(s) == 2 for s in signos)
    config = Configuracion(apuestas=2**dobles * 3**triples, triples=triples, dobles=dobles)
    resumen = resumen_probs(prob_aciertos([cobertura(p, s) for p, s in zip(probs, signos, strict=True)]))
    boleto.configuracion = config.etiqueta
    boleto.num_apuestas = config.apuestas
    boleto.coste = config.coste(settings.QUINIELA_PRECIO_APUESTA)
    boleto.p10, boleto.p11, boleto.p12, boleto.p14 = (resumen[k] for k in ("p10", "p11", "p12", "p14"))


def generar_boleto(jornada: Jornada, usuario, etiqueta: str | None = None) -> Boleto:
    """Crea o rehace el boleto con la opción recomendada (o la de ``etiqueta``).

    Rehacer descarta las sobrescrituras previas del usuario.
    """
    propuesta = proponer(jornada)
    if etiqueta:
        opcion = next((o for o in propuesta.opciones if o.config.etiqueta == etiqueta), None)
        if opcion is None:
            raise BoletoError(f"Configuración no válida con el tope actual: {etiqueta}")
    else:
        opcion = next((o for o in propuesta.opciones if o.recomendada), None)
        if opcion is None:
            raise BoletoError("Ninguna configuración cabe en el tope.")

    boleto = Boleto.objects.filter(jornada=jornada).first()
    if boleto is not None:
        _comprobar_editable(boleto)
    else:
        boleto = Boleto(jornada=jornada, usuario=usuario)
    if jornada.cerrada:
        raise BoletoError("La jornada ya está cerrada.")
    boleto.lineas = [
        {"posicion": i + 1, "signos": s, "origen": "modelo"} for i, s in enumerate(opcion.signos)
    ]
    boleto.pleno = propuesta.pleno or ""
    boleto.explicacion = ""
    probs, *_ = probs_jornada(jornada)
    _recalcular(boleto, probs)
    boleto.save()
    return boleto


def aplicar_sobrescritura(boleto: Boleto, posicion: int, signos: str) -> Boleto:
    """Cambia los signos de un partido 1-14 y recalcula coste y probabilidades."""
    _comprobar_editable(boleto)
    signos = (signos or "").upper().replace(" ", "")
    if not signos or set(signos) - set(SIGNOS_1X2) or len(set(signos)) != len(signos):
        raise BoletoError(f"Signos inválidos: {signos!r}")
    if not 1 <= posicion <= N_COMBINABLES:
        raise BoletoError("Solo se pueden sobrescribir los partidos 1-14; el 15 va con fijar_pleno.")

    lineas = [dict(linea) for linea in boleto.lineas]
    for linea in lineas:
        if linea["posicion"] == posicion:
            linea["signos"] = ordenar_signos(signos)
            linea["origen"] = "usuario"
    apuestas = math.prod(len(linea["signos"]) for linea in lineas)
    precio = settings.QUINIELA_PRECIO_APUESTA
    coste = (precio * apuestas).quantize(Decimal("0.01"))
    if coste > settings.QUINIELA_TOPE_EUR:
        raise BoletoError(f"Supera el tope: costaría {coste} € ({apuestas} apuestas).")
    if apuestas < settings.QUINIELA_MIN_APUESTAS:
        raise BoletoError(f"Mínimo {settings.QUINIELA_MIN_APUESTAS} apuestas: deja al menos un doble o un triple.")

    boleto.lineas = lineas
    probs, *_ = probs_jornada(boleto.jornada)
    _recalcular(boleto, probs)
    boleto.explicacion = ""
    boleto.save()
    return boleto


def fijar_pleno(boleto: Boleto, pleno: str) -> Boleto:
    """Un único signo por equipo (spec boleto: Pleno al 15)."""
    _comprobar_editable(boleto)
    partes = (pleno or "").upper().replace(" ", "").split("-")
    if len(partes) != 2 or any(p not in SIGNOS_PLENO for p in partes):
        raise BoletoError(
            "El Pleno al 15 lleva un único signo (0, 1, 2 o M) por equipo; "
            "marcar más duplicaría el coste del boleto."
        )
    boleto.pleno = "-".join(partes)
    boleto.save()
    return boleto


def confirmar(boleto: Boleto) -> Boleto:
    _comprobar_editable(boleto)
    probs, sin_datos, _ = probs_jornada(boleto.jornada)
    pendientes = [
        linea["posicion"]
        for linea in boleto.lineas
        if linea["posicion"] in sin_datos and linea["origen"] != "usuario" and len(linea["signos"]) < 3
    ]
    if pendientes:
        raise BoletoError(f"Fija el signo de los partidos sin datos: {pendientes}")
    if not boleto.pleno:
        raise BoletoError("Falta el resultado del Pleno al 15.")
    _recalcular(boleto, probs)
    boleto.probabilidades_snapshot = {str(i + 1): p for i, p in enumerate(probs)}
    boleto.confirmado_at = timezone.now()
    boleto.save()
    return boleto


# --------------------------------------------------------------------------- #
# Explicación con IA
# --------------------------------------------------------------------------- #

PROMPT_EXPLICACION = """Explica en 3-5 líneas, en español y en tono directo, por qué este boleto
de quiniela pone los dobles/triples donde los pone. Usa SOLO los datos del JSON:
no cites cifras, jugadores ni hechos que no aparezcan en él. Sin títulos ni listas.

{datos}
"""


def datos_explicacion(boleto: Boleto) -> dict:
    """Dict cerrado con lo único que puede usar la IA."""
    partidos = {p.posicion: p for p in boleto.jornada.partidos.prefetch_related("pronosticos", "avisos")}
    lineas = []
    for linea in sorted(boleto.lineas, key=lambda x: x["posicion"]):
        partido = partidos[linea["posicion"]]
        elegido = partido.pronostico_elegido
        lineas.append(
            {
                "partido": linea["posicion"],
                "encuentro": f"{partido.nombre_local} - {partido.nombre_visitante}",
                "signos": linea["signos"],
                "origen": linea["origen"],
                "fuente": elegido.fuente if elegido else None,
                "probabilidades": {k: round(v, 2) for k, v in elegido.probs.items()} if elegido else None,
                "avisos": [f"{a.equipo}: {a.get_tipo_display()} {a.jugador}".strip() for a in partido.avisos.all()],
            }
        )
    return {
        "configuracion": boleto.configuracion,
        "coste_eur": str(boleto.coste),
        "prob_11_o_mas": round(boleto.p11 or 0, 3),
        "pleno_al_15": boleto.pleno,
        "partidos": lineas,
    }


def explicar(boleto: Boleto, timeout_s: float = 8.0) -> str | None:
    """Explicación breve; ``None`` si la IA falla. Se guarda si el boleto no está confirmado."""
    import json

    prompt = PROMPT_EXPLICACION.format(datos=json.dumps(datos_explicacion(boleto), ensure_ascii=False))
    try:
        texto = call_gemini(prompt, max_output_tokens=400, timeout_s=timeout_s)
    except GeminiNoDisponibleError as exc:
        logger.warning("quiniela explicación no disponible: %s", exc)
        return None
    texto = texto.strip()[:1500]
    if not boleto.confirmado:
        boleto.explicacion = texto
        boleto.save(update_fields=["explicacion", "actualizado_at"])
    return texto
