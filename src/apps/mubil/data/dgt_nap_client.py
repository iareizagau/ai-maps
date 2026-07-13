"""DGT NAP DATEX II ``EnergyInfrastructureTablePublication`` client.

Pure HTTP + XML parsing for the DGT National Access Point charging-station
feed. No DB writes — those live in :mod:`charging_ingest`.

Feed: https://infocar.dgt.es/datex2/v3/miterd/EnergyInfrastructureTablePublication/electrolineras.xml

Schema spec: https://docs.datex2.eu/levels/mastering/energy/

Why streaming (``iterparse``): the feed is ~85 MB (nationwide, ~12k sites).
A DOM parse would blow up memory; we walk it event-by-event and clear each
``egi:energyInfrastructureSite`` after extracting its record.

EH filter: the only province signal DGT exposes is a free-text addressLine
("Provincia: Bizkaia"). DGT publishes ``lang="es"`` content using the local
canonical forms (Bizkaia / Gipuzkoa / Araba / Navarra) — never Vizcaya / Álava —
verified against the 2026-06-11 snapshot.

PROPUESTA.md §3.1.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import IO

import requests

from apps.mubil.data.openchargemap_client import ChargingPOIRecord

log = logging.getLogger(__name__)


BASE_URL = (
    "https://infocar.dgt.es/datex2/v3/miterd/"
    "EnergyInfrastructureTablePublication/electrolineras.xml"
)
HTTP_TIMEOUT = 120  # 85 MB feed, give it room on slow links
USER_AGENT = "mubil/0.1 "

# Canonical province strings as published by DGT in the lang="es" addressLine,
# verified against the 2026-06-11 snapshot. Bizkaia / Gipuzkoa / Navarra ship
# as the bare local name; Araba is the only one that ships hyphenated with its
# castellano alias ("Araba/Álava") — exact string match, no other variants
# appear. If DGT later normalises the form, extend this set (it's cheap).
EH_PROVINCES = frozenset({"Bizkaia", "Gipuzkoa", "Araba/Álava", "Navarra"})

# DATEX II v3 namespaces. Hard-coded in Clark notation so iterparse tag
# comparisons are O(1) string equality.
_NS_EGI = "{http://datex2.eu/schema/3/energyInfrastructure}"
_NS_FAC = "{http://datex2.eu/schema/3/facilities}"
_NS_LOC = "{http://datex2.eu/schema/3/locationReferencing}"
_NS_LOCX = "{http://datex2.eu/schema/3/locationExtension}"
_NS_COM = "{http://datex2.eu/schema/3/common}"

_SITE_TAG = f"{_NS_EGI}energyInfrastructureSite"

# Address line prefixes DGT inserts before the actual value.
_PROVINCIA_PREFIX = "Provincia:"


class DGTNAPError(RuntimeError):
    """Raised on DGT NAP HTTP / XML payload failures."""


# ─────────────────────────────────────────────── parsing helpers


def _watts_text_to_kw(value: str | None) -> Decimal | None:
    """``"22000.0"`` (watts) → ``Decimal("22.00")`` (kW). Empty/invalid → None."""
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    try:
        watts = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    return (watts / Decimal("1000")).quantize(Decimal("0.01"))


def _parse_iso8601(value: str | None) -> datetime | None:
    """Parse DATEX II timestamps (``2026-06-09T10:57:18.000+02:00``).

    Returns timezone-aware UTC, or None on parse failure.
    """
    if not value:
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _text_of(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _address_line_text(line_elem: ET.Element) -> str:
    """Extract the human text from one ``locx:addressLine`` element."""
    return _text_of(line_elem.find(f"./{_NS_LOCX}text/{_NS_COM}values/{_NS_COM}value"))


def _parse_site(elem: ET.Element, *, eh_only: bool) -> ChargingPOIRecord | None:
    """Map one ``egi:energyInfrastructureSite`` element to a record.

    Returns ``None`` to skip (missing id/coords, or filtered out by EH).
    """
    site_id = elem.get("id") or ""
    if not site_id:
        return None

    # NOTE: ``locationReference`` is in the ``fac:`` namespace (typed via
    # ``xsi:type="loc:PointLocation"``), not the ``loc:`` namespace despite
    # what the type attribute suggests. Verified against the live feed.
    lat_text = _text_of(
        elem.find(
            f"./{_NS_FAC}locationReference/{_NS_LOC}coordinatesForDisplay/{_NS_LOC}latitude"
        )
    )
    lon_text = _text_of(
        elem.find(
            f"./{_NS_FAC}locationReference/{_NS_LOC}coordinatesForDisplay/{_NS_LOC}longitude"
        )
    )
    try:
        lat = float(lat_text)
        lon = float(lon_text)
    except ValueError:
        return None

    addr_lines: list[str] = []
    provincia = ""
    for line in elem.findall(
        f"./{_NS_FAC}locationReference/{_NS_LOC}_locationReferenceExtension"
        f"/{_NS_LOC}facilityLocation/{_NS_LOCX}address/{_NS_LOCX}addressLine"
    ):
        txt = _address_line_text(line)
        if not txt:
            continue
        addr_lines.append(txt)
        if txt.startswith(_PROVINCIA_PREFIX):
            provincia = txt[len(_PROVINCIA_PREFIX) :].strip()

    if eh_only and provincia not in EH_PROVINCES:
        return None

    operator = _text_of(
        elem.find(f"./{_NS_FAC}operator/{_NS_FAC}name/{_NS_COM}values/{_NS_COM}value")
    )

    connectors: list[dict] = []
    max_kw: Decimal | None = None
    for cn in elem.findall(
        f"./{_NS_EGI}energyInfrastructureStation/{_NS_EGI}refillPoint/{_NS_EGI}connector"
    ):
        kw = _watts_text_to_kw(
            _text_of(cn.find(f"./{_NS_EGI}maxPowerAtSocket")) or None
        )
        if kw is not None and (max_kw is None or kw > max_kw):
            max_kw = kw
        connectors.append(
            {
                "type": _text_of(cn.find(f"./{_NS_EGI}connectorType")),
                "kw": str(kw) if kw is not None else "",
                "mode": _text_of(cn.find(f"./{_NS_EGI}chargingMode")),
                "format": _text_of(cn.find(f"./{_NS_EGI}connectorFormat")),
            }
        )

    last_updated = _parse_iso8601(
        _text_of(elem.find(f"./{_NS_FAC}lastUpdated")) or None
    )

    return ChargingPOIRecord(
        external_id=f"dgt_nap-{site_id}",
        operator=operator,
        address=", ".join(addr_lines),
        municipality_name="",  # Free-text only inside addressLines; not worth re-parsing.
        postal_code="",
        latitude=lat,
        longitude=lon,
        power_kw=max_kw,
        connectors=connectors,
        last_verified_at=last_updated,
    )


# ─────────────────────────────────────────────── public API


def parse_stream(
    source: str | IO[bytes],
    *,
    eh_only: bool = False,
) -> list[ChargingPOIRecord]:
    """Parse a DATEX II EnergyInfrastructureTablePublication stream.

    Args:
        source: filename or binary file-like object. Stream-friendly — the
            element tree is never materialised in full.
        eh_only: when True, drop sites whose Provincia: addressLine is not
            in :data:`EH_PROVINCES`. Default ``False`` — emit every site in
            the feed (~12k nationwide).

    Memory: each ``energyInfrastructureSite`` is cleared right after its record
    is emitted, so peak resident size stays bounded regardless of feed length.
    """
    records: list[ChargingPOIRecord] = []
    # "end" events only — we wait until each site is fully parsed before
    # clearing it. The root accumulates emptied <site/> shells; at 12k sites
    # those amount to a few MB, negligible next to the 85 MB feed itself, so
    # we don't bother detaching from root.
    for _event, elem in ET.iterparse(source, events=("end",)):
        if elem.tag != _SITE_TAG:
            continue
        try:
            rec = _parse_site(elem, eh_only=eh_only)
        finally:
            elem.clear()
        if rec is not None:
            records.append(rec)
    return records


def fetch_and_parse(
    *,
    url: str = BASE_URL,
    eh_only: bool = False,
) -> list[ChargingPOIRecord]:
    """Stream the live DGT NAP feed and parse it into records.

    Args:
        url: override the canonical feed URL (useful for tests/mirrors).
        eh_only: when True, restrict to Euskal Herria provinces. Default
            ``False`` — loads every site in the feed (~12k nationwide).

    Raises:
        DGTNAPError: on HTTP failure or malformed XML.
    """
    headers = {
        "Accept": "application/xml",
        "User-Agent": USER_AGENT,
    }
    try:
        r = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT, stream=True)
    except requests.RequestException as e:
        raise DGTNAPError(f"DGT NAP request failed: {e}") from e

    if r.status_code >= 400:
        raise DGTNAPError(f"DGT NAP returned HTTP {r.status_code}")

    # Transparent gzip decode so iterparse sees plain XML bytes.
    r.raw.decode_content = True
    try:
        return parse_stream(r.raw, eh_only=eh_only)
    except ET.ParseError as e:
        raise DGTNAPError(f"DGT NAP returned malformed XML: {e}") from e
