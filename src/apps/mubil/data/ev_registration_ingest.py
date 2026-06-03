"""Province-level EV-registration ingest into `EVRegistration`.

Source intent (see model docstring): one-shot CSV derived from DGT matriculaciones
(datos.gob.es). The DGT microdata download sits behind a JSF portal with no clean
static URL, so the workflow mirrors the other CSVs already in `data/`
(EstacionesDeServicio.csv, PuntosCarga.csv): a human drops a CSV in
`apps/mubil/data/` and this module seeds it idempotently.

Granularity: PROVINCE (Araba / Bizkaia / Gipuzkoa). Municipality-level is a
post-premio enrichment — it needs a municipio-name → NAIA mapping that province
codes sidestep entirely. Province rows are stored with a `PROV-<INE>` sentinel in
`municipality_naia` so they never collide with future municipal NAIA rows and are
trivially filterable (`municipality_naia__startswith='PROV-'`).

CSV contract (column names are matched case/space/accent-insensitively; the first
header that matches each role wins):
    provincia       — name ("Araba"/"Álava"/"Bizkaia"/"Gipuzkoa") or INE code (01/48/20)
    anio | año | year
    mes | month
    propulsion | combustible | tipo  — raw label, normalised to Vehicle.Propulsion
    matriculaciones | count | total | n  — integer count

Rows whose province is outside Euskal Herria, or whose propulsion can't be
mapped, are skipped and counted in stats (never silently dropped).
"""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from apps.mubil.models import EVRegistration, Vehicle

# INE province code → canonical display name for the 3 Basque historical territories.
EH_PROVINCES: dict[str, str] = {
    "01": "Araba",
    "48": "Bizkaia",
    "20": "Gipuzkoa",
}

# Accept names/aliases → INE code. Keys are normalised (lowercase, no accents).
_PROVINCE_ALIASES: dict[str, str] = {
    "01": "01", "araba": "01", "alava": "01",
    "48": "48", "bizkaia": "48", "vizcaya": "48",
    "20": "20", "gipuzkoa": "20", "guipuzcoa": "20",
}

# Raw propulsion labels → Vehicle.Propulsion. Keys normalised.
_PROPULSION_ALIASES: dict[str, str] = {
    "bev": Vehicle.Propulsion.BEV,
    "electrico": Vehicle.Propulsion.BEV,
    "electrico puro": Vehicle.Propulsion.BEV,
    "electrico (bev)": Vehicle.Propulsion.BEV,
    "be": Vehicle.Propulsion.BEV,
    "phev": Vehicle.Propulsion.PHEV,
    "hibrido enchufable": Vehicle.Propulsion.PHEV,
    "electrico hibrido enchufable": Vehicle.Propulsion.PHEV,
    "hev": Vehicle.Propulsion.HEV,
    "hibrido": Vehicle.Propulsion.HEV,
    "hibrido no enchufable": Vehicle.Propulsion.HEV,
    "ice": Vehicle.Propulsion.ICE,
    "gasolina": Vehicle.Propulsion.ICE,
    "diesel": Vehicle.Propulsion.DIESEL,
    "gasoleo": Vehicle.Propulsion.DIESEL,
    "cng": Vehicle.Propulsion.CNG,
    "gas natural": Vehicle.Propulsion.CNG,
    "lpg": Vehicle.Propulsion.LPG,
    "glp": Vehicle.Propulsion.LPG,
    "autogas": Vehicle.Propulsion.LPG,
}

# Header-role → accepted normalised header names (first match wins).
_HEADER_ROLES: dict[str, tuple[str, ...]] = {
    "province": ("provincia", "province", "territorio", "cod_provincia"),
    "year": ("anio", "ano", "year", "ejercicio"),
    "month": ("mes", "month"),
    "propulsion": ("propulsion", "combustible", "tipo", "tipo_propulsion", "fuel"),
    "count": ("matriculaciones", "count", "total", "n", "num", "cantidad"),
}

DEFAULT_CSV = Path(__file__).resolve().parent / "MatriculacionesEV_EH.csv"


def _norm(s: str) -> str:
    """lowercase, strip, drop accents — for tolerant header/value matching."""
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


@dataclass
class EVRegIngestStats:
    source: str = ""
    rows_read: int = 0
    upserted: int = 0
    skipped_province: int = 0
    skipped_propulsion: int = 0
    skipped_malformed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "rows_read": self.rows_read,
            "upserted": self.upserted,
            "skipped_province": self.skipped_province,
            "skipped_propulsion": self.skipped_propulsion,
            "skipped_malformed": self.skipped_malformed,
            "errors": self.errors[:10],
        }


def _resolve_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map each role to the actual CSV header. Raises if a required role is missing."""
    norm_to_actual = {_norm(h): h for h in (fieldnames or [])}
    resolved: dict[str, str] = {}
    for role, candidates in _HEADER_ROLES.items():
        for cand in candidates:
            if cand in norm_to_actual:
                resolved[role] = norm_to_actual[cand]
                break
    missing = [r for r in _HEADER_ROLES if r not in resolved]
    if missing:
        raise ValueError(
            f"CSV missing required column(s) for {missing}. "
            f"Headers seen: {list(fieldnames or [])}"
        )
    return resolved


def ingest_csv(path: str | Path | None = None, *, dry_run: bool = False) -> EVRegIngestStats:
    """Parse a province-level matriculaciones CSV and upsert EVRegistration rows.

    Idempotent: re-running the same CSV updates counts in place (unique key is
    municipality_naia + year + month + propulsion).
    """
    csv_path = Path(path) if path else DEFAULT_CSV
    stats = EVRegIngestStats(source=str(csv_path))
    if not csv_path.exists():
        stats.errors.append(f"file not found: {csv_path}")
        return stats

    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = _resolve_headers(reader.fieldnames or [])
        pending: list[EVRegistration] = []

        for raw in reader:
            stats.rows_read += 1
            code = _PROVINCE_ALIASES.get(_norm(raw[cols["province"]]))
            if code not in EH_PROVINCES:
                stats.skipped_province += 1
                continue
            prop = _PROPULSION_ALIASES.get(_norm(raw[cols["propulsion"]]))
            if prop is None:
                stats.skipped_propulsion += 1
                continue
            try:
                year = int(raw[cols["year"]])
                month = int(raw[cols["month"]])
                count = int(float(raw[cols["count"]].replace(".", "").replace(",", ".")))
                if not (1 <= month <= 12) or year < 2000 or count < 0:
                    raise ValueError
            except (ValueError, KeyError, AttributeError):
                stats.skipped_malformed += 1
                continue

            pending.append(EVRegistration(
                municipality_naia=f"PROV-{code}",
                municipality_name=EH_PROVINCES[code],
                year=year, month=month, propulsion=prop, count=count,
            ))

    if dry_run:
        stats.upserted = len(pending)
        return stats

    with transaction.atomic():
        for obj in pending:
            EVRegistration.objects.update_or_create(
                municipality_naia=obj.municipality_naia,
                year=obj.year, month=obj.month, propulsion=obj.propulsion,
                defaults={"municipality_name": obj.municipality_name, "count": obj.count},
            )
            stats.upserted += 1
    return stats
