"""Utilidades compartidas por los comandos de la quiniela."""

from django.core.management.base import CommandError

from apps.quiniela.models import Jornada


def obtener_jornada(jornada_id: int | None) -> Jornada:
    """La jornada indicada o, si no se indica, la de fecha de cierre más reciente."""
    qs = Jornada.objects.all()
    jornada = qs.filter(pk=jornada_id).first() if jornada_id else qs.order_by("-fecha_cierre").first()
    if jornada is None:
        raise CommandError("No hay jornada" + (f" con id {jornada_id}" if jornada_id else " dada de alta"))
    return jornada
