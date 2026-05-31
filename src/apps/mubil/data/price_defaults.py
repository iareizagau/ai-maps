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


# ============================================================ Charging mix
# Tarifas medias para los cuatro canales de carga BEV. Home night/day vienen
# de PVPC live (pvpc_ingest.current_price_eur_kwh); aquí solo viven los
# canales que no tienen ingesta propia.
#
# Fuentes (2026-05): operadores públicos en España publican PPV (precio por
# venta). IBIL ~0,40 €/kWh AC, Iberdrola Plenitude ~0,45 €/kWh AC, Repsol
# ~0,42 €/kWh AC. DC rápida promedio 0,55-0,65 €/kWh (Ionity, Tesla SUC
# abierto, Iberdrola DC). Trabajo se asume gratis (típico parque tecnológico
# / oficina con wallbox empresarial). El override por operador llegará cuando
# `ChargingStation` tenga `price_eur_kwh`.
DEFAULT_PUBLIC_AC_EUR_KWH = Decimal("0.42")
DEFAULT_PUBLIC_DC_EUR_KWH = Decimal("0.55")
DEFAULT_WORK_EUR_KWH = Decimal("0.00")


# ============================================================ Wallbox CAPEX
# Coste medio instalación wallbox 7,4 kW monofásico en garaje particular
# (cable + protecciones + mano de obra, sin la wallbox premium). Trifásico
# 11 kW sube a ~2.000 €. Para v1 usamos importe fijo; el desglose se
# refina cuando metamos preguntas eléctricas (potencia contratada, tirada).
WALLBOX_CAPEX_EUR = Decimal("1500")


# ============================================================ Incentivos
# Importes Moves III (Real Decreto 821/2024 prorrogado, vigente 2026).
# Particulares y autónomos/empresas tienen escalas distintas.
MOVES3_BEV_PARTICULAR_EUR = Decimal("4500")
MOVES3_BEV_PARTICULAR_SCRAP_EUR = Decimal("7000")
MOVES3_BEV_EMPRESA_EUR = Decimal("2900")
MOVES3_BEV_EMPRESA_SCRAP_EUR = Decimal("4000")

# Moves III infraestructura de recarga (capítulo II).
# Particular: 70% sobre coste, tope 600 €. Empresa/autónomo: 35-50%, topes
# mayores. Aproximamos al tope para una wallbox de 1.500 €.
MOVES3_WALLBOX_PARTICULAR_EUR = Decimal("600")
MOVES3_WALLBOX_EMPRESA_EUR = Decimal("800")

# Deducción IRPF Real Decreto-ley 5/2023: 15% sobre base máxima 20.000 €
# en compra de BEV nuevo. Solo personas físicas.
IRPF_BEV_DEDUCCION_PCT = Decimal("0.15")
IRPF_BEV_BASE_MAX_EUR = Decimal("20000")

# IVA deducible — autónomos 50% por defecto (Art. 95 LIVA, presunción uso
# mixto), empresas 100% si se justifica afectación. Tipo aplicado 21%.
IVA_RATE = Decimal("0.21")
IVA_DEDUCIBLE_AUTONOMO_PCT = Decimal("0.50")
IVA_DEDUCIBLE_EMPRESA_PCT = Decimal("1.00")

# Bonificación IVTM media por provincia para BEV. Cada ayuntamiento la fija
# independientemente; tomamos un promedio ponderado por población de los
# municipios con ordenanza vigente.
# - Gipuzkoa: Donostia 75% + Errenteria 50% + Irun 75% + Hondarribia 75% → ~75%
# - Bizkaia: Bilbao 95% + Getxo 75% + Barakaldo 100% + Portugalete 50% → ~90%
# - Araba: Vitoria 50% + resto sin bonif. específica → ~50%
IVTM_BONIF_PCT_BY_PROVINCE = {
    "GI": Decimal("0.75"),
    "BI": Decimal("0.90"),
    "VI": Decimal("0.50"),
    "OTROS": Decimal("0.00"),
}

# Cuota IVTM base para turismo BEV (12-15 CV fiscales típico) — usado para
# calcular el flujo anual ahorrado por la exención.
IVTM_BEV_BASE_EUR_YEAR = Decimal("90")


# ============================================================ Provincia desde CP
# Mapeo CP (2 primeros dígitos) → código provincia. Sólo Euskadi necesita
# granularidad para IVTM; el resto cae en "OTROS".
CP_TO_PROVINCE = {
    "01": "VI",   # Araba
    "20": "GI",   # Gipuzkoa
    "48": "BI",   # Bizkaia
}


def cp_to_province(cp: str) -> str:
    """Devuelve código provincia ('GI'/'BI'/'VI'/'OTROS') desde CP."""
    if not cp or len(cp) < 2:
        return "OTROS"
    return CP_TO_PROVINCE.get(cp[:2], "OTROS")
