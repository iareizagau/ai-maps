"""Ayudas para dar de alta la jornada sin teclear los 15 partidos.

1. ``parsear_lista``: interpreta una lista pegada desde la web o la app de
   Loterías ("1 Athletic - Espanyol", "Real Sociedad vs Sporting"…) y resuelve
   cada nombre contra el catálogo de alias.
2. ``proximos_partidos``: partidos de Primera y Segunda de los próximos días,
   sacados de ``fixtures.csv`` (fuente abierta), para elegirlos con un clic.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import Equipo, EquipoAlias
from .services_ingest import DIVISIONES, _sin_acentos, descargar, parsear_csv, parsear_fecha

MAX_PARTIDOS = 15
# Separadores entre local y visitante: guion con espacios, "vs", "v", raya o semirraya.
SEPARADOR = re.compile(r"\s+(?:-|\u2013|\u2014|vs\.?|v\.?)\s+|\s*[\u2013\u2014]\s*", re.IGNORECASE)
# Prefijos de posición: "1", "1.", "1)", "1 -", "P15", "Pleno al 15:", "15."
PREFIJO = re.compile(r"^\s*(?:pleno(?:\s+al)?\s*15\s*[:.)-]?|p\s*15\s*[:.)-]?|\d{1,2}\s*[.):-]?)\s+", re.IGNORECASE)
# Restos al final: signos o marcadores ("1 X 2", "1X2", horas "21:00").
COLA = re.compile(r"(?:\s+(?:[1x2]{1,3}|\d{1,2}:\d{2}))+\s*$", re.IGNORECASE)
UMBRAL_DIFUSO = 0.82


@dataclass
class LadoParseado:
    texto: str
    equipo: Equipo | None

    @property
    def reconocido(self) -> bool:
        return self.equipo is not None


@dataclass
class PartidoParseado:
    local: LadoParseado
    visitante: LadoParseado
    linea: str


def _indice_alias() -> dict[str, Equipo]:
    """Clave sin acentos → equipo, con nombres canónicos y alias."""
    indice: dict[str, Equipo] = {}
    for alias in EquipoAlias.objects.select_related("equipo"):
        indice[_sin_acentos(alias.texto)] = alias.equipo
    for equipo in Equipo.objects.all():
        indice.setdefault(_sin_acentos(equipo.nombre), equipo)
    return indice


# Abreviaturas habituales en boletos y en la web de Loterías.
ABREVIATURAS = (
    (re.compile(r"(?<!\w)r\.\s*"), "real "),
    (re.compile(r"(?<!\w)at\.\s*"), "atletico "),
    (re.compile(r"(?<!\w)ath\.\s*"), "athletic "),
    (re.compile(r"(?<!\w)dep\.\s*"), "deportivo "),
    (re.compile(r"(?<!\w)sp\.\s*"), "sporting "),
)
# Alias válidos solo en el boleto: en las noticias serían ambiguos.
ALIAS_BOLETO = {"deportivo": "La Coruna", "racing": "Santander", "atletico": "Ath Madrid"}


def resolver_nombre(texto: str, indice: dict[str, Equipo]) -> Equipo | None:
    """Exacto → alias del boleto → alias contenido como palabra (el más largo) → parecido difuso."""
    from .models import resolver_equipo

    clave = _sin_acentos(" ".join(texto.split()))
    for patron, sustituto in ABREVIATURAS:
        clave = patron.sub(sustituto, clave).strip()
    if not clave:
        return None
    if clave in ALIAS_BOLETO:
        return resolver_equipo(ALIAS_BOLETO[clave], crear=False)
    if clave in indice:
        return indice[clave]
    contenidos = [
        alias for alias in indice if len(alias) >= 4 and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", clave)
    ]
    if contenidos:
        return indice[max(contenidos, key=len)]
    parecido = difflib.get_close_matches(clave, list(indice), n=1, cutoff=UMBRAL_DIFUSO)
    return indice[parecido[0]] if parecido else None


def parsear_lista(texto: str) -> list[PartidoParseado]:
    """Hasta 15 partidos en el orden en que aparecen. Las líneas sin separador se ignoran."""
    indice = _indice_alias()
    partidos: list[PartidoParseado] = []
    for linea in (texto or "").splitlines():
        limpia = COLA.sub("", PREFIJO.sub("", linea.strip())).strip()
        partes = [p.strip(" .:;,") for p in SEPARADOR.split(limpia, maxsplit=1)]
        if len(partes) != 2 or not all(partes):
            continue
        local, visitante = partes
        partidos.append(
            PartidoParseado(
                local=LadoParseado(local, resolver_nombre(local, indice)),
                visitante=LadoParseado(visitante, resolver_nombre(visitante, indice)),
                linea=linea.strip(),
            )
        )
        if len(partidos) == MAX_PARTIDOS:
            break
    return partidos


def initial_formset(partidos: list[PartidoParseado]) -> list[dict]:
    """Datos iniciales para las 15 filas del formset (las que falten, vacías)."""
    filas = []
    for p in partidos:
        filas.append(
            {
                "local": p.local.equipo.pk if p.local.equipo else None,
                "local_texto": "" if p.local.equipo else p.local.texto,
                "visitante": p.visitante.equipo.pk if p.visitante.equipo else None,
                "visitante_texto": "" if p.visitante.equipo else p.visitante.texto,
            }
        )
    return filas + [{}] * (MAX_PARTIDOS - len(filas))


# --------------------------------------------------------------------------- #
# Foto o captura del boleto (Gemini Vision)
# --------------------------------------------------------------------------- #

MIMES_IMAGEN = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")
MAX_BYTES_IMAGEN = 8 * 1024 * 1024

PROMPT_IMAGEN = """Esta imagen es un boleto o una pantalla de La Quiniela (fútbol, España).
Extrae los partidos EN EL ORDEN en que aparecen (normalmente 14 más el Pleno al 15).

Devuelve SOLO líneas de texto, una por partido, con este formato exacto:
N Local - Visitante

Reglas:
- N es la posición (1 a 15). El 15 es el Pleno al 15.
- Copia los nombres de los equipos tal como se leen; no los traduzcas ni los completes.
- Si no se lee un equipo, escribe "?" en su lugar. No inventes partidos.
- Sin títulos, sin signos 1 X 2, sin explicaciones, sin markdown.
"""


class ImagenNoValidaError(ValueError):
    """La imagen no es de un tipo admitido o es demasiado grande."""


def lista_desde_imagen(datos: bytes, mime: str) -> str:
    """Texto "N Local - Visitante" por línea leído de una foto o captura del boleto.

    Una llamada a Gemini. Lanza ``ImagenNoValidaError`` o ``GeminiNoDisponibleError``.
    """
    from .services_gemini import call_gemini

    if mime not in MIMES_IMAGEN:
        raise ImagenNoValidaError(f"Formato no admitido ({mime}). Usa JPG, PNG, WEBP o HEIC.")
    if len(datos) > MAX_BYTES_IMAGEN:
        raise ImagenNoValidaError("La imagen pesa más de 8 MB.")
    texto = call_gemini(PROMPT_IMAGEN, max_output_tokens=800, timeout_s=30.0, imagen=(datos, mime))
    lineas = [linea.strip() for linea in texto.replace("```", "").splitlines() if linea.strip()]
    return "\n".join(lineas[:MAX_PARTIDOS])


# --------------------------------------------------------------------------- #
# Próximos partidos de liga (fixtures.csv)
# --------------------------------------------------------------------------- #

CACHE_CLAVE = "quiniela:fixtures"
CACHE_SEGUNDOS = 60 * 60


@dataclass
class Proximo:
    fecha: datetime
    division: str
    local: Equipo
    visitante: Equipo


def proximos_partidos(contenido: bytes | str | None = None, dias: int = 10) -> list[Proximo]:
    """Partidos de SP1/SP2 desde ayer hasta ``dias`` días vista, por fecha.

    El CSV se cachea una hora para no descargarlo en cada apertura del panel.
    Lanza ``IngestError`` si la fuente no responde.
    """
    if contenido is None:
        contenido = cache.get(CACHE_CLAVE)
        if contenido is None:
            contenido = descargar(f"{settings.QUINIELA_FD_BASE_URL}/fixtures.csv")
            cache.set(CACHE_CLAVE, contenido, CACHE_SEGUNDOS)
    desde = timezone.now() - timedelta(days=1)
    hasta = timezone.now() + timedelta(days=dias)
    indice = _indice_alias()
    proximos = []
    for fila in parsear_csv(contenido):
        if fila["Div"].strip() not in DIVISIONES:
            continue
        cuando = parsear_fecha(fila)
        if not desde <= cuando <= hasta:
            continue
        local = indice.get(_sin_acentos(fila["HomeTeam"]))
        visitante = indice.get(_sin_acentos(fila["AwayTeam"]))
        if local and visitante:
            proximos.append(Proximo(cuando, fila["Div"].strip(), local, visitante))
    return sorted(proximos, key=lambda p: (p.fecha, p.division))
