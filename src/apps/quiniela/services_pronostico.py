"""Pronóstico por partido de la jornada (tarea 5.4; spec pronostico).

Precedencia: cuotas > modelo > uniforme ("sin datos"). Se guarda una fila
``Pronostico`` por fuente disponible; la elegida se deriva al leer.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Jornada, PartidoHistorico, PartidoJornada, Pronostico
from .services_modelo import (
    ModeloPoisson,
    PartidoModelo,
    ajustar_modelo,
    distribucion_pleno,
    probs_1x2,
    probs_desde_cuotas,
)

logger = logging.getLogger(__name__)

VENTANA_ENTRENAMIENTO = timedelta(days=730)  # ~2 temporadas (design.md D4)
UNIFORME = (1 / 3, 1 / 3, 1 / 3)


def partidos_para_modelo(fecha_corte: date, ventana: timedelta = VENTANA_ENTRENAMIENTO) -> list[PartidoModelo]:
    filas = PartidoHistorico.objects.filter(fecha__lt=fecha_corte, fecha__gte=fecha_corte - ventana).values_list(
        "fecha", "division", "local_id", "visitante_id", "goles_local", "goles_visitante"
    )
    return [PartidoModelo(*fila) for fila in filas]


def fecha_corte_jornada(jornada: Jornada) -> date:
    """Primer día con partidos de la jornada (o el del cierre si no hay fechas)."""
    fechas = [p.fecha for p in jornada.partidos.all() if p.fecha]
    referencia = min(fechas) if fechas else jornada.fecha_cierre
    return timezone.localtime(referencia).date()


def entrenar_modelo(fecha_corte: date) -> ModeloPoisson | None:
    datos = partidos_para_modelo(fecha_corte)
    if not datos:
        return None
    return ajustar_modelo(datos, fecha_corte, xi=settings.QUINIELA_DECAY_XI, rho=settings.QUINIELA_DC_RHO)


def _guardar(partido: PartidoJornada, fuente: str, probs: tuple[float, float, float], pleno=None, ahora=None):
    Pronostico.objects.update_or_create(
        partido=partido,
        fuente=fuente,
        defaults={"p1": probs[0], "px": probs[1], "p2": probs[2], "pleno_dist": pleno, "calculado_at": ahora},
    )


def calcular_pronostico_jornada(jornada: Jornada, modelo: ModeloPoisson | None = None) -> dict[str, int]:
    """Recalcula y guarda las probabilidades de los 15 partidos. Devuelve el recuento por fuente."""
    if modelo is None:
        modelo = entrenar_modelo(fecha_corte_jornada(jornada))
    minimo = settings.QUINIELA_MIN_PARTIDOS
    ahora = timezone.now()
    recuento = {"cuotas": 0, "modelo": 0, "uniforme": 0}

    with transaction.atomic():
        for partido in jornada.partidos.all():
            fuentes: set[str] = set()

            if partido.tiene_cuotas:
                probs = probs_desde_cuotas(
                    partido.cuota_1, partido.cuota_x, partido.cuota_2, settings.QUINIELA_METODO_CUOTAS
                )
                _guardar(partido, Pronostico.Fuente.CUOTAS, probs, ahora=ahora)
                fuentes.add(Pronostico.Fuente.CUOTAS)

            con_modelo = (
                modelo is not None
                and not partido.sin_historico
                and modelo.conoce(partido.local_id, minimo)
                and modelo.conoce(partido.visitante_id, minimo)
            )
            if con_modelo:
                matriz = modelo.matriz_goles(partido.local_id, partido.visitante_id)
                pleno = distribucion_pleno(matriz) if partido.es_pleno else None
                _guardar(partido, Pronostico.Fuente.MODELO, probs_1x2(matriz), pleno=pleno, ahora=ahora)
                fuentes.add(Pronostico.Fuente.MODELO)

            if not fuentes:
                _guardar(partido, Pronostico.Fuente.UNIFORME, UNIFORME, ahora=ahora)
                fuentes.add(Pronostico.Fuente.UNIFORME)

            # Fuentes que ya no aplican (p. ej. cuotas retiradas, uniforme superado).
            partido.pronosticos.exclude(fuente__in=fuentes).delete()
            recuento[min(fuentes, key=Pronostico.PRECEDENCIA.index)] += 1

    logger.info("quiniela pronóstico %s: %s", jornada, recuento)
    return recuento
