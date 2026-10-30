"""
Services for the Amenabar app.

Three responsibilities:
- scrape_amenabar_listado: pull the promotions index from amenabarpromociones.com
- geocode: resolve "<nombre>, <ciudad>" to a lat/lon via Nominatim (1 req/s)
- fetch_pois_overpass: query the Overpass API for POIs around a Point
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from django.contrib.gis.geos import Point
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .models import POI, Promocion

logger = logging.getLogger(__name__)

AMENABAR_INDEX = "https://www.amenabarpromociones.com/es/promociones/"
AMENABAR_FUTURAS = (
    "https://www.amenabarpromociones.com/es/promociones/futuras-promociones.php"
)
AMENABAR_FINALIZADAS = (
    "https://www.amenabarpromociones.com/es/promociones/finalizadas.php"
)

USER_AGENT = "maps.eus-amenabar/1.0 (contact: iareizagau@gmail.com)"


# Human-readable labels for every OSM subtype we classify. Wrapped in
# gettext_lazy so translations fall back cleanly when LANGUAGE_CODE changes.
# Keys match the `subtipo` field written in `store_pois`.

SUBTIPO_LABELS = {
    # Compras
    "supermarket":       _("Supermercado"),
    "convenience":       _("Tienda de alimentación"),
    "bakery":            _("Panadería"),
    # Educación
    "school":            _("Colegio"),
    "kindergarten":      _("Guardería"),
    # Transporte público
    "bus_stop":          _("Parada de autobús"),
    "train_station":     _("Estación de tren"),
    "tram_stop":         _("Parada de tranvía"),
    "subway":            _("Metro"),
    # Vehículos
    "fuel":              _("Gasolinera"),
    "charging_station":  _("Punto de carga eléctrica"),
    "parking":           _("Aparcamiento"),
    "bicycle_rental":    _("Alquiler de bicis"),
    "car_rental":        _("Alquiler de coches"),
    # Comida
    "restaurant":        _("Restaurante"),
    "cafe":              _("Cafetería"),
    "fast_food":         _("Comida rápida"),
    "ice_cream":         _("Heladería"),
    # Bebida
    "bar":               _("Bar"),
    "pub":               _("Pub"),
    "nightclub":         _("Discoteca"),
    # Atractivos
    "museum":            _("Museo"),
    "viewpoint":         _("Mirador"),
    "artwork":           _("Obra de arte"),
    "zoo":               _("Zoo"),
    "theme_park":        _("Parque temático"),
    # Información
    "information":       _("Oficina de turismo"),
    # Salud
    "hospital":          _("Hospital"),
    "clinic":            _("Clínica"),
    "pharmacy":          _("Farmacia"),
    "dentist":           _("Dentista"),
    "veterinary":        _("Veterinario"),
    # Finanzas
    "atm":               _("Cajero automático"),
    "bank":              _("Banco"),
    # Administración
    "post_office":       _("Oficina de correos"),
    "police":            _("Comisaría"),
    "townhall":          _("Ayuntamiento"),
    "courthouse":        _("Juzgado"),
    # Religión
    "place_of_worship":  _("Lugar de culto"),
    # Espacios verdes
    "park":              _("Parque"),
    "garden":            _("Jardín"),
    "nature_reserve":    _("Reserva natural"),
    # Deporte
    "sports_centre":     _("Centro deportivo"),
    "swimming_pool":     _("Piscina"),
    "fitness_centre":    _("Gimnasio"),
    # Cultura
    "cinema":            _("Cine"),
    "theatre":           _("Teatro"),
    "playground":        _("Parque infantil"),
    "community_centre":  _("Centro cívico"),
    # Histórico
    "castle":            _("Castillo"),
    "ruins":             _("Ruinas"),
    "archaeological":    _("Yacimiento arqueológico"),
    "monument":          _("Monumento"),
    # Naturales
    "drinking_water":    _("Fuente"),
    "peak":              _("Cumbre"),
    "cave":              _("Cueva"),
    "beach":             _("Playa"),
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_RATE_S = 1.1  # Nominatim free usage policy = max 1 req/s; be safe.

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Max radius we need to cover with Overpass (15 min bike ≈ 3500 m) + a small
# cushion so client-side filtering never falls off the edge.
POI_FETCH_RADIUS_M = 3800


# --------------------------------------------------------------------------- #
# Scraper
# --------------------------------------------------------------------------- #

@dataclass
class ScrapedPromocion:
    nombre: str
    ciudad: str
    estado: str  # Promocion.Estado value
    porcentaje_vendido: int | None
    nota: str
    detail_url: str
    image_url: str
    source_url: str

    @property
    def slug(self) -> str:
        return slugify(self.nombre)[:120]


_ESTADO_RULES = (
    # Order matters: check "vendida" before "venta".
    ("100% vendido", Promocion.Estado.VENDIDA),
    ("100% vendida", Promocion.Estado.VENDIDA),
    ("finalizada", Promocion.Estado.FINALIZADA),
    ("próxima", Promocion.Estado.PROXIMA),
    ("proxima", Promocion.Estado.PROXIMA),
    ("obras iniciadas", Promocion.Estado.EN_CURSO),
    ("en curso", Promocion.Estado.EN_CURSO),
    ("vendido", Promocion.Estado.EN_CURSO),  # "80% vendido" → aún en curso
    ("vendida", Promocion.Estado.EN_CURSO),
    ("en venta", Promocion.Estado.EN_VENTA),
    ("nueva promoción", Promocion.Estado.EN_VENTA),
)


def _classify_estado(nota: str) -> str:
    low = nota.lower()
    for needle, estado in _ESTADO_RULES:
        if needle in low:
            return estado
    return Promocion.Estado.EN_VENTA


def _extract_percent(nota: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*%", nota)
    if not m:
        return None
    try:
        v = int(m.group(1))
        return v if 0 <= v <= 100 else None
    except ValueError:
        return None


def _fetch(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.text


def scrape_amenabar_listado(urls: Iterable[str] | None = None) -> list[ScrapedPromocion]:
    """Scrape the three index pages and dedupe by (nombre, ciudad)."""
    urls = urls or [AMENABAR_INDEX, AMENABAR_FUTURAS, AMENABAR_FINALIZADAS]

    out: dict[tuple[str, str], ScrapedPromocion] = {}
    for url in urls:
        try:
            html = _fetch(url)
        except Exception as e:
            logger.warning("amenabar scrape %s failed: %s", url, e)
            continue
        for item in _parse_listado(html, url):
            key = (item.nombre.lower(), item.ciudad.lower())
            out.setdefault(key, item)
    return list(out.values())


_CIUDAD_PREFIX_RE = re.compile(
    r"^(?:obra nueva en|promoci[oó]n en|nueva promoci[oó]n en|pr[oó]xima promoci[oó]n en)\s+",
    flags=re.IGNORECASE,
)


def _parse_listado(html: str, source_url: str) -> list[ScrapedPromocion]:
    """
    Each promotion is rendered as a `<div class="foto">` card:
      <div class="foto">
        <a href="https://airesdearganda.com/es"><img ...></a>
        <a href="...">Aires de Arganda</a>
        <a href="...">Obra nueva en Arganda del Rey, Madrid</a>
        <div>Nueva Promoción a la venta</div>   ← badge
        <div>Nueva promoción</div>              ← status
      </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[ScrapedPromocion] = []

    for card in soup.select("div.foto"):
        img = card.find("img")
        link = card.find("a", href=True)
        if not img or not link:
            continue
        href = link["href"].strip()
        if not re.match(r"^https?://", href):
            continue
        if any(
            d in href
            for d in (
                "amenabarpromociones.com",
                "instagram.com",
                "facebook.com",
                "amenabar.es",
            )
        ):
            continue

        texts = [s.strip() for s in card.stripped_strings if s.strip()]
        if not texts:
            continue

        nombre = texts[0]
        ciudad_raw = texts[1] if len(texts) > 1 else ""
        badge_text = " · ".join(texts[2:]) if len(texts) > 2 else ciudad_raw

        ciudad = _CIUDAD_PREFIX_RE.sub("", ciudad_raw)
        ciudad = re.split(r"[·|]", ciudad)[0].strip() or nombre

        full_text = " ".join(texts)
        results.append(
            ScrapedPromocion(
                nombre=nombre,
                ciudad=ciudad,
                estado=_classify_estado(full_text),
                porcentaje_vendido=_extract_percent(full_text),
                nota=badge_text[:200],
                detail_url=href,
                image_url=(img.get("src") or img.get("data-src") or "").strip(),
                source_url=source_url,
            )
        )
    return results


# --------------------------------------------------------------------------- #
# Geocoding (Nominatim)
# --------------------------------------------------------------------------- #

def geocode_nominatim(query: str) -> Point | None:
    """One-shot query against Nominatim. Returns a 4326 Point or None."""
    params = {"q": query, "format": "json", "limit": 1, "countrycodes": "es"}
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("nominatim %r failed: %s", query, e)
        return None
    if not data:
        return None
    try:
        return Point(float(data[0]["lon"]), float(data[0]["lat"]), srid=4326)
    except (KeyError, ValueError, TypeError):
        return None


def geocode_promocion(p: Promocion) -> Point | None:
    """Try `nombre, ciudad` first, then fall back to `ciudad` alone."""
    for q in (f"{p.nombre}, {p.ciudad}, España", f"{p.ciudad}, España"):
        pt = geocode_nominatim(q)
        if pt:
            return pt
        time.sleep(NOMINATIM_RATE_S)
    return None


# --------------------------------------------------------------------------- #
# Overpass POIs
# --------------------------------------------------------------------------- #

# Mapping: (overpass selector fragment) → our category + default subtipo tag.
# Each entry becomes one `nwr[...](around:R,lat,lon);` line in the query.
OVERPASS_RULES: list[tuple[str, str, str]] = [
    # Compras diarias
    ('["shop"="supermarket"]', POI.Categoria.COMPRAS, "supermarket"),
    ('["shop"="convenience"]', POI.Categoria.COMPRAS, "convenience"),
    ('["shop"="bakery"]', POI.Categoria.COMPRAS, "bakery"),
    # Educación
    ('["amenity"="school"]', POI.Categoria.EDUCACION, "school"),
    ('["amenity"="kindergarten"]', POI.Categoria.EDUCACION, "kindergarten"),
    # Transporte público
    ('["highway"="bus_stop"]', POI.Categoria.TRANSPORTE, "bus_stop"),
    ('["railway"="station"]', POI.Categoria.TRANSPORTE, "train_station"),
    ('["railway"="tram_stop"]', POI.Categoria.TRANSPORTE, "tram_stop"),
    ('["station"="subway"]', POI.Categoria.TRANSPORTE, "subway"),
    # Vehículos
    ('["amenity"="fuel"]', POI.Categoria.VEHICULOS, "fuel"),
    ('["amenity"="charging_station"]', POI.Categoria.VEHICULOS, "charging_station"),
    ('["amenity"="parking"]', POI.Categoria.VEHICULOS, "parking"),
    ('["amenity"="bicycle_rental"]', POI.Categoria.VEHICULOS, "bicycle_rental"),
    ('["amenity"="car_rental"]', POI.Categoria.VEHICULOS, "car_rental"),
    # Comida
    ('["amenity"="restaurant"]', POI.Categoria.COMIDA, "restaurant"),
    ('["amenity"="cafe"]', POI.Categoria.COMIDA, "cafe"),
    ('["amenity"="fast_food"]', POI.Categoria.COMIDA, "fast_food"),
    ('["amenity"="ice_cream"]', POI.Categoria.COMIDA, "ice_cream"),
    # Bebida
    ('["amenity"="bar"]', POI.Categoria.BEBIDA, "bar"),
    ('["amenity"="pub"]', POI.Categoria.BEBIDA, "pub"),
    ('["amenity"="nightclub"]', POI.Categoria.BEBIDA, "nightclub"),
    # Atractivos
    ('["tourism"="museum"]', POI.Categoria.ATRACTIVOS, "museum"),
    ('["tourism"="viewpoint"]', POI.Categoria.ATRACTIVOS, "viewpoint"),
    ('["tourism"="artwork"]', POI.Categoria.ATRACTIVOS, "artwork"),
    ('["tourism"="zoo"]', POI.Categoria.ATRACTIVOS, "zoo"),
    ('["tourism"="theme_park"]', POI.Categoria.ATRACTIVOS, "theme_park"),
    # Información turística
    ('["tourism"="information"]', POI.Categoria.INFORMACION, "information"),
    # Salud
    ('["amenity"="hospital"]', POI.Categoria.SALUD, "hospital"),
    ('["amenity"="clinic"]', POI.Categoria.SALUD, "clinic"),
    ('["amenity"="pharmacy"]', POI.Categoria.SALUD, "pharmacy"),
    ('["amenity"="dentist"]', POI.Categoria.SALUD, "dentist"),
    ('["amenity"="veterinary"]', POI.Categoria.SALUD, "veterinary"),
    # Finanzas
    ('["amenity"="atm"]', POI.Categoria.FINANZAS, "atm"),
    ('["amenity"="bank"]', POI.Categoria.FINANZAS, "bank"),
    # Administración
    ('["amenity"="post_office"]', POI.Categoria.ADMINISTRACION, "post_office"),
    ('["amenity"="police"]', POI.Categoria.ADMINISTRACION, "police"),
    ('["amenity"="townhall"]', POI.Categoria.ADMINISTRACION, "townhall"),
    ('["amenity"="courthouse"]', POI.Categoria.ADMINISTRACION, "courthouse"),
    # Religión
    ('["amenity"="place_of_worship"]', POI.Categoria.RELIGION, "place_of_worship"),
    # Espacios verdes
    ('["leisure"="park"]', POI.Categoria.VERDES, "park"),
    ('["leisure"="garden"]', POI.Categoria.VERDES, "garden"),
    ('["leisure"="nature_reserve"]', POI.Categoria.VERDES, "nature_reserve"),
    # Deporte
    ('["leisure"="sports_centre"]', POI.Categoria.DEPORTE, "sports_centre"),
    ('["leisure"="swimming_pool"]', POI.Categoria.DEPORTE, "swimming_pool"),
    ('["leisure"="fitness_centre"]', POI.Categoria.DEPORTE, "fitness_centre"),
    # Cultura y ocio
    ('["amenity"="cinema"]', POI.Categoria.CULTURA, "cinema"),
    ('["amenity"="theatre"]', POI.Categoria.CULTURA, "theatre"),
    ('["leisure"="playground"]', POI.Categoria.CULTURA, "playground"),
    ('["amenity"="community_centre"]', POI.Categoria.CULTURA, "community_centre"),
    # Histórico
    ('["historic"="castle"]', POI.Categoria.HISTORICO, "castle"),
    ('["historic"="ruins"]', POI.Categoria.HISTORICO, "ruins"),
    ('["historic"="archaeological_site"]', POI.Categoria.HISTORICO, "archaeological"),
    ('["historic"="monument"]', POI.Categoria.HISTORICO, "monument"),
    # Elementos naturales
    ('["amenity"="drinking_water"]', POI.Categoria.NATURAL, "drinking_water"),
    ('["natural"="peak"]', POI.Categoria.NATURAL, "peak"),
    ('["natural"="cave_entrance"]', POI.Categoria.NATURAL, "cave"),
    ('["natural"="beach"]', POI.Categoria.NATURAL, "beach"),
]


def _overpass_query(lat: float, lon: float, radius_m: int) -> str:
    parts = [
        f'nwr{sel}(around:{radius_m},{lat},{lon});'
        for (sel, _, _) in OVERPASS_RULES
    ]
    body = "\n".join(parts)
    return f"[out:json][timeout:60];\n(\n{body}\n);\nout center tags;"


OVERPASS_MIRRORS = (
    # Verificado 2026-10-30 — este responde cuando los oficiales están 502.
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


def fetch_pois_overpass(
    lat: float, lon: float, radius_m: int = POI_FETCH_RADIUS_M,
) -> list[dict]:
    """Fetch POIs rotating mirrors. One shot per mirror with a short timeout —
    worst case ~90 s per failed promotion instead of 15 min."""
    q = _overpass_query(lat, lon, radius_m)
    last_err = None
    for mirror in OVERPASS_MIRRORS:
        try:
            resp = requests.post(
                mirror,
                data={"data": q},
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            if resp.status_code in (429, 502, 503, 504):
                last_err = f"{mirror} → {resp.status_code}"
                continue
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except requests.RequestException as e:
            last_err = f"{mirror} → {e}"
    raise RuntimeError(f"All Overpass mirrors failed: {last_err}")


def _classify_element(tags: dict) -> tuple[str, str] | None:
    """Pick the first matching rule for an element's tags."""
    for selector, category, subtype in OVERPASS_RULES:
        # Selectors are like '["amenity"="restaurant"]'.
        m = re.match(r'\["([^"]+)"="([^"]+)"\]', selector)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if tags.get(k) == v:
            return category, subtype
    return None


# Walking at 4.5 km/h. Street networks are ~1.3x longer than the straight
# line in typical Spanish urban fabric, so minutes are an estimate until we
# switch to real isochrones.
WALK_M_PER_MIN = 75
CIRCUITY = 1.3
RADIUS_5_MIN_M = 400
RADIUS_15_MIN_M = 1200


def nearest_by_category(promocion: Promocion) -> list[dict]:
    """Nearest POI per category plus counts within 5' / 15' walking."""
    from django.contrib.gis.db.models.functions import Distance
    from django.contrib.gis.measure import D
    from django.db.models import Count, Q

    center = promocion.location
    base = POI.objects.filter(promocion=promocion)

    nearest = (
        base.annotate(dist=Distance("location", center))
        .order_by("categoria", "dist")
        .distinct("categoria")
    )
    counts = {
        row["categoria"]: row
        for row in base.values("categoria").annotate(
            n_5=Count("id", filter=Q(location__distance_lte=(center, D(m=RADIUS_5_MIN_M)))),
            n_15=Count("id", filter=Q(location__distance_lte=(center, D(m=RADIUS_15_MIN_M)))),
        )
    }

    out = []
    for poi in nearest:
        dist_m = poi.dist.m
        c = counts.get(poi.categoria, {})
        out.append({
            "categoria": poi.categoria,
            "nombre": poi.nombre,
            "subtipo": poi.subtipo,
            "lat": poi.location.y,
            "lon": poi.location.x,
            "dist_m": round(dist_m),
            "walk_min": max(1, round(dist_m * CIRCUITY / WALK_M_PER_MIN)),
            "n_5": c.get("n_5", 0),
            "n_15": c.get("n_15", 0),
        })
    return out


def store_pois(promocion: Promocion, elements: list[dict]) -> int:
    """Persist Overpass elements as POI rows. Returns count created/updated."""
    kept = 0
    seen = set()
    for el in elements:
        tags = el.get("tags") or {}
        cls = _classify_element(tags)
        if not cls:
            continue
        category, subtype = cls

        if "lat" in el and "lon" in el:
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue

        osm_type = el.get("type", "")
        osm_id = el.get("id")
        if not osm_id:
            continue
        key = (osm_type, osm_id)
        if key in seen:
            continue
        seen.add(key)

        POI.objects.update_or_create(
            promocion=promocion,
            osm_type=osm_type,
            osm_id=osm_id,
            defaults={
                "nombre": (tags.get("name") or "")[:200],
                "categoria": category,
                "subtipo": subtype,
                "tags": tags,
                "location": Point(float(lon), float(lat), srid=4326),
            },
        )
        kept += 1
    return kept
