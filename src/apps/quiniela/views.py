"""Vistas HTMX de la quiniela. Todas requieren ``staff_member_required`` (uso personal).

Los endpoints HTMX devuelven el panel completo de la jornada (partidos + boleto):
para una sola persona es más simple que sincronizar fragmentos sueltos.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services_boleto as sb
from .forms import JornadaForm, crear_formset, guardar_jornada
from .models import SIGNOS_PLENO, Boleto, Jornada, PartidoJornada
from .services_avisos import extraer_avisos
from .services_ingest import IngestError, ingest_cuotas_jornada, ingest_noticias, ingest_resultados_jornada
from .services_pronostico import calcular_pronostico_jornada
from .services_seguimiento import calibracion, evaluar_boleto, jornadas_de_temporada, ultimas_jornadas

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Contexto del panel
# --------------------------------------------------------------------------- #


def _panel_context(jornada: Jornada, error: str = "", aviso: str = "") -> dict:
    partidos = list(
        jornada.partidos.select_related("local", "visitante").prefetch_related("pronosticos", "avisos__noticia")
    )
    boleto = Boleto.objects.filter(jornada=jornada).first()
    lineas = {linea["posicion"]: linea for linea in boleto.lineas} if boleto else {}
    filas = [
        {
            "partido": p,
            "elegido": p.pronostico_elegido,
            "avisos": list(p.avisos.all()),
            "linea": lineas.get(p.posicion),
        }
        for p in partidos
    ]
    propuesta, error_propuesta = None, ""
    try:
        propuesta = sb.proponer(jornada)
    except sb.BoletoError as exc:
        error_propuesta = str(exc)
    return {
        "jornada": jornada,
        "filas": filas,
        "boleto": boleto,
        "propuesta": propuesta,
        "error_propuesta": error_propuesta,
        "error": error,
        "aviso": aviso,
        "signos_pleno": SIGNOS_PLENO,
        "pleno_partes": boleto.pleno.split("-") if boleto and boleto.pleno else ["", ""],
        "texto_copia": (
            " ".join(f"{i}:{lineas[i]['signos']}" for i in sorted(lineas)) + f" P15:{boleto.pleno or '?'}"
            if boleto
            else ""
        ),
    }


def _panel(request, jornada: Jornada, error: str = "", aviso: str = ""):
    return render(request, "quiniela/_panel.html", _panel_context(jornada, error, aviso))


# --------------------------------------------------------------------------- #
# Páginas
# --------------------------------------------------------------------------- #


@staff_member_required
def index(request):
    jornada = Jornada.objects.order_by("-fecha_cierre").first()
    if jornada is None:
        return redirect("quiniela:jornada_nueva")
    return redirect("quiniela:jornada_detalle", pk=jornada.pk)


@staff_member_required
def jornada_nueva(request):
    if request.method == "POST":
        form = JornadaForm(request.POST)
        formset = crear_formset(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                jornada = guardar_jornada(form, formset)
            try:
                ingest_cuotas_jornada(jornada)
            except IngestError as exc:
                messages.warning(request, f"Sin cuotas por ahora: {exc}")
            calcular_pronostico_jornada(jornada)
            return redirect("quiniela:jornada_detalle", pk=jornada.pk)
    else:
        form = JornadaForm()
        formset = crear_formset()
    return render(request, "quiniela/jornada_form.html", {"form": form, "formset": formset})


@staff_member_required
def jornada_detalle(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    contexto = _panel_context(jornada)
    contexto["jornadas"] = Jornada.objects.order_by("-fecha_cierre")[:10]
    return render(request, "quiniela/jornada.html", contexto)


@staff_member_required
def seguimiento(request):
    ultima = Jornada.objects.order_by("-fecha_cierre").first()
    temporada = request.GET.get("temporada") or (ultima.temporada if ultima else "")
    return render(
        request,
        "quiniela/seguimiento.html",
        {
            "temporada": temporada,
            "cal_temporada": calibracion(jornadas_de_temporada(temporada)) if temporada else None,
            "cal_ultimas": calibracion(ultimas_jornadas(10)),
        },
    )


# --------------------------------------------------------------------------- #
# Acciones HTMX (devuelven el panel)
# --------------------------------------------------------------------------- #


@staff_member_required
@require_POST
def actualizar_cuotas(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    try:
        res = ingest_cuotas_jornada(jornada)
    except IngestError as exc:
        return _panel(request, jornada, error=f"No se pudieron leer las cuotas: {exc}")
    calcular_pronostico_jornada(jornada)
    return _panel(request, jornada, aviso=f"Cuotas: {res.actualizados} partidos actualizados.")


@staff_member_required
@require_POST
def actualizar_noticias(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    noticias = ingest_noticias(jornada)
    res = extraer_avisos(jornada)
    if not res.disponible:
        return _panel(request, jornada, error="Avisos no disponibles: la IA no respondió.")
    resumen = f"{noticias.creados} noticias nuevas · {res.creados} avisos de {res.noticias} titulares."
    return _panel(request, jornada, aviso=resumen)


@staff_member_required
@require_POST
def generar(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    try:
        sb.generar_boleto(jornada, request.user, etiqueta=request.POST.get("configuracion") or None)
    except sb.BoletoError as exc:
        return _panel(request, jornada, error=str(exc))
    return _panel(request, jornada)


def _boleto_o_error(jornada: Jornada):
    boleto = Boleto.objects.filter(jornada=jornada).first()
    if boleto is None:
        raise sb.BoletoError("Primero genera el boleto.")
    return boleto


@staff_member_required
@require_POST
def sobrescribir(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    try:
        posicion = int(request.POST.get("posicion", "0"))
        signos = "".join(request.POST.getlist("signos"))
        sb.aplicar_sobrescritura(_boleto_o_error(jornada), posicion, signos)
    except (sb.BoletoError, ValueError) as exc:
        return _panel(request, jornada, error=str(exc))
    return _panel(request, jornada)


@staff_member_required
@require_POST
def pleno(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    valor = f"{request.POST.get('pleno_local', '')}-{request.POST.get('pleno_visitante', '')}"
    try:
        sb.fijar_pleno(_boleto_o_error(jornada), valor)
    except sb.BoletoError as exc:
        return _panel(request, jornada, error=str(exc))
    return _panel(request, jornada)


@staff_member_required
@require_POST
def explicar(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    try:
        texto = sb.explicar(_boleto_o_error(jornada))
    except sb.BoletoError as exc:
        return _panel(request, jornada, error=str(exc))
    if texto is None:
        return _panel(request, jornada, error="Explicación no disponible: la IA no respondió.")
    return _panel(request, jornada)


@staff_member_required
@require_POST
def confirmar(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    try:
        sb.confirmar(_boleto_o_error(jornada))
    except sb.BoletoError as exc:
        return _panel(request, jornada, error=str(exc))
    return _panel(request, jornada, aviso="Boleto confirmado. Ya no se puede modificar.")


@staff_member_required
@require_POST
def actualizar_resultados(request, pk: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    res = ingest_resultados_jornada(jornada)
    evaluar_boleto(jornada)
    return _panel(request, jornada, aviso=f"Resultados: {res.actualizados} partidos actualizados.")


@staff_member_required
@require_POST
def resultado_manual(request, pk: int, posicion: int):
    jornada = get_object_or_404(Jornada, pk=pk)
    partido = get_object_or_404(PartidoJornada, jornada=jornada, posicion=posicion)
    try:
        gl, gv = int(request.POST["goles_local"]), int(request.POST["goles_visitante"])
        if gl < 0 or gv < 0:
            raise ValueError
    except (KeyError, ValueError):
        return _panel(request, jornada, error=f"Goles no válidos en el partido {posicion}.")
    partido.goles_local, partido.goles_visitante = gl, gv
    partido.save(update_fields=["goles_local", "goles_visitante"])
    evaluar_boleto(jornada)
    return _panel(request, jornada)
