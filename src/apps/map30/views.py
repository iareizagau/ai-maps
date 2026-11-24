from __future__ import annotations

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from apps.mubil.models import ChargingStation

from .models import MapEntry


def _common_ctx(entry: MapEntry | None = None, parent_template: str = "map30/base.html") -> dict:
    return {
        "carto_api_key": settings.CARTO_API_KEY,
        "entry": entry,
        "parent_template": parent_template,
    }


def index(request):
    """Calendario — rejilla con los 30 días."""
    entries = list(MapEntry.objects.all().order_by("day"))
    return render(
        request,
        "map30/index.html",
        {**_common_ctx(), "entries": entries},
    )


def day_detail(request, day: int):
    """Detalle de un día. Despacha al template específico del día."""
    entry = get_object_or_404(MapEntry, day=day)

    try:
        get_template(entry.template_path)
    except TemplateDoesNotExist as exc:
        raise Http404(f"Template ausente: {entry.template_path}") from exc

    prev_entry = MapEntry.objects.filter(day=entry.prev_day).first() if entry.prev_day else None
    next_entry = MapEntry.objects.filter(day=entry.next_day).first() if entry.next_day else None

    return render(
        request,
        entry.template_path,
        {
            **_common_ctx(entry),
            "prev_entry": prev_entry,
            "next_entry": next_entry,
        },
    )


def day_capture(request, day: int):
    """Vista 1200×630 lista para captura manual (LinkedIn OG).

    Reutiliza el template del día pero inyecta `capture_base.html` como padre.
    Útil para abrir en Chrome y hacer `Cmd/Ctrl+Shift+P → Capture full size screenshot`.
    """
    entry = get_object_or_404(MapEntry, day=day)
    try:
        get_template(entry.template_path)
    except TemplateDoesNotExist as exc:
        raise Http404(f"Template ausente: {entry.template_path}") from exc
    return render(
        request,
        entry.template_path,
        _common_ctx(entry, parent_template="map30/capture_base.html"),
    )


# ------------------------------------------------------------------
# Data endpoints por día
# ------------------------------------------------------------------


def day01_points_geojson(request):
    """GeoJSON de puntos de recarga EV para el día 1 (Points).

    Reutiliza `mubil.ChargingStation`. Filtra por bbox opcional para tiles
    grandes; por defecto devuelve todos (pocos miles, aceptable sin tiling).
    """
    qs = ChargingStation.objects.filter(geom__isnull=False).only(
        "id", "operator", "power_kw", "geom", "connectors"
    )
    features = []
    for cs in qs.iterator(chunk_size=1000):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [cs.geom.x, cs.geom.y],
                },
                "properties": {
                    "id": cs.id,
                    "operator": cs.operator or "",
                    "kw": float(cs.power_kw) if cs.power_kw is not None else None,
                },
            }
        )
    return JsonResponse(
        {"type": "FeatureCollection", "features": features},
        json_dumps_params={"separators": (",", ":")},
    )


# ------------------------------------------------------------------
# Día 4 — Clusters de pintxos (Parte Vieja de Donostia).
# Como el modelo pintxos.Restaurant tiene pocos registros, servimos una
# muestra curada de bares icónicos para ilustrar el clustering.
# ------------------------------------------------------------------

_PINTXOS_PARTE_VIEJA = [
    ("La Cuchara de San Telmo", -1.9859, 43.3245),
    ("Ganbara", -1.9871, 43.3239),
    ("Borda Berri", -1.9857, 43.3242),
    ("Txepetxa", -1.9846, 43.3246),
    ("Atari", -1.9869, 43.3236),
    ("Gandarias", -1.9866, 43.3236),
    ("Astelena 1997", -1.9874, 43.3234),
    ("Bar Nestor", -1.9867, 43.3237),
    ("A Fuego Negro", -1.9865, 43.3236),
    ("Zeruko", -1.9870, 43.3237),
    ("Bar Txondorra", -1.9862, 43.3243),
    ("Casa Alcalde", -1.9854, 43.3251),
    ("Bar Sport", -1.9868, 43.3238),
    ("Goiz Argi", -1.9868, 43.3239),
    ("Beti Jai Berria", -1.9872, 43.3235),
    ("La Mejillonera", -1.9868, 43.3236),
    ("Bergara", -1.9879, 43.3221),
    ("Aloña Berri", -1.9742, 43.3159),
    ("Hidalgo 56", -1.9826, 43.3194),
    ("Zazpi", -1.9865, 43.3235),
    ("Narru", -1.9798, 43.3199),
    ("Bodegón Alejandro", -1.9865, 43.3239),
    ("La Viña", -1.9862, 43.3246),
    ("Bar Néstor (Zabaleta)", -1.9867, 43.3237),
    ("Haizea", -1.9874, 43.3239),
    ("Antonio Bar", -1.9848, 43.3203),
    ("Casa Vallés", -1.9825, 43.3193),
    ("Oquendo", -1.9829, 43.3202),
    ("Txirimiri", -1.9810, 43.3185),
    ("Kata 4", -1.9850, 43.3238),
]


def day04_pintxos_geojson(request):
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"name": name},
        }
        for name, lng, lat in _PINTXOS_PARTE_VIEJA
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features})


# ------------------------------------------------------------------
# Día 11 — Festivales de música. Curada manualmente; el modelo kultur.CulturalEvent
# no incluye categorización "festival vs evento suelto", por eso embebemos aquí.
# ------------------------------------------------------------------

_FESTIVALES = [
    ("BBK Live",              -2.978, 43.288, 115000, "Bilbao"),
    ("Jazzaldia",             -1.978, 43.321, 165000, "Donostia"),
    ("Azkena Rock Festival",  -2.681, 42.846,  38000, "Vitoria-Gasteiz"),
    ("Vitoria Jazz Festival", -2.670, 42.847,  50000, "Vitoria-Gasteiz"),
    ("Zinemaldia (SSIFF)",    -1.986, 43.319, 185000, "Donostia"),
    ("Mundaka Festival",      -2.697, 43.407,  32000, "Mundaka"),
    ("Hatortxu Rock",         -1.645, 42.870,  12000, "Atarrabia"),
    ("Kalakan Festibala",     -1.479, 43.493,  18000, "Baiona"),
    ("Musikaria",             -2.935, 43.263,   8000, "Bilbao"),
    ("Gaztetxe Fest",         -1.981, 43.320,   6000, "Donostia"),
    ("BBK Mendizabala",       -2.670, 42.846,  25000, "Vitoria-Gasteiz"),
    ("Iruñea Rock",           -1.644, 42.812,  15000, "Iruñea"),
    ("Deabruak Teloia",       -2.464, 43.206,   4500, "Eibar"),
    ("Durangoko Azoka Live",  -2.634, 43.172,   9000, "Durango"),
    ("Jaialdia Getxo",        -3.010, 43.355,  12000, "Getxo"),
]


def day11_festivales_geojson(request):
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"name": name, "attendance": att, "city": city},
        }
        for name, lng, lat, att, city in _FESTIVALES
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features})


# ------------------------------------------------------------------
# Día 20 — Hexágonos: cuadrícula sobre el bbox de Euskal Herria y
# cuento de recargas EV por celda. Sin H3 (no está en requirements):
# usamos una cuadrícula hexagonal regular aproximada en lng/lat, suficiente
# para la demo visual del día "Hexagons".
# ------------------------------------------------------------------

def _hex_centers(bbox, step_lng=0.08):
    """Genera centros de una cuadrícula hexagonal (flat-top) sobre bbox."""
    w, s, e, n = bbox
    step_lat = step_lng * (3 ** 0.5) / 2
    row = 0
    lat = s
    while lat <= n:
        offset = (step_lng / 2) if (row % 2) else 0
        lng = w + offset
        while lng <= e:
            yield (lng, lat)
            lng += step_lng
        lat += step_lat
        row += 1


def _hex_polygon(cx, cy, r):
    import math
    coords = []
    for i in range(6):
        ang = math.radians(60 * i)  # flat-top
        coords.append([cx + r * math.cos(ang), cy + r * math.sin(ang) * 0.866])
    coords.append(coords[0])
    return coords


def day20_hexagons_geojson(request):
    bbox = (-3.45, 42.4, -0.3, 43.65)
    step_lng = 0.08
    r = step_lng / 2.0

    features = []
    qs = ChargingStation.objects.filter(geom__isnull=False).only("geom")
    # Precargamos coords en memoria (12k puntos aceptable).
    ev_coords = [(cs.geom.x, cs.geom.y) for cs in qs.iterator(chunk_size=2000)]

    for cx, cy in _hex_centers(bbox, step_lng=step_lng):
        poly_coords = _hex_polygon(cx, cy, r)
        # Contaje bbox rápido (no hay que ser precisos — es un día artístico).
        xs = [p[0] for p in poly_coords]
        ys = [p[1] for p in poly_coords]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        count = sum(1 for (x, y) in ev_coords if xmin <= x <= xmax and ymin <= y <= ymax)
        if count == 0:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [poly_coords]},
            "properties": {"count": count},
        })

    return JsonResponse({"type": "FeatureCollection", "features": features})
