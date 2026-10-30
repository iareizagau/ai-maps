"""Match-maker for Amenabar promotions.

Pipeline (see openspec/changes/amenabar-matchmaker/design.md):

    extract_preferences  (Gemini, JSON schema cerrado)
            ↓
    rank_promociones     (puro Django ORM + PostGIS, SIN LLM)
            ↓
    generate_explanation (Gemini, SÓLO redacta sobre breakdown ya calculado)

Anti-alucinación por arquitectura: Gemini nunca ve el catálogo. Decide el SQL.

Gemini helper (_call_gemini_json) duplica el patrón de fallback ladder de
`apps.mubil.ask.services._call_gemini_generate`. Se duplica a propósito
(unas ~40 líneas) para no acoplar `amenabar` a privados de `mubil`; cuando
tengamos un tercer consumidor, refactorizamos a `apps.core.gemini`.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance

from .models import POI, Promocion

if TYPE_CHECKING:
    from .models import AirQualityStation, PromocionClima, SolarPotential  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- preferences

VALID_CLIMATE: frozenset[str] = frozenset({"coastal", "mild", "warm", "cold", "any"})
VALID_POI_CATEGORIES: frozenset[str] = frozenset(c.value for c in POI.Categoria)


@dataclass(frozen=True)
class MatchPreferences:
    budget_eur_min: int = 0
    budget_eur_max: int = 0  # 0 = sin tope
    bedrooms_min: int = 0
    cities: tuple[str, ...] = ()
    must_near: tuple[str, ...] = ()
    nice_to_have: tuple[str, ...] = ()
    climate_preference: str = "any"
    prefers_sunny: bool = False
    prefers_clean_air: bool = False
    destination_city: str = ""
    summary: str = ""

    def __post_init__(self):
        """Normalise out-of-range values to safe defaults — never raise."""
        # Clamp non-negative integers
        for name in ("budget_eur_min", "budget_eur_max", "bedrooms_min"):
            v = getattr(self, name)
            if not isinstance(v, int) or v < 0:
                object.__setattr__(self, name, 0)

        # Climate preference ∈ VALID_CLIMATE
        if self.climate_preference not in VALID_CLIMATE:
            object.__setattr__(self, "climate_preference", "any")

        # must_near / nice_to_have filtered to known POI categories, dedup, upper
        def _clean(seq) -> tuple[str, ...]:
            seen: list[str] = []
            for x in seq or ():
                if not isinstance(x, str):
                    continue
                code = x.strip().upper()
                if code in VALID_POI_CATEGORIES and code not in seen:
                    seen.append(code)
            return tuple(seen)

        object.__setattr__(self, "must_near", _clean(self.must_near))
        object.__setattr__(self, "nice_to_have", _clean(self.nice_to_have))

        # Cities: lower-cased, stripped, dedup
        def _norm_cities(seq) -> tuple[str, ...]:
            seen: list[str] = []
            for x in seq or ():
                if not isinstance(x, str):
                    continue
                c = x.strip().lower()
                if c and c not in seen:
                    seen.append(c)
            return tuple(seen)

        object.__setattr__(self, "cities", _norm_cities(self.cities))

        # Strings
        for name in ("destination_city", "summary"):
            v = getattr(self, name)
            if not isinstance(v, str):
                object.__setattr__(self, name, "")

        # Booleans
        for name in ("prefers_sunny", "prefers_clean_air"):
            object.__setattr__(self, name, bool(getattr(self, name)))


# ---------------------------------------------------------------- Gemini helper


_FALLBACK_MARKERS = ("429", "quota", "rate", "resource_exhausted", "503", "unavailable", "temporarily")
_HARD_ERROR_MARKERS = ("401", "403", "permission", "unauthenticated", "api key")


def _should_fallback(exc: Exception) -> bool:
    msg = (str(exc) or "").lower()
    if any(m in msg for m in _HARD_ERROR_MARKERS):
        return False
    return any(m in msg for m in _FALLBACK_MARKERS)


def _generation_ladder() -> list[str]:
    ladder = list(getattr(settings, "GEMINI_GENERATION_FALLBACK_MODELS", []) or [])
    if ladder:
        return ladder
    primary = getattr(settings, "GEMINI_GENERATION_MODEL", None)
    return [primary] if primary else []


def _call_gemini_json(prompt: str, max_output_tokens: int = 800) -> str:
    """Call Gemini with the project fallback ladder. Returns raw text.

    Duplicates on purpose the pattern of `mubil.ask.services._call_gemini_generate`.
    Keep in sync when the SDK or the ladder convention changes.
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=max_output_tokens,
    )

    ladder = _generation_ladder()
    if not ladder:
        raise RuntimeError("No Gemini generation model configured.")

    last_exc: Exception | None = None
    for model in ladder:
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=cfg)
        except Exception as e:
            if _should_fallback(e):
                logger.warning("Gemini %s soft-failed (%s) — falling through.", model, e)
                last_exc = e
                continue
            raise
        text = (response.text or "").strip()
        if not text:
            logger.warning("Gemini %s returned empty text — falling through.", model)
            last_exc = RuntimeError(f"{model} returned empty completion")
            continue
        if model != ladder[0]:
            logger.info("Gemini fallback succeeded with %s.", model)
        return text

    raise last_exc or RuntimeError("All Gemini models in the ladder failed.")


# ---------------------------------------------------------------- extraction


_EXTRACTION_PROMPT = """Eres un extractor de preferencias inmobiliarias. Devuelve EXCLUSIVAMENTE
un JSON válido (sin ```, sin texto adicional) con este esquema cerrado:

{{
  "budget_eur_min": int (0 si no se menciona),
  "budget_eur_max": int (0 si no se menciona),
  "bedrooms_min": int (0 si no se menciona),
  "cities": [string] (ciudades mencionadas, en minúsculas),
  "must_near": [string] (categorías de servicios imprescindibles, uno o varios de: {categorias}),
  "nice_to_have": [string] (categorías deseables, mismo enum que must_near),
  "climate_preference": string (uno de: coastal, mild, warm, cold, any),
  "prefers_sunny": bool,
  "prefers_clean_air": bool,
  "destination_city": string (ciudad de destino diario si se menciona teletrabajo/oficina/trabajo),
  "summary": string (una frase breve en español resumiendo lo que busca)
}}

Reglas:
- Si un campo no está claro, usa el default (0, "", [], false, "any").
- NO inventes campos adicionales.
- NO uses markdown, bloque de código ni comentarios.
- "coastal" = costa / cerca del mar; "cold" = montaña / interior / clima frío;
  "warm" = clima cálido / sur; "mild" = templado; "any" = cualquiera.

Texto del usuario:
{texto}

JSON:"""


def _strip_code_fence(s: str) -> str:
    """Gemini sometimes wraps JSON in ```json … ``` despite instructions."""
    t = s.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def extract_preferences(user_text: str) -> MatchPreferences:
    """LLM extraction with keyword fallback. Never raises on bad input."""
    if not user_text or not user_text.strip():
        return MatchPreferences()

    cats = ", ".join(sorted(VALID_POI_CATEGORIES))
    prompt = _EXTRACTION_PROMPT.format(categorias=cats, texto=user_text.strip())

    try:
        raw = _call_gemini_json(prompt, max_output_tokens=600)
        payload = json.loads(_strip_code_fence(raw))
        if not isinstance(payload, dict):
            raise ValueError(f"Gemini returned non-object JSON: {type(payload).__name__}")
    except Exception as e:
        logger.warning("Gemini extraction failed (%s) — using keyword fallback.", e)
        return _extract_keyword_fallback(user_text)

    # Keep only fields defined in the dataclass; __post_init__ normalises the rest.
    known = {f.name for f in fields(MatchPreferences)}
    clean = {k: v for k, v in payload.items() if k in known}
    # Convert JSON lists to tuples (dataclass default is tuple)
    for list_field in ("cities", "must_near", "nice_to_have"):
        if list_field in clean and isinstance(clean[list_field], list):
            clean[list_field] = tuple(clean[list_field])
    try:
        return MatchPreferences(**clean)
    except TypeError as e:
        logger.warning("MatchPreferences(**clean) failed (%s) — using keyword fallback.", e)
        return _extract_keyword_fallback(user_text)


# ---------------------------------------------------------------- keyword fallback


# en-dash and euro sign are intentional in this user-input regex.
_RE_BUDGET = re.compile(
    r"(?:(\d{2,4})\s*[-–a]\s*(\d{2,4})\s*(k|k€|mil)|(\d{2,4})\s*(k|k€|mil))",  # noqa: RUF001
    re.IGNORECASE,
)
_RE_BEDROOMS = re.compile(r"(\d+)\s*(?:dormitorio|habitaci|hab\b)", re.IGNORECASE)
_RE_HIJOS = re.compile(r"(\d+)\s*(?:hijo|ni[ñn]o|peque)", re.IGNORECASE)
_RE_SUNNY = re.compile(r"\b(?:sol|soleado|c[áa]lido|caluros)", re.IGNORECASE)
_RE_CLEAN_AIR = re.compile(r"\b(?:aire\s+limpio|sin\s+contamina|contaminaci|aire\s+puro)", re.IGNORECASE)
_RE_COAST = re.compile(r"\b(?:costa|mar|playa)\b", re.IGNORECASE)
_RE_INLAND = re.compile(r"\b(?:montaña|interior|rural|pueblo)\b", re.IGNORECASE)
_RE_WARM = re.compile(r"\b(?:cálido|calor|sur)\b", re.IGNORECASE)


def _known_cities() -> list[str]:
    """Pull distinct cities from Promocion. Cached per-process is fine; the
    catalogue barely moves. Avoid circular import by late binding."""
    from .models import Promocion

    try:
        return [c.lower() for c in Promocion.objects.values_list("ciudad", flat=True).distinct() if c]
    except Exception:
        return []


def _extract_keyword_fallback(user_text: str) -> MatchPreferences:
    text = user_text or ""
    text_lower = text.lower()

    budget_min = 0
    budget_max = 0
    m = _RE_BUDGET.search(text)
    if m:
        if m.group(1) and m.group(2):
            budget_min = int(m.group(1)) * 1000
            budget_max = int(m.group(2)) * 1000
        elif m.group(4):
            budget_max = int(m.group(4)) * 1000

    bedrooms_min = 0
    bm = _RE_BEDROOMS.search(text)
    if bm:
        bedrooms_min = int(bm.group(1))
    else:
        hm = _RE_HIJOS.search(text)
        if hm:
            bedrooms_min = int(hm.group(1)) + 1  # asume dormitorio principal

    cities: list[str] = []
    for city in _known_cities():
        if city and city in text_lower:
            cities.append(city)

    must_near: list[str] = []
    if re.search(r"colegio|escuela|guarder", text_lower):
        must_near.append("EDUCACION")
    if re.search(r"supermercado|mercado|compra", text_lower):
        must_near.append("COMPRAS")
    if re.search(r"metro|bus|tren|transporte", text_lower):
        must_near.append("TRANSPORTE")
    if re.search(r"hospital|cl[íi]nica|farmac", text_lower):
        must_near.append("SALUD")
    if re.search(r"parque|verde|jard[íi]n", text_lower):
        must_near.append("VERDES")

    climate = "any"
    if _RE_COAST.search(text):
        climate = "coastal"
    elif _RE_INLAND.search(text):
        climate = "cold"
    elif _RE_WARM.search(text):
        climate = "warm"

    return MatchPreferences(
        budget_eur_min=budget_min,
        budget_eur_max=budget_max,
        bedrooms_min=bedrooms_min,
        cities=tuple(cities),
        must_near=tuple(must_near),
        nice_to_have=(),
        climate_preference=climate,
        prefers_sunny=bool(_RE_SUNNY.search(text)),
        prefers_clean_air=bool(_RE_CLEAN_AIR.search(text)),
        destination_city="",
        summary=text.strip()[:200],
    )


# ---------------------------------------------------------------- ranking

# Weights MUST sum to 1.0 when all preferences are active. When a preference
# is inactive, its weight is redistributed to the pois axis — services are
# always relevant.
_W_POIS_BASE = 0.35
_W_SOLAR = 0.20
_W_CLIMATE = 0.20
_W_AIR = 0.15
_W_CITY = 0.10


@dataclass
class ScoredPromocion:
    promocion: Promocion
    score: float
    breakdown: dict[str, float | None] = field(default_factory=dict)
    highlights: list[str] = field(default_factory=list)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _axis_pois(
    promocion: Promocion,
    must_near: tuple[str, ...],
    nice_to_have: tuple[str, ...],
) -> tuple[float, dict[str, float | None]]:
    """Score 0..1 por cercanía a POIs. Devuelve también el breakdown por categoría."""
    from .services import nearest_by_category

    bk: dict[str, float | None] = {}
    if not promocion.location:
        return 0.0, bk

    nearest = {n["categoria"]: n for n in nearest_by_category(promocion)}

    def _score_one(cat: str) -> float:
        n = nearest.get(cat)
        if not n:
            return 0.0
        d = n.get("dist_m")
        if d is None:
            return 0.0
        bk[f"{cat.lower()}_m"] = int(d)
        # 1.0 si ≤ 600 m, 0.0 si ≥ 1500 m, lineal en medio
        return _clamp(1.0 - (d - 600) / 900.0)

    if must_near:
        must_scores = [_score_one(c) for c in must_near]
        must_total = sum(must_scores) / len(must_scores)
    else:
        must_total = 0.5  # neutral si no se especificó

    if nice_to_have:
        nice_scores = [_score_one(c) for c in nice_to_have]
        nice_total = sum(nice_scores) / len(nice_scores)
    else:
        nice_total = 0.0

    # must_near pesa 0.75, nice_to_have 0.25 dentro del eje POIs
    total = must_total * 0.75 + nice_total * 0.25 if nice_to_have else must_total
    return _clamp(total), bk


def _axis_solar(promocion: Promocion) -> tuple[float, float | None]:
    """Score por potencial solar. kWh/kWp·año 900 → 0.0, 1700 → 1.0."""
    solar = getattr(promocion, "solar", None)
    if not solar or solar.kwh_kwp_year is None:
        return 0.5, None
    kwh = float(solar.kwh_kwp_year)
    return _clamp((kwh - 900.0) / 800.0), kwh


# Bandas (°C) por preferencia climática. Interior del rango → 1.0, bordes decaen.
_CLIMATE_BANDS: dict[str, tuple[float, float]] = {
    "coastal": (13.0, 18.0),
    "mild": (12.0, 18.0),
    "warm": (16.0, 22.0),
    "cold": (8.0, 14.0),
}


def _axis_climate(promocion: Promocion, climate_preference: str) -> tuple[float, float | None]:
    clima = getattr(promocion, "clima", None)
    if not clima or not clima.temp_mean:
        return 0.5, None
    vals = [v for v in clima.temp_mean if v is not None]
    if not vals:
        return 0.5, None
    annual = sum(vals) / len(vals)
    if climate_preference == "any":
        return 0.5, round(annual, 1)
    band = _CLIMATE_BANDS.get(climate_preference)
    if not band:
        return 0.5, round(annual, 1)
    lo, hi = band
    if lo <= annual <= hi:
        s = 1.0
    else:
        # Fuera de banda: decae 1 punto por cada 1 °C hasta 5 °C → 0
        dist = min(abs(annual - lo), abs(annual - hi))
        s = _clamp(1.0 - dist / 5.0)
    return s, round(annual, 1)


def _axis_air(promocion: Promocion) -> tuple[float, dict[str, float | None]]:
    """Score por calidad del aire usando la estación OpenAQ más cercana."""
    from .models import AirQualityStation

    bk: dict[str, float | None] = {"pm25_latest": None, "aq_distance_m": None}
    if not promocion.location:
        return 0.5, bk
    nearest = (
        AirQualityStation.objects.annotate(d=Distance("location", promocion.location))
        .order_by("d")
        .first()
    )
    if not nearest:
        return 0.5, bk
    bk["aq_distance_m"] = int(nearest.d.m)
    if nearest.pm25 is None:
        return 0.5, bk
    pm25 = float(nearest.pm25)
    bk["pm25_latest"] = round(pm25, 1)
    # WHO 2021 24h: ≤12 → 1.0, ≤35 → 0.7, ≤55 → 0.3, >55 → 0
    if pm25 <= 12:
        return 1.0, bk
    if pm25 <= 35:
        return 0.7, bk
    if pm25 <= 55:
        return 0.3, bk
    return 0.0, bk


def _axis_city(promocion: Promocion, cities: tuple[str, ...]) -> float:
    if not cities:
        return 0.5
    return 1.0 if promocion.ciudad.lower() in cities else 0.0


def _build_highlights(
    prefs: MatchPreferences,
    breakdown: dict[str, float | None],
) -> list[str]:
    """Compact strings for the UI card. Keep each under ~30 chars."""
    out: list[str] = []
    for cat in prefs.must_near:
        key = f"{cat.lower()}_m"
        d = breakdown.get(key)
        if d is not None:
            label = str(POI.Categoria(cat).label)
            out.append(f"{label} a {int(d)} m")
    kwh = breakdown.get("kwh_kwp_year")
    if kwh is not None and prefs.prefers_sunny:
        out.append(f"{int(kwh)} kWh/kWp·año")
    t = breakdown.get("temp_mean_year")
    if t is not None and prefs.climate_preference != "any":
        out.append(f"Tª media {t} °C")
    pm = breakdown.get("pm25_latest")
    if pm is not None and prefs.prefers_clean_air:
        out.append(f"PM2.5 {pm} µg/m³")
    return out


def rank_promociones(prefs: MatchPreferences, limit: int = 3) -> list[ScoredPromocion]:
    """Deterministic ranker. No LLM, no network. Returns top-N by score desc."""
    qs = Promocion.objects.filter(
        location__isnull=False,
        estado__in=[Promocion.Estado.EN_VENTA, Promocion.Estado.PROXIMA],
    ).select_related("solar", "clima")
    if prefs.cities:
        qs = qs.filter(ciudad__iregex=r"(?i)(" + "|".join(re.escape(c) for c in prefs.cities) + ")")

    # Weight redistribution: inactive axes send their weight to the POIs axis.
    w_pois = _W_POIS_BASE
    w_solar = _W_SOLAR if prefs.prefers_sunny else 0.0
    w_climate = _W_CLIMATE if prefs.climate_preference != "any" else 0.0
    w_air = _W_AIR if prefs.prefers_clean_air else 0.0
    w_city = _W_CITY if prefs.cities else 0.0
    redistributed = (_W_SOLAR - w_solar) + (_W_CLIMATE - w_climate) + (_W_AIR - w_air) + (_W_CITY - w_city)
    w_pois += redistributed

    scored: list[ScoredPromocion] = []
    for p in qs:
        s_pois, bk_pois = _axis_pois(p, prefs.must_near, prefs.nice_to_have)
        s_solar, kwh = _axis_solar(p)
        s_climate, temp_annual = _axis_climate(p, prefs.climate_preference)
        s_air, bk_air = _axis_air(p)
        s_city = _axis_city(p, prefs.cities)

        total = (
            s_pois * w_pois
            + s_solar * w_solar
            + s_climate * w_climate
            + s_air * w_air
            + s_city * w_city
        )

        breakdown: dict[str, float | None] = {}
        breakdown.update(bk_pois)
        breakdown["kwh_kwp_year"] = kwh
        breakdown["temp_mean_year"] = temp_annual
        breakdown.update(bk_air)
        breakdown["city_match"] = s_city

        scored.append(
            ScoredPromocion(
                promocion=p,
                score=round(total, 4),
                breakdown=breakdown,
                highlights=_build_highlights(prefs, breakdown),
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]


# ---------------------------------------------------------------- explanation


_EXPLANATION_PROMPT = """Eres un redactor comercial inmobiliario. Escribe UN SOLO PÁRRAFO
(2 a 3 frases, máximo 350 caracteres) en español explicando por qué esta promoción
encaja con las preferencias del usuario. Usa SOLO los datos de más abajo. NO cites
precios, rentabilidades ni cifras que no estén en los datos. NO uses listas,
viñetas ni encabezados. Devuelve exclusivamente el párrafo.

Preferencias del usuario (resumen): {summary}

Promoción: {nombre} ({ciudad})
Datos: {breakdown}

Párrafo:"""


def generate_explanation(
    prefs: MatchPreferences,
    scored: ScoredPromocion,
    timeout_s: float = 3.0,
) -> str | None:
    """Returns a short paragraph, or None on any failure/timeout."""
    # Keep only the breakdown entries that are populated — the LLM should see
    # exactly what we can defend.
    bk = {k: v for k, v in scored.breakdown.items() if v is not None}
    prompt = _EXPLANATION_PROMPT.format(
        summary=prefs.summary or "(sin resumen)",
        nombre=scored.promocion.nombre,
        ciudad=scored.promocion.ciudad,
        breakdown=json.dumps(bk, ensure_ascii=False),
    )

    def _call() -> str:
        return _call_gemini_json(prompt, max_output_tokens=200)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call)
            text = future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        logger.warning("Gemini explanation timed out for %s", scored.promocion.slug)
        return None
    except Exception as e:
        logger.warning("Gemini explanation failed for %s: %s", scored.promocion.slug, e)
        return None
    cleaned = _strip_code_fence(text).strip()
    return cleaned or None


@dataclass
class ScoredPromocionWithExplanation:
    scored: ScoredPromocion
    explanation: str | None


@dataclass
class MatchResult:
    preferences: MatchPreferences
    results: list[ScoredPromocionWithExplanation]
    degraded: bool  # True si fallback keyword se usó o alguna explicación falló


def match(user_text: str, limit: int = 3, explanation_timeout_s: float = 3.0) -> MatchResult:
    """End-to-end orchestrator: extract → rank → parallel explain."""
    degraded_flag = False

    # Phase 1 — extract. We detect degraded-mode by checking whether Gemini was
    # tried and failed; here we just note if `summary` is empty but the input
    # had content (strong hint the LLM path didn't produce anything useful).
    prefs = extract_preferences(user_text)
    if user_text.strip() and not prefs.summary:
        degraded_flag = True

    # Phase 2 — rank.
    scored = rank_promociones(prefs, limit=limit)

    # Phase 3 — explain in parallel.
    def _one(s: ScoredPromocion) -> ScoredPromocionWithExplanation:
        exp = generate_explanation(prefs, s, timeout_s=explanation_timeout_s)
        return ScoredPromocionWithExplanation(scored=s, explanation=exp)

    results_with_exp: list[ScoredPromocionWithExplanation] = []
    if scored:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(scored), 3)) as ex:
            results_with_exp = list(ex.map(_one, scored))
    if any(r.explanation is None for r in results_with_exp):
        degraded_flag = True

    return MatchResult(preferences=prefs, results=results_with_exp, degraded=degraded_flag)
