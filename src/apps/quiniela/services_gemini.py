"""Llamada a Gemini con la ladder de fallback del proyecto (tarea 6.1; design.md D6).

Tercera copia consciente del patrón de ``mubil.ask.services._call_gemini_generate``
y ``amenabar.services_match._call_gemini_json``: importar un helper privado de
otra app acopla más que duplicar 50 líneas. TODO: consolidar las tres en
``apps.core`` en un cambio aparte.

Diferencias con la copia de amenabar: timeout por petición y parseo JSON tolerante.
"""

from __future__ import annotations

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

_FALLBACK_MARKERS = (
    "429",
    "quota",
    "rate",
    "resource_exhausted",
    "503",
    "unavailable",
    "temporarily",
    "timeout",
    "timed out",
    "deadline",
)
_HARD_ERROR_MARKERS = ("401", "403", "permission", "unauthenticated", "api key")


class GeminiNoDisponibleError(RuntimeError):
    """Gemini no está configurado o todos los modelos de la ladder fallaron."""


def _should_fallback(exc: Exception) -> bool:
    msg = (str(exc) or "").lower()
    if any(m in msg for m in _HARD_ERROR_MARKERS):
        return False
    return any(m in msg for m in _FALLBACK_MARKERS)


def _ladder() -> list[str]:
    ladder = list(getattr(settings, "GEMINI_GENERATION_FALLBACK_MODELS", []) or [])
    if ladder:
        return ladder
    primary = getattr(settings, "GEMINI_GENERATION_MODEL", None)
    return [primary] if primary else []


def call_gemini(
    prompt: str,
    max_output_tokens: int = 1500,
    timeout_s: float = 20.0,
    imagen: tuple[bytes, str] | None = None,
) -> str:
    """Texto crudo de la primera respuesta no vacía de la ladder.

    503/429/timeout avanzan al siguiente modelo; errores de autenticación cortan.
    Cualquier fallo final se convierte en ``GeminiNoDisponibleError``.
    ``imagen`` = (bytes, mime): solo se usan los modelos ``gemini-*`` de la
    ladder, porque los Gemma del final no aceptan imágenes.
    """
    if not getattr(settings, "GEMINI_API_KEY", ""):
        raise GeminiNoDisponibleError("GEMINI_API_KEY no está configurada.")
    ladder = _ladder()
    if imagen is not None:
        ladder = [m for m in ladder if m.startswith("gemini")]
    if not ladder:
        raise GeminiNoDisponibleError("No hay modelos de Gemini configurados.")

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
    )
    cfg = types.GenerateContentConfig(temperature=0.1, max_output_tokens=max_output_tokens)
    contenido = prompt
    if imagen is not None:
        datos, mime = imagen
        contenido = [types.Part.from_bytes(data=datos, mime_type=mime), prompt]

    ultimo: Exception | None = None
    for modelo in ladder:
        try:
            respuesta = client.models.generate_content(model=modelo, contents=contenido, config=cfg)
        except Exception as exc:
            if _should_fallback(exc):
                logger.warning("quiniela Gemini %s falló (%s); siguiente modelo.", modelo, exc)
                ultimo = exc
                continue
            raise GeminiNoDisponibleError(f"{modelo}: {exc}") from exc
        texto = (respuesta.text or "").strip()
        if not texto:
            logger.warning("quiniela Gemini %s devolvió texto vacío; siguiente modelo.", modelo)
            ultimo = RuntimeError(f"{modelo} vacío")
            continue
        return texto
    raise GeminiNoDisponibleError(f"Todos los modelos fallaron: {ultimo}")


def parsear_json(texto: str):
    """JSON de la respuesta, tolerando bloques ```json … ``` y texto alrededor."""
    limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        pass
    m = re.search(r"(\[.*\]|\{.*\})", limpio, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    raise ValueError("La respuesta de Gemini no es JSON válido.")
