"""Coste energético ponderado por canal de carga (home / work / public).

Reemplaza la decisión binaria `night_charging` (que aplicaba P3 o blended
al 100 % del kWh anual) por una mezcla realista de cuatro canales. El
delta económico entre "100 % casa valle" y "100 % pública DC" puede
exceder los 10.000 € a 10 años, así que medir el mix es la palanca de
exactitud más importante del TCO eléctrico.

Canales:
- home: PVPC (valle si night_charging, blended si no)
- work: 0 €/kWh por defecto (oficina / parque tecnológico)
- public_ac: 0,42 €/kWh (IBIL / Iberdrola públicos)
- public_dc: 0,55 €/kWh (DC rápida ≥50 kW)

Los porcentajes se validan y normalizan a 100 % en la entrada. Si suman
99 o 101 por redondeo del slider, se reparte el residuo en `home` (que
es el canal por defecto cuando la suma queda corta).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from apps.mubil.data import pvpc_ingest
from apps.mubil.data.price_defaults import (
    DEFAULT_PUBLIC_AC_EUR_KWH,
    DEFAULT_PUBLIC_DC_EUR_KWH,
    DEFAULT_WORK_EUR_KWH,
)

Profile = Literal["particular", "autonomo", "empresa"]


# --------------------------------------------------------------- presets

# (home, work, public_ac, public_dc) — siempre suman 100.
PRESETS = {
    "particular": {
        "home_always": (100, 0, 0, 0),
        "home_work": (60, 35, 3, 2),
        "mixed": (50, 0, 35, 15),
        "public_only": (0, 0, 60, 40),
    },
    "autonomo": {
        "office_always": (0, 100, 0, 0),
        "office_public": (0, 70, 20, 10),
        "fleet_mixed": (30, 40, 20, 10),
    },
    "empresa": {
        "office_always": (0, 100, 0, 0),
        "office_public": (0, 70, 20, 10),
        "fleet_mixed": (30, 40, 20, 10),
    },
}


# --------------------------------------------------------------- model


@dataclass(frozen=True)
class ChargingMix:
    """Distribución (%) de la energía anual por canal. Suma 100."""

    home_pct: int
    work_pct: int
    public_ac_pct: int
    public_dc_pct: int

    def __post_init__(self):
        total = self.home_pct + self.work_pct + self.public_ac_pct + self.public_dc_pct
        if not (98 <= total <= 102):
            raise ValueError(f"ChargingMix debe sumar ~100, suma {total}")

    @classmethod
    def from_preset(cls, profile: Profile, preset_key: str) -> ChargingMix:
        try:
            home, work, ac, dc = PRESETS[profile][preset_key]
        except KeyError as exc:
            raise ValueError(f"Preset desconocido: {profile}/{preset_key}") from exc
        return cls(home, work, ac, dc)

    @classmethod
    def normalized(cls, home: int, work: int, ac: int, dc: int) -> ChargingMix:
        """Construye y corrige el redondeo del slider (residuo va a home)."""
        total = home + work + ac + dc
        if total != 100:
            home = max(0, home + (100 - total))
        return cls(home, work, ac, dc)

    def weighted_price_eur_kwh(self, *, night_charging: bool) -> Decimal:
        """Precio medio ponderado €/kWh para el mix actual."""
        home_price = pvpc_ingest.current_price_eur_kwh(night_charging=night_charging)
        return (
            (Decimal(self.home_pct) * home_price)
            + (Decimal(self.work_pct) * DEFAULT_WORK_EUR_KWH)
            + (Decimal(self.public_ac_pct) * DEFAULT_PUBLIC_AC_EUR_KWH)
            + (Decimal(self.public_dc_pct) * DEFAULT_PUBLIC_DC_EUR_KWH)
        ) / Decimal("100")

    def to_out(self) -> dict:
        return {
            "home_pct": self.home_pct,
            "work_pct": self.work_pct,
            "public_ac_pct": self.public_ac_pct,
            "public_dc_pct": self.public_dc_pct,
        }
