"""Capa 3: estimación de PVP vía Gemini (memoria estadística pre-entrenada).

Gemini no consulta nada en vivo — devuelve un precio aprendido durante el
entrenamiento desde fuentes públicas (km77.com, motor.es, web fabricante,
foros). Es decir: memoria estadística comprimida con ruido, no un crawler.
Esto implica:
- Drift temporal (datos hasta el corte del modelo, no MY26).
- Sesgo de popularidad (Golf/Niro precisos, variantes raras inventan).
- Hay que filtrar por `confidence` declarada y validar contra heurística.

Reusa la cascada `_call_gemini_generate` de `ask.services` (ya tiene
fallback ladder de 7 modelos resistente a 503/429/empty completions).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from apps.mubil.ask import services as ask_services
from apps.mubil.models import Vehicle

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceEstimate:
    price_eur: Optional[int]
    confidence: float
    raw: str  # respuesta sin parsear (para debug)


PROMPT_TEMPLATE = """Eres un experto en precios de coches nuevos en el mercado español 2026.

Dado un vehículo del catálogo IDAE, devuelve su PVP base recomendado (con IVA, sin opciones extra) en euros.

Reglas:
- Si conoces el modelo con certeza, devuelve confidence >= 0.7.
- Si tienes que extrapolar de un modelo similar, confidence 0.4-0.7.
- Si no tienes datos fiables, confidence < 0.4 y price_eur null.
- Responde ÚNICAMENTE un JSON válido en una línea, sin texto extra ni markdown.

Ejemplos (anclas verificadas 2026-05):
- Volkswagen Golf 1.5 TSI 150 Life (ICE, 2024) → {{"price_eur": 28500, "confidence": 0.95}}
- Tesla Model 3 RWD (BEV, 60 kWh, 513 km WLTP) → {{"price_eur": 39990, "confidence": 0.95}}
- Kia Niro EV Long Range (BEV, 64.8 kWh) → {{"price_eur": 41500, "confidence": 0.95}}
- Dacia Sandero 1.0 TCe 90 (ICE) → {{"price_eur": 13900, "confidence": 0.9}}
- BMW i4 eDrive40 (BEV, 83.9 kWh) → {{"price_eur": 60900, "confidence": 0.9}}

Vehículo a tasar:
- Marca: {make}
- Modelo / variante: {model}
- Año: {year}
- Propulsión: {propulsion}
- Batería: {battery_kwh} kWh
- Autonomía WLTP: {range_wltp_km} km
- Consumo: {consumption}

JSON:"""


_JSON_RE = re.compile(r"\{[^{}]*\}")


def _format_consumption(v: Vehicle) -> str:
    if v.consumption_kwh_100km:
        return f"{v.consumption_kwh_100km} kWh/100km"
    if v.consumption_l_100km:
        return f"{v.consumption_l_100km} L/100km"
    return "n/d"


def _build_prompt(v: Vehicle) -> str:
    return PROMPT_TEMPLATE.format(
        make=v.make,
        model=v.model[:140],  # IDAE a veces concatena hasta 200 chars
        year=v.year or "reciente",
        propulsion=v.propulsion,
        battery_kwh=v.battery_kwh if v.battery_kwh else "n/d",
        range_wltp_km=v.range_wltp_km if v.range_wltp_km else "n/d",
        consumption=_format_consumption(v),
    )


def _parse_response(text: str) -> PriceEstimate:
    """Extrae JSON `{price_eur, confidence}` tolerando ruido del modelo."""
    raw = text.strip()
    # Algunos modelos envuelven en ```json ... ```; quita fences si aparecen.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Si el modelo coló texto extra, agarra el primer objeto JSON.
    match = _JSON_RE.search(raw)
    if not match:
        return PriceEstimate(price_eur=None, confidence=0.0, raw=text)

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return PriceEstimate(price_eur=None, confidence=0.0, raw=text)

    price = data.get("price_eur")
    conf = float(data.get("confidence", 0.0) or 0.0)
    if price is None:
        return PriceEstimate(price_eur=None, confidence=conf, raw=text)
    try:
        return PriceEstimate(price_eur=int(price), confidence=conf, raw=text)
    except (TypeError, ValueError):
        return PriceEstimate(price_eur=None, confidence=conf, raw=text)


def estimate_price(v: Vehicle) -> PriceEstimate:
    """Pregunta a Gemini el PVP del vehículo y devuelve estimación + confianza."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY no está configurada.")
    prompt = _build_prompt(v)
    text = ask_services._call_gemini_generate(prompt)
    return _parse_response(text)


# ---------------------------------------------------------------- validation


def validate_against_heuristic(
    *, gemini_price: int, heuristic_price: int, tolerance_pct: float = 0.50,
) -> bool:
    """Acepta el precio Gemini si difiere < tolerance del heurístico.

    Si Gemini dice 80k y heurística 25k (factor 3,2), algo va mal: o el
    coche es realmente premium y la heurística falla (caso bueno), o
    Gemini alucinó. Sin verdad externa, marcamos para review en vez de
    sobrescribir. tolerance_pct=0.50 deja pasar diferencias razonables.
    """
    if heuristic_price <= 0:
        return False
    delta = abs(gemini_price - heuristic_price) / heuristic_price
    return delta <= tolerance_pct
