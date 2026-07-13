"""MINCOTUR (Ministerio de Industria, Comercio y Turismo) HTTP client.

Pure HTTP + JSON parsing for the public *Geoportal de gasolineras* REST API.
No DB writes — those live in `fuel_ingest.py` so this module stays reusable
for any province / municipality filter.

Auth: none (public endpoint). Updated by MINCOTUR ~daily (afternoon).

Endpoint shape:

    GET  https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/
         PreciosCarburantes/EstacionesTerrestres/FiltroProvincia/{IDProvincia}/

Province IDs we care about for Euskal Herria:
    01 → Álava       20 → Gipuzkoa     48 → Bizkaia     31 → Navarra

Quirks of the upstream payload (any of which silently break naive parsers):
- Prices and coordinates are localised strings with a comma decimal separator,
  e.g. ``"1,659"`` → Decimal("1.659").
- Empty strings (``""``) mean "this station does not report this fuel" — they
  are not zero, drop them.
- Field keys carry spaces and a ``.``: ``"C.P."``, ``"Precio Gasolina 95 E5"``,
  ``"Longitud (WGS84)"``.

PROPUESTA.md §3.1, §5.1.
"""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import requests
from urllib3.util.ssl_ import create_urllib3_context

log = logging.getLogger(__name__)


BASE_URL = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
    "PreciosCarburantes"
)
HTTP_TIMEOUT = 30
USER_AGENT = "mubil/0.1 (iareizagau@gmail.com)"


class _LegacyTLSAdapter(requests.adapters.HTTPAdapter):
    """HTTPS adapter that tolerates MS-IIS servers without ``close_notify``.

    MINCOTUR's IIS terminates the TLS connection without sending a clean
    ``close_notify`` alert. OpenSSL 3 (Python 3.12) treats this as a protocol
    violation and raises ``SSLEOFError`` — older OpenSSL 1.1.x silently
    ignored it. We restore the lenient behaviour for this one host (NOT
    globally) by combining three knobs:

    - ``OP_IGNORE_UNEXPECTED_EOF`` — tell OpenSSL 3 to accept the truncated
      shutdown that IIS sends.
    - Force TLS ≤ 1.2 — IIS on this host does not speak 1.3 cleanly.
    - ``SECLEVEL=1`` — re-enables the cipher suites IIS still serves
      (default SECLEVEL=2 blocks several of them in distros built on
      OpenSSL 3.0+).
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        # 0x80 = OP_IGNORE_UNEXPECTED_EOF; literal kept as fallback for
        # platforms where the constant is not exposed.
        ctx.options |= getattr(ssl, "OP_IGNORE_UNEXPECTED_EOF", 0x80)
        # Pin to TLS 1.2 — IIS on this host stutters on 1.3.
        if hasattr(ctx, "maximum_version") and hasattr(ssl, "TLSVersion"):
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            # OpenSSL build without legacy SECLEVEL support — keep going,
            # OP_IGNORE_UNEXPECTED_EOF alone often gets us through.
            pass
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _session() -> requests.Session:
    s = requests.Session()
    s.mount("https://sedeaplicaciones.minetur.gob.es", _LegacyTLSAdapter())
    return s


# Province IDs (INE) for Euskal Herria — default scope of the cron.
PROVINCE_ARABA = "01"
PROVINCE_GIPUZKOA = "20"
PROVINCE_NAVARRA = "31"
PROVINCE_BIZKAIA = "48"
DEFAULT_EH_PROVINCES = (PROVINCE_ARABA, PROVINCE_GIPUZKOA, PROVINCE_BIZKAIA)

# Internal short keys → MINCOTUR payload keys. Add a row here to start ingesting
# a new fuel (Hidrogeno, GLP, …) — the rest of the pipeline picks it up.
FUEL_KEY_MAP: dict[str, str] = {
    "gasolina_95_e5": "Precio Gasolina 95 E5",
    "gasolina_98_e5": "Precio Gasolina 98 E5",
    "gasoleo_a": "Precio Gasoleo A",
    "gasoleo_premium": "Precio Gasoleo Premium",
}


class MincoturError(RuntimeError):
    """Raised on MINCOTUR HTTP / payload failures."""


@dataclass
class FuelStationRecord:
    """One station from MINCOTUR — already parsed into Python-native types."""

    ideess: int
    brand: str = ""
    address: str = ""
    municipality_name: str = ""
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    prices: dict[str, Decimal] = field(default_factory=dict)  # short_key → €/L
    schedule: str = ""
    sale_type: str = ""


# ─────────────────────────────────────────────── parsing helpers


def _to_decimal_eur(value: object) -> Decimal | None:
    """Parse ``"1,659"`` → Decimal("1.659"). Empty/invalid → None."""
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError):
        return None


def _to_float_coord(value: object) -> float | None:
    """Parse ``"43,318"`` → 43.318. Empty/invalid → None."""
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_record(row: dict) -> FuelStationRecord | None:
    """Map one raw MINCOTUR dict to a :class:`FuelStationRecord`.

    Returns ``None`` if the row lacks the minimum we need (id + coordinates) —
    MINCOTUR occasionally publishes broken rows we want to skip silently.
    """
    raw_id = row.get("IDEESS")
    if raw_id is None:
        return None
    try:
        ideess = int(str(raw_id).strip())
    except ValueError:
        return None

    lat = _to_float_coord(row.get("Latitud"))
    # MINCOTUR labels the longitude column literally with the SRID name.
    lon = _to_float_coord(row.get("Longitud (WGS84)") or row.get("Longitud"))
    if lat is None or lon is None:
        return None

    prices: dict[str, Decimal] = {}
    for short_key, payload_key in FUEL_KEY_MAP.items():
        price = _to_decimal_eur(row.get(payload_key))
        if price is not None:
            prices[short_key] = price

    return FuelStationRecord(
        ideess=ideess,
        brand=(row.get("Rótulo") or "").strip(),
        address=(row.get("Dirección") or "").strip(),
        municipality_name=(row.get("Municipio") or "").strip(),
        postal_code=(row.get("C.P.") or "").strip(),
        latitude=lat,
        longitude=lon,
        prices=prices,
        schedule=(row.get("Horario") or "").strip(),
        sale_type=(row.get("Tipo Venta") or "").strip(),
    )


# ─────────────────────────────────────────────── public API


def fetch_province(prov_code: str) -> list[FuelStationRecord]:
    """Fetch every station in one INE province and return parsed records.

    Args:
        prov_code: INE province code as a zero-padded string (``"20"`` for
            Gipuzkoa, ``"01"`` for Álava). Numeric ints are accepted and
            normalised.

    Raises:
        MincoturError: on HTTP failure or non-JSON / unexpected payload shape.
    """
    code = str(prov_code).strip().zfill(2)
    # NB: MINCOTUR's IIS returns 404 if the trailing slash is included.
    url = f"{BASE_URL}/EstacionesTerrestres/FiltroProvincia/{code}"
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    r = _session().get(url, headers=headers, timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise MincoturError(
            f"MINCOTUR returned HTTP {r.status_code} for province {code}: {r.text[:200]}"
        )
    try:
        payload = r.json()
    except ValueError as e:
        raise MincoturError(
            f"MINCOTUR returned non-JSON for province {code}: {e}"
        ) from e

    rows = payload.get("ListaEESSPrecio")
    if not isinstance(rows, list):
        raise MincoturError(
            f"MINCOTUR payload missing 'ListaEESSPrecio' for province {code}."
        )

    records: list[FuelStationRecord] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        rec = _parse_record(raw)
        if rec is not None:
            records.append(rec)
    return records
