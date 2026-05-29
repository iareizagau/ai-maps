"""Curated URL list for the `ask` corpus normativa expansion.

Why this exists: the CKAN-only MVP corpus indexed dataset *metadata*, not
regulatory content — the 2026-05-29 RAG benchmark on 5 gold prompts showed
MOVES III + BizkaiBus declined because no source ever discussed them.

Selection criteria:
- **URLs verified live (2026-05-29).** Every entry returned HTTP 200 and
  yielded ≥ ``MIN_BODY_CHARS`` text from trafilatura/pypdf when checked.
- **Official sites first** (IDAE, EVE, gov.es) — Wikipedia is fallback.
- **Public, no JS render needed** — trafilatura's main-content path works.

Add new entries here, run ``manage.py ingest_normativa_corpus``
(idempotent via content_hash), then ``embed_ask_corpus`` for new chunks.
URLs that 404 now have NOT been silently kept — they would inflate the
"errors" counter and slow the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class NormativaSource:
    url: str
    title_override: str = ""        # if set, overrides the page's <title>.
    region_naia: str = ""           # NAIA code for "filter by my municipality".
    note: str = ""                  # human-readable tag, e.g. "MOVES III RD".


# ────────────────────────── MOVES III + ayudas vehículos eléctricos
# `ayudasenergiaidae.es` is the IDAE-managed portal with the most concrete
# per-programme content (presupuesto, cuantías, beneficiarios). Better than
# Wikipedia, which has no MOVES III article.

MOVES_III: List[NormativaSource] = [
    NormativaSource(
        url="https://ayudasenergiaidae.es/moves-iii/",
        title_override="MOVES III — IDAE oficial",
        note="MOVES III — programa, cuantías, beneficiarios",
    ),
    NormativaSource(
        url="https://ayudasenergiaidae.es/moves-singulares-ii/",
        title_override="MOVES Singulares II — IDAE",
        note="MOVES Singulares II — puntos de recarga rápida",
    ),
    NormativaSource(
        url="https://ayudasenergiaidae.es/",
        title_override="Ayudas IDAE — catálogo de programas energéticos",
        note="Portal IDAE — listado completo de ayudas activas",
    ),
]


# ────────────────────────── PVPC / mercado eléctrico

PVPC: List[NormativaSource] = [
    NormativaSource(
        url="https://es.wikipedia.org/wiki/PVPC",
        note="PVPC — Precio Voluntario para el Pequeño Consumidor",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Mercado_el%C3%A9ctrico_de_Espa%C3%B1a",
        note="Mercado eléctrico de España — operación, tarifas",
    ),
]


# ────────────────────────── transporte público EH

TRANSPORTE_EH: List[NormativaSource] = [
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Bizkaibus",
        region_naia="48",
        note="BizkaiBus — bus interurbano Bizkaia",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Euskotren",
        note="Euskotren — operador ferroviario CAV",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Metro_de_Bilbao",
        region_naia="48",
        note="Metro Bilbao",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Lurraldebus",
        region_naia="20",
        note="Lurraldebus — bus interurbano Gipuzkoa",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Bilbao",
        region_naia="48",
        note="Tranvía de Bilbao",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Tranv%C3%ADa_de_Vitoria",
        region_naia="01",
        note="Tranvía de Vitoria-Gasteiz",
    ),
]


# ────────────────────────── ZBE (Zonas de Bajas Emisiones)

ZBE: List[NormativaSource] = [
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Zona_de_bajas_emisiones",
        note="ZBE — Zona de Bajas Emisiones (Ley 7/2021)",
    ),
]


# ────────────────────────── vehículo eléctrico / mercado

VEHICULO_ELECTRICO: List[NormativaSource] = [
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Veh%C3%ADculo_el%C3%A9ctrico",
        note="Vehículo eléctrico — general",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Coche_el%C3%A9ctrico",
        note="Coche eléctrico",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Veh%C3%ADculo_h%C3%ADbrido_enchufable",
        note="Vehículo híbrido enchufable (PHEV)",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Estaci%C3%B3n_de_carga",
        note="Estación de carga — infraestructura",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Worldwide_Harmonised_Light_Vehicles_Test_Procedure",
        note="WLTP — homologación consumo / CO₂",
    ),
]


# ────────────────────────── movilidad sostenible / red ciclista

MOVILIDAD: List[NormativaSource] = [
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Movilidad_sostenible",
        note="Movilidad sostenible — concepto + políticas",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Bidegorri",
        note="Bidegorri — red ciclista País Vasco",
    ),
    NormativaSource(
        url="https://es.wikipedia.org/wiki/Carril_bici",
        note="Carril bici — definición y normativa",
    ),
]


# ────────────────────────── full registry

ALL_SOURCES: List[NormativaSource] = (
    MOVES_III
    + PVPC
    + TRANSPORTE_EH
    + ZBE
    + VEHICULO_ELECTRICO
    + MOVILIDAD
)
