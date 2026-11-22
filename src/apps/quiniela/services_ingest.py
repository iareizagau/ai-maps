"""Ingesta de datos abiertos para la quiniela (tarea 4; design.md D2).

- Histórico, resultados y cuotas: CSV de football-data.co.uk.
- Cuotas de la semana: ``fixtures.csv`` de la misma fuente.
- Noticias: RSS (AS, Mundo Deportivo) y búsqueda Google News por equipo.
"""

from __future__ import annotations

import contextlib
import csv
import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import feedparser
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    Equipo,
    Jornada,
    Noticia,
    PartidoHistorico,
    PartidoJornada,
    resolver_equipo,
)

logger = logging.getLogger(__name__)

UK = ZoneInfo("Europe/London")
DIVISIONES = ("SP1", "SP2")
COLUMNAS_OBLIGATORIAS = ("Div", "Date", "HomeTeam", "AwayTeam")
# Orden de preferencia de cuotas (design.md D2): media de cierre, Bet365 de
# cierre y media previa. Pinnacle se descarta porque desaparece en 25-26.
PREFERENCIA_CUOTAS = (
    ("AvgC", ("AvgCH", "AvgCD", "AvgCA")),
    ("B365C", ("B365CH", "B365CD", "B365CA")),
    ("Avg", ("AvgH", "AvgD", "AvgA")),
    ("B365", ("B365H", "B365D", "B365A")),
)
USER_AGENT = "Mozilla/5.0 (compatible; quiniela-personal/1.0)"
TIMEOUT_S = 30
VENTANA_NOTICIAS = timedelta(days=7)
TOLERANCIA_FECHA = timedelta(days=1)


class IngestError(Exception):
    """La fuente no responde o devuelve un formato inesperado."""


@dataclass
class ResultadoIngesta:
    creados: int = 0
    actualizados: int = 0
    omitidos: int = 0
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"creados={self.creados} actualizados={self.actualizados} omitidos={self.omitidos}"


# --------------------------------------------------------------------------- #
# Descarga y parseo
# --------------------------------------------------------------------------- #


def descargar(url: str) -> bytes:
    """GET con redirecciones (``www.`` → host sin www) y errores explícitos."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S, allow_redirects=True)
    except requests.RequestException as exc:
        raise IngestError(f"No se pudo descargar {url}: {exc}") from exc
    if resp.status_code != 200:
        raise IngestError(f"{url} respondió {resp.status_code}")
    return resp.content


def parsear_csv(contenido: bytes | str) -> list[dict[str, str]]:
    """Lee un CSV de football-data (UTF-8 con BOM; latin-1 de respaldo)."""
    if isinstance(contenido, bytes):
        try:
            texto = contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = contenido.decode("latin-1")
    else:
        texto = contenido.lstrip("﻿")
    if texto.lstrip().startswith("<"):
        raise IngestError("La fuente devolvió HTML en lugar de CSV.")
    lector = csv.DictReader(io.StringIO(texto))
    columnas = lector.fieldnames or []
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in columnas]
    if faltan:
        raise IngestError(f"Formato inesperado: faltan columnas {faltan}")
    return [fila for fila in lector if (fila.get("Div") or "").strip()]


def parsear_fecha(fila: dict[str, str]) -> datetime:
    """``Date`` dd/mm/yyyy (o dd/mm/yy) + ``Time`` en hora del Reino Unido → aware."""
    crudo = (fila.get("Date") or "").strip()
    for formato in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            dia = datetime.strptime(crudo, formato).date()
            break
        except ValueError:
            continue
    else:
        raise IngestError(f"Fecha no reconocida: {crudo!r}")
    hora = time(0, 0)
    crudo_hora = (fila.get("Time") or "").strip()
    if crudo_hora:
        with contextlib.suppress(ValueError):
            hora = datetime.strptime(crudo_hora, "%H:%M").time()
    return datetime.combine(dia, hora, tzinfo=UK)


def _decimal(valor: str | None) -> Decimal | None:
    try:
        d = Decimal((valor or "").strip())
    except InvalidOperation:
        return None
    return d if d > 1 else None


def extraer_cuotas(fila: dict[str, str]) -> tuple[Decimal | None, Decimal | None, Decimal | None, str]:
    """Primer trío completo según ``PREFERENCIA_CUOTAS``; si no hay, (None, None, None, '')."""
    for tipo, columnas in PREFERENCIA_CUOTAS:
        valores = [_decimal(fila.get(c)) for c in columnas]
        if all(v is not None for v in valores):
            return valores[0], valores[1], valores[2], tipo
    return None, None, None, ""


def _goles(valor: str | None) -> int | None:
    try:
        return int((valor or "").strip())
    except ValueError:
        return None


def url_temporada(division: str, temporada: str) -> str:
    return f"{settings.QUINIELA_FD_BASE_URL}/mmz4281/{temporada}/{division}.csv"


def temporada_de(fecha: date) -> str:
    """Código yyYY de la temporada que contiene ``fecha`` (empieza en julio)."""
    inicio = fecha.year if fecha.month >= 7 else fecha.year - 1
    return f"{inicio % 100:02d}{(inicio + 1) % 100:02d}"


# --------------------------------------------------------------------------- #
# 4.1 Histórico por temporada
# --------------------------------------------------------------------------- #


def ingest_temporada(division: str, temporada: str, contenido: bytes | str | None = None) -> ResultadoIngesta:
    """Upsert idempotente de una temporada. Todo o nada (spec datos-jornada)."""
    if division not in DIVISIONES:
        raise IngestError(f"División no soportada: {division}")
    if contenido is None:
        contenido = descargar(url_temporada(division, temporada))
    filas = parsear_csv(contenido)

    res = ResultadoIngesta()
    with transaction.atomic():
        for fila in filas:
            if fila["Div"].strip() != division:
                res.omitidos += 1
                continue
            gl, gv = _goles(fila.get("FTHG")), _goles(fila.get("FTAG"))
            if gl is None or gv is None:
                res.omitidos += 1  # partido aún sin resultado
                continue
            local = resolver_equipo(fila["HomeTeam"])
            visitante = resolver_equipo(fila["AwayTeam"])
            if local is None or visitante is None:
                res.omitidos += 1
                continue
            c1, cx, c2, tipo = extraer_cuotas(fila)
            _, creado = PartidoHistorico.objects.update_or_create(
                fecha=parsear_fecha(fila).date(),
                local=local,
                visitante=visitante,
                defaults={
                    "division": division,
                    "temporada": temporada,
                    "goles_local": gl,
                    "goles_visitante": gv,
                    "cuota_1": c1,
                    "cuota_x": cx,
                    "cuota_2": c2,
                    "cuota_tipo": tipo,
                },
            )
            if creado:
                res.creados += 1
            else:
                res.actualizados += 1
    logger.info("quiniela ingest %s %s: %s", division, temporada, res)
    return res


# --------------------------------------------------------------------------- #
# Emparejar partidos de la jornada con filas de una fuente
# --------------------------------------------------------------------------- #


def _ventana_jornada(jornada: Jornada) -> tuple[datetime, datetime]:
    """Rango razonable de partidos de una jornada sin fecha propia."""
    return jornada.fecha_cierre - timedelta(days=2), jornada.fecha_cierre + timedelta(days=5)


def _encaja_fecha(partido: PartidoJornada, cuando: datetime) -> bool:
    if partido.fecha:
        return abs(cuando - partido.fecha) <= TOLERANCIA_FECHA + timedelta(hours=12)
    desde, hasta = _ventana_jornada(partido.jornada)
    return desde <= cuando <= hasta


# --------------------------------------------------------------------------- #
# 4.3 Cuotas de la semana
# --------------------------------------------------------------------------- #


def ingest_cuotas_jornada(jornada: Jornada, contenido: bytes | str | None = None) -> ResultadoIngesta:
    """Asocia cuotas previas de ``fixtures.csv`` a los partidos de la jornada."""
    if contenido is None:
        contenido = descargar(f"{settings.QUINIELA_FD_BASE_URL}/fixtures.csv")
    filas = [f for f in parsear_csv(contenido) if f["Div"].strip() in DIVISIONES]

    indice: dict[tuple[int, int], list[tuple[datetime, dict]]] = {}
    for fila in filas:
        local = resolver_equipo(fila["HomeTeam"], crear=False)
        visitante = resolver_equipo(fila["AwayTeam"], crear=False)
        if local and visitante:
            indice.setdefault((local.pk, visitante.pk), []).append((parsear_fecha(fila), fila))

    res = ResultadoIngesta()
    ahora = timezone.now()
    for partido in jornada.partidos.all():
        candidatos = [
            (cuando, fila)
            for cuando, fila in indice.get((partido.local_id, partido.visitante_id), [])
            if partido.local_id and _encaja_fecha(partido, cuando)
        ]
        if not candidatos:
            res.omitidos += 1
            continue
        cuando, fila = candidatos[0]
        c1, cx, c2, _tipo = extraer_cuotas(fila)
        if c1 is None:
            res.omitidos += 1
            continue
        partido.cuota_1, partido.cuota_x, partido.cuota_2 = c1, cx, c2
        partido.cuotas_capturadas_at = ahora
        if partido.fecha is None:
            partido.fecha = cuando
        partido.save(update_fields=["cuota_1", "cuota_x", "cuota_2", "cuotas_capturadas_at", "fecha"])
        res.actualizados += 1
    return res


# --------------------------------------------------------------------------- #
# 4.4 Resultados de la jornada
# --------------------------------------------------------------------------- #


def ingest_resultados_jornada(
    jornada: Jornada, contenidos: dict[str, bytes | str] | None = None
) -> ResultadoIngesta:
    """Refresca el histórico de la temporada y copia goles a la jornada.

    ``contenidos`` permite inyectar los CSV por división en tests.
    Los partidos fuera de SP1/SP2 se quedan sin resultado (entrada manual).
    """
    temporada = jornada.temporada
    for division in DIVISIONES:
        contenido = (contenidos or {}).get(division)
        try:
            ingest_temporada(division, temporada, contenido)
        except IngestError as exc:
            logger.warning("quiniela resultados %s %s: %s", division, temporada, exc)

    res = ResultadoIngesta()
    for partido in jornada.partidos.all():
        if partido.tiene_resultado:
            continue
        if partido.sin_historico:
            res.omitidos += 1
            continue
        historicos = PartidoHistorico.objects.filter(local_id=partido.local_id, visitante_id=partido.visitante_id)
        encontrado = next(
            (
                h
                for h in historicos
                if _encaja_fecha(partido, datetime.combine(h.fecha, time(12, 0), tzinfo=UK))
            ),
            None,
        )
        if encontrado is None:
            res.omitidos += 1
            continue
        partido.goles_local = encontrado.goles_local
        partido.goles_visitante = encontrado.goles_visitante
        partido.save(update_fields=["goles_local", "goles_visitante"])
        res.actualizados += 1
    return res


# --------------------------------------------------------------------------- #
# 4.5 Noticias
# --------------------------------------------------------------------------- #


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).casefold()


def patrones_equipo(equipo: Equipo) -> list[re.Pattern]:
    """Regex por nombre y alias (≥ 4 letras), sin acentos y por palabra completa."""
    textos = {equipo.nombre, *equipo.aliases.values_list("texto", flat=True)}
    return [
        re.compile(rf"(?<!\w){re.escape(_sin_acentos(t))}(?!\w)")
        for t in sorted(textos)
        if len(t.strip()) >= 4
    ]


def equipos_mencionados(texto: str, patrones: dict[int, list[re.Pattern]]) -> set[int]:
    limpio = _sin_acentos(texto)
    return {pk for pk, regs in patrones.items() if any(r.search(limpio) for r in regs)}


def url_google_news(equipo: Equipo) -> str:
    consulta = f'"{equipo.nombre}" (lesión OR baja OR convocatoria OR sancionado)'
    return f"https://news.google.com/rss/search?q={quote_plus(consulta)}&hl=es&gl=ES&ceid=ES:es"


def _fecha_entrada(entrada) -> datetime | None:
    estructura = entrada.get("published_parsed") or entrada.get("updated_parsed")
    if not estructura:
        return None
    return datetime(*estructura[:6], tzinfo=ZoneInfo("UTC"))


def _leer_feed(url: str) -> list:
    try:
        contenido = descargar(url)
    except IngestError as exc:
        logger.warning("quiniela RSS caído %s: %s", url, exc)
        return []
    feed = feedparser.parse(contenido)
    if feed.bozo and not feed.entries:
        logger.warning("quiniela RSS inválido %s: %s", url, feed.get("bozo_exception"))
        return []
    return list(feed.entries)


def ingest_noticias(
    jornada: Jornada,
    feeds: dict[str, list] | None = None,
    equipo_de_feed: dict[str, int] | None = None,
) -> ResultadoIngesta:
    """Recoge noticias de los últimos 7 días que mencionan equipos de la jornada.

    ``feeds`` permite inyectar ``{url: entradas}`` en tests; si es None se
    descargan los RSS de settings y, si está activo, Google News por equipo.
    ``equipo_de_feed`` asocia un feed a un equipo (búsquedas por equipo): sus
    entradas cuentan para ese equipo aunque el titular no lo nombre.
    """
    equipo_de_feed = dict(equipo_de_feed or {})
    equipos = {
        e.pk: e
        for e in Equipo.objects.filter(
            pk__in={pk for p in jornada.partidos.all() for pk in (p.local_id, p.visitante_id) if pk}
        ).prefetch_related("aliases")
    }
    patrones = {pk: patrones_equipo(e) for pk, e in equipos.items()}

    if feeds is None:
        urls = list(settings.QUINIELA_RSS_FEEDS)
        if settings.QUINIELA_GNEWS_ENABLED:
            for e in equipos.values():
                url = url_google_news(e)
                urls.append(url)
                equipo_de_feed[url] = e.pk
        feeds = {url: _leer_feed(url) for url in urls}

    res = ResultadoIngesta()
    limite = timezone.now() - VENTANA_NOTICIAS
    for url_feed, entradas in feeds.items():
        for entrada in entradas:
            enlace = (entrada.get("link") or "").strip()
            titulo = (entrada.get("title") or "").strip()
            publicada = _fecha_entrada(entrada)
            if not enlace or not titulo or publicada is None or publicada < limite:
                res.omitidos += 1
                continue
            mencionados = equipos_mencionados(f"{titulo} {entrada.get('summary', '')}", patrones)
            if url_feed in equipo_de_feed:
                mencionados.add(equipo_de_feed[url_feed])
            if not mencionados:
                res.omitidos += 1
                continue
            noticia, creada = Noticia.objects.get_or_create(
                url=enlace[:1000],
                defaults={"titulo": titulo[:500], "publicada_at": publicada, "feed": url_feed[:300]},
            )
            noticia.equipos.add(*mencionados)
            if creada:
                res.creados += 1
            else:
                res.actualizados += 1
    return res
