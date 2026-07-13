"""IDAE (Instituto para la Diversificación y Ahorro de la Energía) HTTP client.

Reverse-engineered access to https://coches.idae.es — the Spanish ministry's
authoritative WLTP fuel-consumption + CO₂ + DGT-energy-label database for
new vehicles, mandated by Directive 1999/94/CE and RD 837/2002.

Pure HTTP + JSON parsing. No DB writes — those live in `idae_ingest.py` so
this module stays reusable for any subset of marcas / categorías.

Architecture quirks discovered live (any of which silently break a naive
client):

- **Stack is Laravel + jQuery DataTables (server-side).** Two CSRF artefacts
  travel together: the form `_token` (rotated on every page load) and the
  cookie `XSRF-TOKEN` (URL-encoded, must be decoded and sent back as the
  `X-XSRF-TOKEN` header on every AJAX call). Cookie `idae_coches_session`
  binds the request to the same session.

- **There are TWO listing endpoints, both at `POST /ajax`, distinguished by
  `ciclo`:**
    - `ciclo=elec` returns Motorización, Categoría, MTMA, electric specs.
    - `ciclo=wltp` returns combustion consumption + CO₂.
  Both include the SAME idae_id rows — they are joins, not partitions. Merge
  by id after fetching both.

- **The `marca` dropdown is server-rendered into the HTML** — there is no
  `campo=marca` endpoint. We extract the 286 marcas from the form HTML once
  and use them as fixed inputs for per-marca pagination.

- **Rate limit:** `X-RateLimit-Limit: 300` (5-minute bucket inferred). The
  client throttles to 1 req/s by default; flip with the constructor arg if
  you know you have headroom.

PROPUESTA.md §3.1.
"""

from __future__ import annotations

import html
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlencode

import requests

log = logging.getLogger(__name__)


BASE_URL = "https://coches.idae.es"
FORM_PATH = "/base-datos/marca-y-modelo"
AJAX_PATH = "/ajax"
HTTP_TIMEOUT = 30
USER_AGENT = "mu/0.1"
DEFAULT_THROTTLE_S = 1.0
PAGE_LENGTH = 1000  # DataTables `length` — IDAE tolerates this without 4xx.


class IDAEError(RuntimeError):
    """Raised on IDAE HTTP / payload failures."""


# ─────────────────────────────────────────────── parsing helpers


_DECIMAL_RX = re.compile(r"-?\d+(?:[.,]\d+)?")


def _to_decimal(value: object) -> Decimal | None:
    """Parse "13,2" / "13.2" / 13.2 / "" → Decimal or None.

    IDAE's JSON mixes raw numbers and Spanish-locale strings depending on the
    column. Empty strings mean "this vehicle does not report this metric" —
    they are not zero.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip()
    if not s:
        return None
    m = _DECIMAL_RX.search(s.replace(",", "."))
    if not m:
        return None
    try:
        return Decimal(m.group(0))
    except (InvalidOperation, ValueError):
        return None


def _to_int(value: object) -> int | None:
    d = _to_decimal(value)
    if d is None:
        return None
    return int(d)


def _extract_energy_class(html_blob: object) -> str:
    """Pull the A/B/.../S letter out of the `<img>` clasificación column."""
    if not html_blob:
        return ""
    s = str(html_blob)
    # The img filename carries the letter: /img/clasificacion/A.gif → "A".
    m = re.search(r"/clasificacion/([A-GS])\.", s)
    if m:
        return m.group(1)
    # Fallback: parse the title attribute.
    m = re.search(r"Clasificaci[oó]n:\s*([A-GS])\b", s)
    return m.group(1) if m else ""


def _normalize_make_model(
    modelo_raw: str,
    *,
    make_hint: str | None = None,
) -> tuple[str, str]:
    """Split the IDAE Modelo string into (make, model_plus_variant).

    The Modelo string is the marca name concatenated with the model+variant.
    The separator is sometimes a double space ("TESLA  Model X …") and
    sometimes a single one — the catalog has both styles, often within the
    same marca. Relying on the separator alone fails (verified live: VW row
    559685 was parsed with an 81-char make).

    Robust path: when we already know the marca because we paginated by
    `marca_id`, we pass its name as ``make_hint`` and strip that prefix.
    Without a hint we fall back to the double-space heuristic and then to
    the first-single-space split for compatibility.
    """
    s = html.unescape(modelo_raw or "").strip()
    if not s:
        return "", ""

    if make_hint:
        hint = make_hint.strip()
        if s.lower().startswith(hint.lower()):
            return hint, s[len(hint) :].strip()

    parts = re.split(r"\s{2,}", s, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    # Single-word marca, no double-space — fall back to first space.
    first, _, rest = s.partition(" ")
    return first.strip(), rest.strip()


# ─────────────────────────────────────────────── propulsion enum mapping


# Maps IDAE's "Motorización" column to our Vehicle.Propulsion choices.
# Keys are lowercased + accent-stripped on lookup; ordered for first-match.
_PROPULSION_PATTERNS: list[tuple[str, str]] = [
    ("electricos puros", "BEV"),
    # IDAE labels PHEVs as "Híbridos enchufables" (plural) — must match
    # before any "hibrid" / "hibridos" rule, otherwise PHEVs fall into HEV.
    ("enchufa", "PHEV"),
    ("hibrido", "HEV"),
    ("hibridos", "HEV"),
    ("diesel", "DIESEL"),
    ("gasoleo", "DIESEL"),
    ("gnc", "CNG"),
    ("gas natural", "CNG"),
    ("glp", "LPG"),
    ("autogas", "LPG"),
    ("gasolina", "ICE"),
]


def _strip_accents(s: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def map_propulsion(motorizacion: str) -> str | None:
    """Map IDAE's free-text Motorización to a `Vehicle.Propulsion` choice."""
    if not motorizacion:
        return None
    key = _strip_accents(motorizacion).lower().strip()
    for needle, choice in _PROPULSION_PATTERNS:
        if needle in key:
            return choice
    return None


# ─────────────────────────────────────────────── parsed-row dataclasses


@dataclass
class IDAEElecRow:
    """One row from the `ciclo=elec` listing (electric / hybrid specs)."""

    idae_id: int
    make: str
    model: str
    energy_class: str = ""
    propulsion: str | None = None  # Vehicle.Propulsion choice
    category: str = ""
    mtma_kg: int | None = None
    consumption_kwh_100km: Decimal | None = None
    power_kw: Decimal | None = None  # not stored; reserved for future use
    range_wltp_km: int | None = None
    battery_kwh: Decimal | None = None


@dataclass
class IDAEWLTPRow:
    """One row from the `ciclo=wltp` listing (combustion + CO₂)."""

    idae_id: int
    make: str
    model: str
    energy_class: str = ""
    consumption_l_100km_min: Decimal | None = None
    consumption_l_100km_max: Decimal | None = None
    co2_g_km_min: int | None = None
    co2_g_km_max: int | None = None


@dataclass
class Marca:
    idae_id: int
    name: str


# ─────────────────────────────────────────────── Laravel session


@dataclass
class _SessionState:
    cookies: requests.cookies.RequestsCookieJar
    form_token: str
    ajax_token: str
    xsrf_header: str
    marcas: list[Marca] = field(default_factory=list)


class IDAESession:
    """Manages the Laravel CSRF/cookie lifecycle for `coches.idae.es`.

    Lifecycle:
        1. GET  /base-datos/marca-y-modelo   → form `_token` + XSRF cookie
        2. POST /base-datos/marca-y-modelo   → page with embedded AJAX token
                                              and pre-rendered `<select id="marca">`
        3. POST /ajax …                      → using AJAX token + X-XSRF-TOKEN

    The session is single-shot in practice (tokens are session-scoped) and
    must be re-opened if a 419 comes back from `/ajax`.
    """

    def __init__(self, *, throttle_s: float = DEFAULT_THROTTLE_S):
        self.throttle_s = throttle_s
        self._state: _SessionState | None = None
        self._last_request_at = 0.0

    # ---------------- internal helpers

    def _throttle(self) -> None:
        delta = time.monotonic() - self._last_request_at
        if delta < self.throttle_s:
            time.sleep(self.throttle_s - delta)
        self._last_request_at = time.monotonic()

    def _http(
        self,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        cookies=None,
        headers: dict | None = None,
        ajax: bool = False,
    ) -> requests.Response:
        self._throttle()
        url = f"{BASE_URL}{path}"
        h = {"User-Agent": USER_AGENT}
        if ajax:
            h["X-Requested-With"] = "XMLHttpRequest"
            h["Referer"] = f"{BASE_URL}{FORM_PATH}"
        if headers:
            h.update(headers)
        r = requests.request(
            method,
            url,
            data=data,
            cookies=cookies,
            headers=h,
            timeout=HTTP_TIMEOUT,
        )
        return r

    def _open(self) -> _SessionState:
        if self._state is not None:
            return self._state

        # ── Step 1: GET form page → cookies + form _token.
        r = self._http("GET", FORM_PATH)
        if r.status_code != 200:
            raise IDAEError(f"GET {FORM_PATH} returned HTTP {r.status_code}")
        form_token = self._extract_form_token(r.text)
        if not form_token:
            raise IDAEError("Could not extract form _token from initial GET.")

        cookies = r.cookies

        # ── Step 2: POST the form so the next page renders DataTables JS
        # with its own AJAX `_token` and the populated `<select id="marca">`.
        xsrf = self._xsrf_header_value(cookies)
        r = self._http(
            "POST",
            FORM_PATH,
            data={
                "_token": form_token,
                "tipo": "marca-y-modelo",
                "categoria": "",
                "segmento": "",
                "marca": "",
                "modelo": "",
            },
            cookies=cookies,
            headers={"X-XSRF-TOKEN": xsrf},
        )
        if r.status_code != 200:
            raise IDAEError(f"POST {FORM_PATH} returned HTTP {r.status_code}")

        ajax_token = self._extract_ajax_token(r.text)
        if not ajax_token:
            raise IDAEError("Could not extract AJAX _token from results page.")
        marcas = self._extract_marcas(r.text)
        if not marcas:
            log.warning(
                "IDAE marca list parsed empty — selector markup may have changed."
            )

        # Cookies may have rotated after the POST.
        if r.cookies:
            cookies = r.cookies

        self._state = _SessionState(
            cookies=cookies,
            form_token=form_token,
            ajax_token=ajax_token,
            xsrf_header=self._xsrf_header_value(cookies),
            marcas=marcas,
        )
        return self._state

    @staticmethod
    def _extract_form_token(page: str) -> str:
        m = re.search(r'name="_token"\s+value="([^"]+)"', page)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_ajax_token(page: str) -> str:
        # Pattern in the DataTable JS body:
        #     data._token  = "abc123…";
        m = re.search(r'data\._token\s*=\s*"([^"]+)"', page)
        return m.group(1) if m else ""

    @staticmethod
    def _xsrf_header_value(cookies) -> str:
        raw = cookies.get("XSRF-TOKEN", "")
        return unquote(raw) if raw else ""

    @staticmethod
    def _extract_marcas(page: str) -> list[Marca]:
        # Slice the `<select id="marca">…</select>` block then pull options.
        m = re.search(
            r'<select[^>]*id="marca"[^>]*>(.*?)</select>',
            page,
            flags=re.DOTALL,
        )
        if not m:
            return []
        block = m.group(1)
        out: list[Marca] = []
        for opt in re.finditer(r'<option\s+value="(\d+)"[^>]*>([^<]+)</option>', block):
            out.append(
                Marca(
                    idae_id=int(opt.group(1)), name=html.unescape(opt.group(2)).strip()
                )
            )
        return out

    # ---------------- public API

    def marcas(self) -> list[Marca]:
        return list(self._open().marcas)

    def fetch_listing(
        self,
        *,
        ciclo: str,  # 'elec' | 'wltp'
        marca_id: int | None = None,
        categoria_id: int | None = None,
        start: int = 0,
        length: int = PAGE_LENGTH,
    ) -> dict:
        """One DataTables-paginated AJAX call. Returns the raw JSON envelope.

        Caller handles pagination (this method is one page).
        """
        if ciclo not in ("elec", "wltp"):
            raise IDAEError(f"ciclo must be 'elec' or 'wltp', got {ciclo!r}")

        state = self._open()

        filtros_pairs = [
            ("_token", state.ajax_token),
            ("tipo", "marca-y-modelo"),
            ("categoria", str(categoria_id) if categoria_id else ""),
            ("segmento", ""),
            ("marca", str(marca_id) if marca_id else ""),
            ("modelo", ""),
        ]
        filtros_str = urlencode(filtros_pairs)

        data = [
            ("_token", state.ajax_token),
            ("campo", "listado"),
            ("ciclo", ciclo),
            ("filtros", filtros_str),
            ("draw", "1"),
            ("start", str(start)),
            ("length", str(length)),
            ("order[0][column]", "0"),
            ("order[0][dir]", "asc"),
            ("search[value]", ""),
        ]

        r = self._http(
            "POST",
            AJAX_PATH,
            data=data,
            cookies=state.cookies,
            headers={"X-XSRF-TOKEN": state.xsrf_header},
            ajax=True,
        )
        if r.status_code == 419:
            # CSRF mismatch — session expired. Re-open and retry once.
            log.info("IDAE returned 419, re-opening session.")
            self._state = None
            state = self._open()
            # Rebuild the payload with the fresh token.
            data[0] = ("_token", state.ajax_token)
            for i, (k, _) in enumerate(filtros_pairs):
                if k == "_token":
                    filtros_pairs[i] = ("_token", state.ajax_token)
            data[3] = ("filtros", urlencode(filtros_pairs))
            r = self._http(
                "POST",
                AJAX_PATH,
                data=data,
                cookies=state.cookies,
                headers={"X-XSRF-TOKEN": state.xsrf_header},
                ajax=True,
            )
        if r.status_code != 200:
            raise IDAEError(
                f"POST /ajax ciclo={ciclo} returned HTTP {r.status_code}: {r.text[:200]}"
            )
        try:
            return r.json()
        except ValueError as e:
            raise IDAEError(f"IDAE returned non-JSON for ciclo={ciclo}: {e}") from e


# ─────────────────────────────────────────────── high-level paged iterators


def iter_elec(
    session: IDAESession,
    *,
    marca_id: int | None = None,
    make_hint: str | None = None,
    page_length: int = PAGE_LENGTH,
) -> Iterator[IDAEElecRow]:
    """Yield every electric/hybrid row, paging through `ciclo=elec`.

    ``make_hint`` is forwarded to the parser to avoid mis-splitting the
    Modelo string when the marca/model separator is a single space (common
    in VW Turismos rows). When not provided and ``marca_id`` is set, the
    hint is auto-resolved from ``session.marcas()``.
    """
    if make_hint is None and marca_id is not None:
        make_hint = _lookup_marca_name(session, marca_id)
    start = 0
    while True:
        envelope = session.fetch_listing(
            ciclo="elec",
            marca_id=marca_id,
            start=start,
            length=page_length,
        )
        rows = envelope.get("data") or []
        if not rows:
            return
        for raw in rows:
            row = _parse_elec_row(raw, make_hint=make_hint)
            if row is not None:
                yield row
        start += len(rows)
        if len(rows) < page_length:
            return


def iter_wltp(
    session: IDAESession,
    *,
    marca_id: int | None = None,
    make_hint: str | None = None,
    page_length: int = PAGE_LENGTH,
) -> Iterator[IDAEWLTPRow]:
    """Yield every combustion row, paging through `ciclo=wltp`."""
    if make_hint is None and marca_id is not None:
        make_hint = _lookup_marca_name(session, marca_id)
    start = 0
    while True:
        envelope = session.fetch_listing(
            ciclo="wltp",
            marca_id=marca_id,
            start=start,
            length=page_length,
        )
        rows = envelope.get("data") or []
        if not rows:
            return
        for raw in rows:
            row = _parse_wltp_row(raw, make_hint=make_hint)
            if row is not None:
                yield row
        start += len(rows)
        if len(rows) < page_length:
            return


def _lookup_marca_name(session: IDAESession, marca_id: int) -> str | None:
    for m in session.marcas():
        if m.idae_id == marca_id:
            return m.name
    return None


# ─────────────────────────────────────────────── row parsers


def _parse_elec_row(
    raw: list,
    *,
    make_hint: str | None = None,
) -> IDAEElecRow | None:
    """Map one raw `ciclo=elec` JSON row to :class:`IDAEElecRow`.

    Columns (verified live 2026-05-29):
      [0] Modelo  [1] Clas. Energética (HTML img)  [2] Motorización
      [3] Categoría  [4] MTMA (Kg)  [5] Consumo Eléctrico kWh/100
      [6] Potencia eléctrica kW  [7] Autonomía km  [8] Batería kWh
      [9] idae_id (int)
    """
    if not isinstance(raw, list) or len(raw) < 10:
        return None
    try:
        idae_id = int(raw[9])
    except (TypeError, ValueError):
        return None
    make, model = _normalize_make_model(raw[0] or "", make_hint=make_hint)
    return IDAEElecRow(
        idae_id=idae_id,
        make=make,
        model=model,
        energy_class=_extract_energy_class(raw[1]),
        propulsion=map_propulsion(raw[2] or ""),
        category=(raw[3] or "").strip(),
        mtma_kg=_to_int(raw[4]),
        consumption_kwh_100km=_to_decimal(raw[5]),
        power_kw=_to_decimal(raw[6]),
        range_wltp_km=_to_int(raw[7]),
        battery_kwh=_to_decimal(raw[8]),
    )


def _parse_wltp_row(
    raw: list,
    *,
    make_hint: str | None = None,
) -> IDAEWLTPRow | None:
    """Map one raw `ciclo=wltp` JSON row to :class:`IDAEWLTPRow`.

    Columns:
      [0] Modelo  [1] Clas. Energética (HTML img)
      [2] Consumo Mín l/100  [3] Consumo Máx l/100
      [4] CO₂ Mín g/km  [5] CO₂ Máx g/km
      [6] idae_id (int)
    """
    if not isinstance(raw, list) or len(raw) < 7:
        return None
    try:
        idae_id = int(raw[6])
    except (TypeError, ValueError):
        return None
    make, model = _normalize_make_model(raw[0] or "", make_hint=make_hint)
    return IDAEWLTPRow(
        idae_id=idae_id,
        make=make,
        model=model,
        energy_class=_extract_energy_class(raw[1]),
        consumption_l_100km_min=_to_decimal(raw[2]),
        consumption_l_100km_max=_to_decimal(raw[3]),
        co2_g_km_min=_to_int(raw[4]),
        co2_g_km_max=_to_int(raw[5]),
    )
