"""Avisos de bajas y dudas extraídos con IA (tarea 6.2; spec avisos-noticias).

Gemini lee los titulares ya recogidos y devuelve avisos con un esquema cerrado.
Cada aviso tiene que citar una de las noticias numeradas que se le pasan; lo
que no cite una noticia real, o hable de un equipo que no juega la jornada, se
descarta. Los avisos son solo informativos: no tocan ``Pronostico``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import Aviso, Jornada, Noticia
from .services_gemini import GeminiNoDisponibleError, call_gemini, parsear_json
from .services_ingest import VENTANA_NOTICIAS

logger = logging.getLogger(__name__)

MAX_NOTICIAS_POR_EQUIPO = 12
TIPOS_VALIDOS = {t.value for t in Aviso.Tipo}

PROMPT = """Eres un analista de fútbol. Abajo tienes titulares recientes numerados,
agrupados por equipo (con su id). Extrae SOLO avisos sobre jugadores que pueden
faltar o estar mermados en el próximo partido: lesiones, sanciones, dudas y
rotaciones anunciadas. Ignora fichajes, resultados pasados, crónicas y rumores
sin relación con la disponibilidad.

Devuelve EXCLUSIVAMENTE un array JSON (sin ``` ni texto extra). Cada elemento:
{{"equipo_id": int, "jugador": string ("" si no se nombra), "tipo": "lesion" | "sancion" | "duda" | "rotacion" | "otro",
  "resumen": string (máx. 20 palabras, en español), "noticia": int (número del titular que lo dice)}}

Reglas:
- Usa SOLO lo que dicen los titulares. No inventes jugadores ni datos.
- Cada aviso DEBE citar el número de un titular de la lista.
- Si no hay avisos, devuelve [].

Titulares:
{titulares}
"""


@dataclass
class ResultadoAvisos:
    disponible: bool
    creados: int = 0
    descartados: int = 0
    noticias: int = 0
    error: str = ""


def noticias_de_la_jornada(jornada: Jornada) -> dict[int, list[Noticia]]:
    """Noticias recientes por equipo de la jornada (más nuevas primero)."""
    limite = timezone.now() - VENTANA_NOTICIAS
    por_equipo: dict[int, list[Noticia]] = {}
    for partido in jornada.partidos.select_related("local", "visitante"):
        for equipo in (partido.local, partido.visitante):
            if equipo is None or equipo.pk in por_equipo:
                continue
            por_equipo[equipo.pk] = list(
                equipo.noticias.filter(publicada_at__gte=limite).order_by("-publicada_at")[:MAX_NOTICIAS_POR_EQUIPO]
            )
    return por_equipo


def construir_prompt(jornada: Jornada, por_equipo: dict[int, list[Noticia]]) -> tuple[str, dict[int, Noticia]]:
    """Prompt con titulares numerados y el índice número → noticia."""
    nombres = {
        e.pk: e.nombre
        for p in jornada.partidos.select_related("local", "visitante")
        for e in (p.local, p.visitante)
        if e is not None
    }
    indice: dict[int, Noticia] = {}
    lineas: list[str] = []
    for equipo_id, noticias in por_equipo.items():
        if not noticias:
            continue
        lineas.append(f"## {nombres[equipo_id]} (equipo_id={equipo_id})")
        for noticia in noticias:
            n = len(indice) + 1
            indice[n] = noticia
            lineas.append(f"[{n}] {noticia.titulo}")
    return PROMPT.format(titulares="\n".join(lineas)), indice


def validar_avisos(
    crudos, indice: dict[int, Noticia], partido_de_equipo: dict[int, int]
) -> tuple[list[dict], int]:
    """Filtra la respuesta de la IA según el esquema cerrado. Devuelve (válidos, descartados)."""
    if not isinstance(crudos, list):
        return [], 1
    validos: list[dict] = []
    vistos: set[tuple] = set()
    descartados = 0
    for item in crudos:
        if not isinstance(item, dict):
            descartados += 1
            continue
        try:
            equipo_id = int(item.get("equipo_id"))
            num_noticia = int(item.get("noticia"))
        except (TypeError, ValueError):
            descartados += 1
            continue
        noticia = indice.get(num_noticia)
        if noticia is None or equipo_id not in partido_de_equipo:
            logger.info("quiniela aviso descartado (noticia=%s, equipo=%s)", num_noticia, equipo_id)
            descartados += 1
            continue
        tipo = str(item.get("tipo") or "").strip().lower()
        if tipo not in TIPOS_VALIDOS:
            tipo = Aviso.Tipo.OTRO
        jugador = str(item.get("jugador") or "").strip()[:120]
        resumen = str(item.get("resumen") or "").strip()[:300]
        if not resumen:
            descartados += 1
            continue
        clave = (equipo_id, jugador.casefold(), tipo)
        if clave in vistos:
            continue
        vistos.add(clave)
        validos.append(
            {
                "partido_id": partido_de_equipo[equipo_id],
                "equipo_id": equipo_id,
                "jugador": jugador,
                "tipo": tipo,
                "resumen": resumen,
                "noticia": noticia,
            }
        )
    return validos, descartados


def extraer_avisos(jornada: Jornada) -> ResultadoAvisos:
    """Una llamada a Gemini por jornada. Si falla, se conservan los avisos previos
    y se guarda el motivo en ``jornada.avisos_error`` para mostrar el banner."""
    por_equipo = noticias_de_la_jornada(jornada)
    prompt, indice = construir_prompt(jornada, por_equipo)
    partido_de_equipo = {
        e: p.pk for p in jornada.partidos.all() for e in (p.local_id, p.visitante_id) if e is not None
    }

    if not indice:
        with transaction.atomic():
            Aviso.objects.filter(partido__jornada=jornada).delete()
            jornada.avisos_at, jornada.avisos_error = timezone.now(), ""
            jornada.save(update_fields=["avisos_at", "avisos_error"])
        return ResultadoAvisos(disponible=True)

    try:
        crudos = parsear_json(call_gemini(prompt))
    except (GeminiNoDisponibleError, ValueError) as exc:
        logger.warning("quiniela avisos no disponibles para %s: %s", jornada, exc)
        jornada.avisos_error = str(exc)[:300] or "Error desconocido"
        jornada.save(update_fields=["avisos_error"])
        return ResultadoAvisos(disponible=False, noticias=len(indice), error=jornada.avisos_error)

    validos, descartados = validar_avisos(crudos, indice, partido_de_equipo)
    with transaction.atomic():
        Aviso.objects.filter(partido__jornada=jornada).delete()
        Aviso.objects.bulk_create(Aviso(**v) for v in validos)
        jornada.avisos_at, jornada.avisos_error = timezone.now(), ""
        jornada.save(update_fields=["avisos_at", "avisos_error"])
    return ResultadoAvisos(disponible=True, creados=len(validos), descartados=descartados, noticias=len(indice))
