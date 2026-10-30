"""PVGIS v5.3 (JRC/EU) photovoltaic potential — cached per Promocion.

Fixed-parameter call: south, 30°, 14% losses, crystSi, building-mounted.
Rationale: see docs/amenabar/PLAN.md section 1 and
openspec/changes/amenabar-pvgis-solar/design.md.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import requests

from .models import Promocion, SolarPotential
from .services import USER_AGENT

logger = logging.getLogger(__name__)

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
PVGIS_RATE_S = 1.0
PVGIS_VERSION = "v5_3"

PVGIS_DEFAULTS: dict[str, int | str] = {
    "peakpower": 1,
    "loss": 14,
    "angle": 30,
    "aspect": 0,
    "pvtechchoice": "crystSi",
    "mountingplace": "building",
    "outputformat": "json",
}


def fetch_pvgis(lat: float, lon: float) -> dict:
    """One shot against PVGIS. Raises on network / HTTP errors."""
    params = {**PVGIS_DEFAULTS, "lat": lat, "lon": lon}
    resp = requests.get(
        PVGIS_URL,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def store_solar(promocion: Promocion) -> SolarPotential | None:
    """Fetch PVGIS and persist the result. Returns None on any failure.

    Degrades silently: logs a warning and returns None so the public
    endpoint keeps working. Keeps `raw_json` for audit / re-parsing.
    """
    if not promocion.location:
        return None

    try:
        data = fetch_pvgis(promocion.location.y, promocion.location.x)
        totals = data["outputs"]["totals"]["fixed"]
        monthly_entries = data["outputs"]["monthly"]["fixed"]
        monthly = [round(float(m["E_m"]), 2) for m in monthly_entries]
        kwh_year = Decimal(str(totals["E_y"]))
        irradiation_year = Decimal(str(totals["H(i)_y"]))
    except (requests.RequestException, KeyError, ValueError, TypeError) as e:
        logger.warning("PVGIS failed for %s: %s", promocion.slug, e)
        return None

    obj, _ = SolarPotential.objects.update_or_create(
        promocion=promocion,
        defaults={
            "kwh_kwp_year": kwh_year,
            "irradiation_year": irradiation_year,
            "monthly_json": monthly,
            "tilt_deg": PVGIS_DEFAULTS["angle"],
            "azimuth_deg": PVGIS_DEFAULTS["aspect"],
            "system_loss_pct": Decimal(str(PVGIS_DEFAULTS["loss"])),
            "pvgis_version": PVGIS_VERSION,
            "raw_json": data,
        },
    )
    return obj
