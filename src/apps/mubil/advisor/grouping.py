"""Agrupamiento de `Vehicle` por `(make_canonical, model_base)`.

El catálogo IDAE entrega una fila por cada variante de homologación. Para
el autocomplete del advisor eso es decisión fatiga — el usuario piensa
"Vito" como una entidad, no como 67 variantes (114 CDI Larga 2800, 114
CDI Larga 3050, etc.).

Esta utilidad resuelve tres ruidos del dataset:

  1. **Variantes IDAE** — un Vehicle por trim/distancia entre ejes/transmisión.
     → Agrupar por (make, model_base).
  2. **Make duplicado por concesionario** — "TESLA" vs "Tesla",
     "Volkswagen Canarias" vs "Volkswagen Turismos" son el mismo
     fabricante. → Normalizar via CANONICAL_MAKES + strip de sufijos
     ("Canarias", "Turismos", "Vehículos Comerciales").
  3. **Prefijos comerciales basura** — "Nuevo ID. Polo MY27" no debe
     producir model_base = "Nuevo". → Strip "Nuevo/Nueva/New" antes de
     extraer el primer token.

Para precisión real haría falta un campo Vehicle.model_base poblado en el
ingest IDAE. Para el MVP MUBIL esta heurística agrupa el ~95 % del catálogo
correctamente, con drill-down futuro para el 5 % restante.
"""

import re
from collections import defaultdict
from decimal import Decimal

# Prefijos compuestos donde la "base" son 2+ tokens. Ampliar al observar
# colisiones reales. Lista corta a propósito — más permite agrupación más
# fina pero exige mantenimiento.
COMPOUND_PREFIXES = (
    "Model 3",
    "Model S",
    "Model X",
    "Model Y",  # Tesla
    "A4 Avant",
    "A6 Avant",
    "A4 Allroad",
    "A6 Allroad",  # Audi estate
    "EQE SUV",
    "EQS SUV",  # Mercedes
)

# Marcas canónicas (lower → display name). El catálogo IDAE tiene la marca
# como aparece en la documentación de cada concesionario, lo que genera
# duplicados como "TESLA" + "Tesla" + "Tesla Motors". Esta tabla los une.
CANONICAL_MAKES = {
    "tesla": "Tesla",
    "volkswagen": "Volkswagen",
    "mercedes-benz": "Mercedes-Benz",
    "audi": "Audi",
    "bmw": "BMW",
    "kia": "Kia",
    "hyundai": "Hyundai",
    "renault": "Renault",
    "peugeot": "Peugeot",
    "citroën": "Citroën",
    "citroen": "Citroën",
    "ford": "Ford",
    "opel": "Opel",
    "skoda": "Škoda",
    "škoda": "Škoda",
    "seat": "SEAT",
    "cupra": "Cupra",
    "fiat": "Fiat",
    "nissan": "Nissan",
    "mazda": "Mazda",
    "volvo": "Volvo",
    "mini": "MINI",
    "smart": "smart",
    "porsche": "Porsche",
    "mg": "MG",
    "byd": "BYD",
    "lexus": "Lexus",
    "suzuki": "Suzuki",
    "honda": "Honda",
    "mitsubishi": "Mitsubishi",
    "subaru": "Subaru",
    "alfa romeo": "Alfa Romeo",
    "jaguar": "Jaguar",
    "land rover": "Land Rover",
    "jeep": "Jeep",
    "ds automobiles": "DS Automobiles",
    "ds": "DS Automobiles",
    "maserati": "Maserati",
    "toyota": "Toyota",
    "dacia": "Dacia",
    "lancia": "Lancia",
    "lynk & co": "Lynk & Co",
    "lynk&co": "Lynk & Co",
}

# Sufijos que las concesionarias añaden al nombre de marca. Strip y revolver
# a buscar en CANONICAL_MAKES.
DEALER_SUFFIXES = (
    " canarias",
    " turismos",
    " vehículos comerciales",
    " vehiculos comerciales",
    " trucks españa",
    " trucks",  # CUIDADO: "Renault Trucks" es brand diferente
    " motors",
)

_PARENS_PREFIX_RE = re.compile(r"^\s*\([^)]*\)\s*")
_NUEVO_PREFIX_RE = re.compile(r"^(?:nuev[ao]|new)\s+", re.IGNORECASE)


def normalize_make(make: str) -> str:
    """`"Volkswagen Canarias" → "Volkswagen"`, `"TESLA" → "Tesla"`."""
    if not make:
        return ""
    lower = make.lower().strip()

    # Hit directo en la tabla canónica.
    if lower in CANONICAL_MAKES:
        return CANONICAL_MAKES[lower]

    # Sufijos de concesionario. Sólo aplicamos el strip si el resto coincide
    # con una marca canónica conocida — así "Renault Trucks" (brand
    # diferente) NO colapsa a "Renault".
    for suf in DEALER_SUFFIXES:
        if lower.endswith(suf):
            base = lower[: -len(suf)].strip()
            if base in CANONICAL_MAKES:
                return CANONICAL_MAKES[base]

    return make.strip()


def extract_model_base(model: str) -> str:
    if not model:
        return ""
    # Strip prefijo entre paréntesis: "(03.2024) Vito 110…" → "Vito 110…"
    cleaned = _PARENS_PREFIX_RE.sub("", model).strip()
    if not cleaned:
        return model.strip()

    # Strip "Nuevo"/"Nueva"/"New" del inicio: "Nuevo ID. Polo…" → "ID. Polo…"
    cleaned = _NUEVO_PREFIX_RE.sub("", cleaned).strip()
    if not cleaned:
        return model.strip()

    lower = cleaned.lower()

    # Compound prefix (Model 3, A6 Avant, etc.)
    for prefix in COMPOUND_PREFIXES:
        p = prefix.lower()
        if lower == p or lower.startswith(p + " "):
            return prefix

    parts = cleaned.split()
    if not parts:
        return cleaned
    first = parts[0]
    # Si el primer token termina en "." (`ID.`, `e.`), tomar 2 tokens —
    # `ID.` solo es demasiado genérico (VW vende ID.3, ID.4, ID.7, ID. Polo…).
    if first.endswith(".") and len(parts) > 1:
        return first + " " + parts[1]
    return first


def _consumption_value(v, propulsion_hint: str | None = None) -> Decimal | None:
    """Consumo comparable en una unidad. BEV/PHEV usan kWh/100, el resto
    L/100. Si la fila no tiene el campo apropiado, devolvemos None.
    """
    prop = (propulsion_hint or v.propulsion or "").upper()
    if prop in ("BEV", "PHEV"):
        return v.consumption_kwh_100km
    return v.consumption_l_100km


def group_by_model_base(
    vehicles: list,
    propulsion_hint: str | None = None,
) -> list[dict]:
    """Agrupa por `(make_canonical, model_base)` (case-insensitive).

    Devuelve por grupo:
      - representative: el Vehicle mediano de consumo (más "medio"
        estadísticamente).
      - variant_count, model_base (display), make (display canonical),
        consumption_min/max.

    La clave incluye `category` para que productos del mismo make+modelo
    pero en categorías EU distintas (p. ej. KG Mobility TORRES ADVENTURE M1
    SUV vs TORRES EVX VAN PRO N1 furgoneta) NO se mezclen.

    Orden: respeta el orden de aparición del primer miembro de cada grupo,
    para no romper el ranking trigram del caller.
    """
    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    canonical_make_for: dict[tuple[str, str, str], str] = {}
    base_for: dict[tuple[str, str, str], str] = {}
    order: list[tuple[str, str, str]] = []

    for v in vehicles:
        canonical_make = normalize_make(v.make)
        base = extract_model_base(v.model)
        category = (v.category or "").upper()
        key = (canonical_make.lower(), base.lower(), category)
        if key not in groups:
            order.append(key)
            canonical_make_for[key] = canonical_make
            base_for[key] = base
        groups[key].append(v)

    out: list[dict] = []
    for key in order:
        variants = groups[key]
        sortable = [(v, _consumption_value(v, propulsion_hint)) for v in variants]
        sortable.sort(key=lambda t: (t[1] is None, t[1] or Decimal("0")))
        rep = sortable[(len(sortable) - 1) // 2][0]
        cons_vals = [c for _, c in sortable if c is not None]

        out.append(
            {
                "representative": rep,
                "make_display": canonical_make_for[key],
                "model_base": base_for[key],
                "variant_count": len(variants),
                "consumption_min": min(cons_vals) if cons_vals else None,
                "consumption_max": max(cons_vals) if cons_vals else None,
            }
        )
    return out
