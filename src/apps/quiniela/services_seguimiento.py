"""Seguimiento y backtest (tarea 8; spec seguimiento; design.md D9).

- ``evaluar_boleto``: aciertos del boleto confirmado de una jornada con resultados.
- ``calibracion``: Brier y acierto por fuente, sobrescrituras del usuario, gasto.
- ``backtest``: modelo frente a cuotas de cierre, walk-forward por semana.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import QuerySet

from .models import SIGNOS_1X2, Boleto, Jornada, PartidoHistorico, Pronostico
from .services_modelo import PartidoModelo, ajustar_modelo, probs_desde_cuotas
from .services_pronostico import VENTANA_ENTRENAMIENTO

FUENTES_MEDIBLES = (Pronostico.Fuente.CUOTAS, Pronostico.Fuente.MODELO)
EPS = 1e-12


def brier(probs: dict[str, float], resultado: str) -> float:
    """Brier multiclase: Σ (p_s - y_s)² sobre 1/X/2 (0 = perfecto, 2 = peor)."""
    return sum((probs[s] - (1.0 if s == resultado else 0.0)) ** 2 for s in SIGNOS_1X2)


def logloss(probs: dict[str, float], resultado: str) -> float:
    return -math.log(max(probs[resultado], EPS))


def favorito(probs: dict[str, float]) -> str:
    return max(SIGNOS_1X2, key=lambda s: probs[s])


# --------------------------------------------------------------------------- #
# 8.1 Evaluación del boleto
# --------------------------------------------------------------------------- #


def evaluar_boleto(jornada: Jornada) -> Boleto | None:
    """Rellena ``aciertos`` y ``pleno_acertado`` del boleto confirmado (si lo hay)."""
    boleto = Boleto.objects.filter(jornada=jornada, confirmado_at__isnull=False).first()
    if boleto is None or not jornada.tiene_resultados:
        return None
    resultados = {p.posicion: p for p in jornada.partidos.all()}
    boleto.aciertos = sum(
        1 for linea in boleto.lineas if resultados[linea["posicion"]].signo_resultado in linea["signos"]
    )
    boleto.pleno_acertado = boleto.pleno == resultados[15].pleno_resultado
    boleto.save(update_fields=["aciertos", "pleno_acertado"])
    return boleto


# --------------------------------------------------------------------------- #
# 8.2 Calibración
# --------------------------------------------------------------------------- #


@dataclass
class MetricaFuente:
    n: int = 0
    brier: float = 0.0
    logloss: float = 0.0
    aciertos: int = 0

    def anadir(self, probs: dict[str, float], resultado: str) -> None:
        self.n += 1
        self.brier += brier(probs, resultado)
        self.logloss += logloss(probs, resultado)
        self.aciertos += favorito(probs) == resultado

    @property
    def brier_medio(self) -> float | None:
        return self.brier / self.n if self.n else None

    @property
    def logloss_medio(self) -> float | None:
        return self.logloss / self.n if self.n else None

    @property
    def tasa_acierto(self) -> float | None:
        return self.aciertos / self.n if self.n else None


@dataclass
class Calibracion:
    fuentes: dict[str, MetricaFuente] = field(default_factory=dict)
    sobrescrituras: int = 0
    sobrescrituras_acertadas: int = 0
    propuesta_habria_acertado: int = 0
    jornadas: list[dict] = field(default_factory=list)  # {jornada, configuracion, coste, aciertos, pleno}
    gasto_total: Decimal = Decimal("0")


def calibracion(jornadas: QuerySet[Jornada]) -> Calibracion:
    cal = Calibracion(fuentes={f: MetricaFuente() for f in FUENTES_MEDIBLES})
    jornadas = jornadas.prefetch_related("partidos__pronosticos").select_related("boleto")
    for jornada in jornadas:
        partidos = {p.posicion: p for p in jornada.partidos.all()}
        for partido in partidos.values():
            resultado = partido.signo_resultado
            if resultado is None or partido.es_pleno:
                continue
            for pron in partido.pronosticos.all():
                if pron.fuente in cal.fuentes:
                    cal.fuentes[pron.fuente].anadir(pron.probs, resultado)

        boleto = getattr(jornada, "boleto", None)
        if boleto is None or not boleto.confirmado:
            continue
        cal.gasto_total += boleto.coste
        cal.jornadas.append(
            {
                "jornada": jornada,
                "configuracion": boleto.configuracion,
                "coste": boleto.coste,
                "aciertos": boleto.aciertos,
                "pleno": boleto.pleno_acertado,
            }
        )
        snapshot = boleto.probabilidades_snapshot or {}
        for linea in boleto.lineas:
            partido = partidos.get(linea["posicion"])
            if linea["origen"] != "usuario" or partido is None or partido.signo_resultado is None:
                continue
            cal.sobrescrituras += 1
            cal.sobrescrituras_acertadas += partido.signo_resultado in linea["signos"]
            probs = snapshot.get(str(linea["posicion"]))
            if probs:
                cal.propuesta_habria_acertado += favorito(probs) == partido.signo_resultado
    return cal


def jornadas_de_temporada(temporada: str) -> QuerySet[Jornada]:
    return Jornada.objects.filter(temporada=temporada)


def ultimas_jornadas(n: int = 10) -> QuerySet[Jornada]:
    ids = list(Jornada.objects.order_by("-fecha_cierre").values_list("pk", flat=True)[:n])
    return Jornada.objects.filter(pk__in=ids)


# --------------------------------------------------------------------------- #
# 8.3 Backtest
# --------------------------------------------------------------------------- #


@dataclass
class ResultadoBacktest:
    por_division: dict[str, dict[str, MetricaFuente]]
    total: dict[str, MetricaFuente]
    ajustes: int
    omitidos: int  # partidos sin cuotas o con equipos sin histórico suficiente


def _semana(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return iso[0], iso[1]


def backtest(
    temporadas: list[str],
    divisiones: list[str] | None = None,
    xi: float | None = None,
    rho: float | None = None,
    minimo: int | None = None,
    metodo_cuotas: str = "proporcional",
    ventana: timedelta = VENTANA_ENTRENAMIENTO,
) -> ResultadoBacktest:
    """Pronostica cada partido con el modelo entrenado solo con partidos anteriores
    a su semana y lo compara con las cuotas de cierre en el mismo conjunto."""
    xi = settings.QUINIELA_DECAY_XI if xi is None else xi
    rho = settings.QUINIELA_DC_RHO if rho is None else rho
    minimo = settings.QUINIELA_MIN_PARTIDOS if minimo is None else minimo
    divisiones = divisiones or ["SP1", "SP2"]

    todos = list(
        PartidoHistorico.objects.order_by("fecha", "id").values_list(
            "fecha", "division", "local_id", "visitante_id", "goles_local", "goles_visitante"
        )
    )
    historico = [PartidoModelo(*f) for f in todos]
    objetivo = list(
        PartidoHistorico.objects.filter(
            temporada__in=temporadas, division__in=divisiones, cuota_1__isnull=False
        ).order_by("fecha", "id")
    )

    por_semana: dict[tuple[int, int], list[PartidoHistorico]] = defaultdict(list)
    for p in objetivo:
        por_semana[_semana(p.fecha)].append(p)

    por_division = {d: {f: MetricaFuente() for f in FUENTES_MEDIBLES} for d in divisiones}
    total = {f: MetricaFuente() for f in FUENTES_MEDIBLES}
    ajustes = omitidos = 0
    for clave in sorted(por_semana):
        partidos = por_semana[clave]
        corte = min(p.fecha for p in partidos)
        datos = [h for h in historico if corte - ventana <= h.fecha < corte]
        if not datos:
            omitidos += len(partidos)
            continue
        modelo = ajustar_modelo(datos, corte, xi=xi, rho=rho)
        ajustes += 1
        for p in partidos:
            if not (modelo.conoce(p.local_id, minimo) and modelo.conoce(p.visitante_id, minimo)):
                omitidos += 1
                continue
            resultado = p.signo
            pm = dict(zip(SIGNOS_1X2, modelo.predecir(p.local_id, p.visitante_id, p.division), strict=True))
            pc = dict(
                zip(SIGNOS_1X2, probs_desde_cuotas(p.cuota_1, p.cuota_x, p.cuota_2, metodo_cuotas), strict=True)
            )
            for fuente, probs in ((Pronostico.Fuente.MODELO, pm), (Pronostico.Fuente.CUOTAS, pc)):
                por_division[p.division][fuente].anadir(probs, resultado)
                total[fuente].anadir(probs, resultado)
    return ResultadoBacktest(por_division=por_division, total=total, ajustes=ajustes, omitidos=omitidos)
