"""Default price constants used while ESIOS/MINCOTUR tokens arrive.

Sustituir por queries reales a `EnergyPricePVPC` y `FuelStation` cuando F0
desbloquee las ingestas (ver PROPUESTA.md §14 — token ESIOS 5-10d lag).

Valores tomados a fecha 2026-05-26, fuentes:
- PVPC: ESIOS indicator 1001 (media móvil 30d, todas tarifas)
- Gasolina/Diésel: media nacional MINCOTUR (informativa)
"""

from decimal import Decimal


# Electricidad — €/kWh (incluye impuestos y peajes, tarifa 2.0TD)
DEFAULT_PVPC_EUR_KWH = Decimal("0.165")
DEFAULT_PVPC_VALLE_EUR_KWH = Decimal("0.085")  # tramo P3 nocturno

# Combustibles — €/litro
DEFAULT_GASOLINA_95_EUR_L = Decimal("1.585")
DEFAULT_GASOLEO_A_EUR_L = Decimal("1.495")

# Factor de emisiones — kg CO₂e / unidad
CO2_KG_PER_KWH_MIX_ES = Decimal("0.190")   # mix eléctrico España, REE 2025
CO2_KG_PER_LITRE_GASOLINA = Decimal("2.31")
CO2_KG_PER_LITRE_DIESEL = Decimal("2.68")

# Asunciones operativas constantes
DEFAULT_INSURANCE_EUR_YEAR_ICE = Decimal("450")
DEFAULT_INSURANCE_EUR_YEAR_EV = Decimal("500")    # ligeramente más alta
DEFAULT_MAINTENANCE_EUR_YEAR_ICE = Decimal("400")
DEFAULT_MAINTENANCE_EUR_YEAR_EV = Decimal("180")  # ~55% menos
DEFAULT_TAX_EUR_YEAR_ICE = Decimal("90")
DEFAULT_TAX_EUR_YEAR_EV = Decimal("30")
