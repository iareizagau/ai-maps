"""Estimador heurístico de PVP por specs IDAE — Capa 2 de la pipeline.

Con sólo ~33 anclas manuales no es posible una regresión multifeature
estable, así que usamos un modelo más simple y robusto: **mediana del
precio por cluster (propulsion × tier_marca)** + ajuste marginal por
capacidad de batería para BEV/PHEV.

Ventajas vs regresión:
- Cero dependencias externas (scikit-learn fuera).
- Tolerante a celdas con 1 muestra (fallback al promedio del tier).
- Inspeccionable: el comando puede imprimir la tabla calibrada.
- Falla "suave": si una celda está vacía, retrocede a otra tier/propulsion.

Precisión esperada vs anclas: error medio absoluto 15-25 %. Suficiente
para que el `advisor` calcule un payback orientativo en vehículos no
verificados. Los flags `price_source='heuristic'` permiten que la UI
etiquete la confianza ("Estimado ±20 %") y que Capa 3 (Gemini) los
sobrescriba selectivamente.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from apps.mubil.models import Vehicle


# ───────────────────── Tier por marca (hardcoded) ─────────────────────
# Clasificación pragmática para el mercado español 2026. La marca canónica
# es la PRIMERA palabra del campo `make` (algunos vienen como "Volkswagen
# Canarias" o "BMW Group"), por eso el lookup se hace sobre `make.split()[0]`.

TIER_BY_MAKE = {
    # Budget
    "Dacia":   "budget",
    "Lada":    "budget",
    "MG":      "budget",
    "SsangYong": "budget",
    "Suzuki":  "budget",
    # Mid mass-market
    "Citroën":   "mid",
    "Citroen":   "mid",
    "Cupra":     "mid",
    "Fiat":      "mid",
    "Ford":      "mid",
    "Honda":     "mid",
    "Hyundai":   "mid",
    "Jeep":      "mid",
    "Kia":       "mid",
    "Mazda":     "mid",
    "Mitsubishi":"mid",
    "Nissan":    "mid",
    "Opel":      "mid",
    "Peugeot":   "mid",
    "Renault":   "mid",
    "SEAT":      "mid",
    "Seat":      "mid",
    "Skoda":     "mid",
    "Subaru":    "mid",
    "Toyota":    "mid",
    "Volkswagen":"mid",
    # Premium / luxury
    "Alfa":       "premium",
    "Audi":       "premium",
    "BMW":        "premium",
    "DS":         "premium",
    "Genesis":    "premium",
    "Jaguar":     "premium",
    "Land":       "premium",  # Land Rover
    "Lexus":      "premium",
    "Maserati":   "premium",
    "Mercedes-Benz": "premium",
    "Mercedes":   "premium",
    "Mini":       "premium",
    "Polestar":   "premium",
    "Porsche":    "premium",
    "Tesla":      "premium",
    "Volvo":      "premium",
}
DEFAULT_TIER = "mid"
VALID_PROPULSIONS = ("BEV", "PHEV", "HEV", "ICE", "DIESEL", "CNG", "LPG")
BATTERY_MARGINAL_EUR_PER_KWH = Decimal("250")  # marginal €/kWh sobre la mediana


@dataclass
class CalibrationTable:
    """Resultado de calibrar la heurística sobre los anchors manuales."""

    cluster_median_price: dict[tuple[str, str], int]   # (propulsion, tier) → mediana
    cluster_median_battery: dict[tuple[str, str], Decimal]  # idem para battery_kwh
    propulsion_fallback_price: dict[str, int]          # propulsion → mediana global
    n_anchors: int

    def estimate(self, *, propulsion: str, make: str, battery_kwh: Optional[Decimal]) -> int:
        """Predice PVP para una fila concreta."""
        tier = tier_for_make(make)
        base = self.cluster_median_price.get((propulsion, tier))
        if base is None:
            base = self.propulsion_fallback_price.get(propulsion)
        if base is None:
            return 25_000  # último recurso: precio típico de un coche español
        price = Decimal(base)

        # Ajuste marginal por capacidad batería (sólo BEV/PHEV)
        if propulsion in ("BEV", "PHEV") and battery_kwh:
            median_bat = self.cluster_median_battery.get((propulsion, tier))
            if median_bat is not None:
                delta_kwh = Decimal(battery_kwh) - median_bat
                price += delta_kwh * BATTERY_MARGINAL_EUR_PER_KWH

        # Floor / cap defensivos
        return max(8_000, min(180_000, int(price.quantize(Decimal("1")))))


# ───────────────────── helpers ─────────────────────


def tier_for_make(make: str) -> str:
    if not make:
        return DEFAULT_TIER
    head = make.split()[0]
    return TIER_BY_MAKE.get(head, DEFAULT_TIER)


def _median_int(values: list[int]) -> Optional[int]:
    return int(statistics.median(values)) if values else None


def _median_decimal(values: list[Decimal]) -> Optional[Decimal]:
    if not values:
        return None
    # statistics.median funciona con Decimal
    return statistics.median(values)


def calibrate(anchors: Optional[list[Vehicle]] = None) -> CalibrationTable:
    """Lee anclas `price_source='manual'` y construye la tabla de predicción.

    Pasar `anchors` explícitamente solo para tests; en producción se
    recalcula desde BD en cada `seed_vehicle_prices_heuristic`.
    """
    if anchors is None:
        anchors = list(
            Vehicle.objects
            .filter(price_source=Vehicle.PriceSource.MANUAL, price_eur__isnull=False)
        )

    price_buckets: dict[tuple[str, str], list[int]] = {}
    bat_buckets: dict[tuple[str, str], list[Decimal]] = {}
    by_propulsion: dict[str, list[int]] = {}

    for v in anchors:
        if v.propulsion not in VALID_PROPULSIONS or not v.price_eur:
            continue
        tier = tier_for_make(v.make)
        key = (v.propulsion, tier)
        price_buckets.setdefault(key, []).append(v.price_eur)
        by_propulsion.setdefault(v.propulsion, []).append(v.price_eur)
        if v.battery_kwh:
            bat_buckets.setdefault(key, []).append(v.battery_kwh)

    return CalibrationTable(
        cluster_median_price={k: _median_int(v) for k, v in price_buckets.items()},
        cluster_median_battery={k: _median_decimal(v) for k, v in bat_buckets.items() if v},
        propulsion_fallback_price={k: _median_int(v) for k, v in by_propulsion.items()},
        n_anchors=len(anchors),
    )


def mean_abs_error(table: CalibrationTable, anchors: list[Vehicle]) -> float:
    """Error medio absoluto de la tabla evaluada sobre los anchors (in-sample).

    No es validación cruzada — sirve para sanity check rápido. Si MAE in-
    sample ya supera el 20 % del precio medio, la heurística no es útil y
    conviene revisar TIER_BY_MAKE o añadir features.
    """
    errs: list[float] = []
    for v in anchors:
        if not v.price_eur:
            continue
        pred = table.estimate(
            propulsion=v.propulsion, make=v.make, battery_kwh=v.battery_kwh,
        )
        errs.append(abs(pred - v.price_eur))
    return sum(errs) / len(errs) if errs else 0.0
