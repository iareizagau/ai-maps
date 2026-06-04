"""`advisor` sub-router — TCO eléctrico vs combustión (MUST, demo en vivo).

Endpoints (PROPUESTA.md §3.1):
  GET  /vehicles?q=&propulsion=  → autocompletar catálogo
  POST /quote                    → AdvisorQuoteIn → AdvisorQuoteOut
  GET  /cp/{cp}                  → centroide CP (helper para el formulario)
  POST /route-commute            → RouteCommuteIn → RouteCommuteOut
"""

from typing import List, Optional

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, FloatField, Q, Value, When
from django.db.models.functions import Greatest
from ninja import Query, Router
from ninja.errors import HttpError

from apps.mubil.data import cp_centroids
from apps.mubil.models import Vehicle

from . import services
from .grouping import extract_model_base, group_by_model_base
from .schemas import (
    AdvisorQuoteIn,
    AdvisorQuoteOut,
    ChargerOut,
    CostBreakdownOut,
    RecommendOut,
    VehicleSummary,
    RouteCommuteIn,
    RouteCommuteOut,
)

# Sentinel para el seed `ICE genérico medio` (migración 0012). Path C lo usa
# como `vehicle_current_id` cuando el usuario elige el modo "recomiéndame".
ICE_GENERIC_LOOKUP = dict(
    idae_id__isnull=True,
    make="Genérico",
    model="Coche ICE medio",
    variant="",
    year=2020,
)

# Buckets de tamaño calibrados con el catálogo IDAE 2026-06 (ver
# CLAUDE memory + dist mtma_kg p25/50/75 = 2158/2480/2750 en BEV M1).
# Solo tenemos `category` (M1/N1) y `mtma_kg` — no hay `segment` poblado,
# así que `SUV` vs `berlina` queda fuera del MVP.
SIZE_FILTERS = {
    "small": dict(category="M1", mtma_kg__lte=2000),
    "mid":   dict(category="M1", mtma_kg__gt=2000, mtma_kg__lte=2400),
    "large": dict(category="M1", mtma_kg__gt=2400),
    "van":   dict(category="N1"),
}

# Cubos de autonomía pedidos por el usuario en sesión de diseño:
# baja <350 / media 350-450 / alta >=450. La distribución actual del
# catálogo es 64 % / 14 % / 22 % — suficiente densidad en los 3 buckets.
RANGE_FILTERS = {
    "low":  dict(range_wltp_km__lt=350),
    "mid":  dict(range_wltp_km__gte=350, range_wltp_km__lt=450),
    "high": dict(range_wltp_km__gte=450),
}

router = Router()


# ============ helpers ============


def _vehicle_to_summary(v: Vehicle) -> dict:
    return {
        "id": v.id,
        "make": v.make,
        "model": v.model,
        "year": v.year,
        "propulsion": v.propulsion,
        "category": v.category or None,
        "price_eur": v.price_eur,
        "price_source": v.price_source,
        "dgt_label": v.dgt_label or "C",
        "range_wltp_km": v.range_wltp_km,
        "consumption_kwh_100km": v.consumption_kwh_100km,
        "consumption_l_100km": v.consumption_l_100km,
        "variant_count": 1,
        "consumption_min": None,
        "consumption_max": None,
    }


def _grouped_summary(group: dict) -> dict:
    """Convierte la salida de `group_by_model_base` en el shape de
    VehicleSummary. El `id` y los specs son los del representante mediano;
    el `make` se muestra normalizado ("Tesla" en vez de "TESLA") y el
    `model` se muestra como base ("Vito") en vez de la variante larga.
    El frontend usa `variant_count > 1` para mostrar el badge "N variantes".
    """
    out = _vehicle_to_summary(group["representative"])
    out["make"] = group["make_display"] or out["make"]
    out["model"] = group["model_base"] or out["model"]
    out["variant_count"] = group["variant_count"]
    out["consumption_min"] = group["consumption_min"]
    out["consumption_max"] = group["consumption_max"]
    return out


def _breakdown_to_out(b) -> dict:
    return {
        "energy": b.energy,
        "maintenance": b.maintenance,
        "insurance": b.insurance,
        "taxes": b.taxes,
        "total": b.total,
    }


def _quote_to_out(quote: services.TCOQuote) -> dict:
    bd_c = _breakdown_to_out(quote.breakdown_current)
    bd_t = _breakdown_to_out(quote.breakdown_target)
    saved = (quote.co2_kg_year_current - quote.co2_kg_year_target).quantize(
        quote.co2_kg_year_current
    )
    chargers = [
        {
            "id": c.id,
            "operator": c.operator or "",
            "power_kw": c.power_kw,
            "latitude": c.geom.y,
            "longitude": c.geom.x,
            "address": c.address or "",
            "distance_km": (c.distance.km if getattr(c, "distance", None) else None),
        }
        for c in quote.nearby_chargers
    ]
    return {
        "cp": quote.cp,
        "cp_name": quote.cp_name,
        "km_year": quote.km_year,
        "years_horizon": quote.years_horizon,
        "vehicle_current": _vehicle_to_summary(quote.vehicle_current),
        "vehicle_target": _vehicle_to_summary(quote.vehicle_target),
        "breakdown_current": bd_c,
        "breakdown_target": bd_t,
        "total_cost_current": bd_c["total"],
        "total_cost_target": bd_t["total"],
        "co2_kg_year_current": quote.co2_kg_year_current,
        "co2_kg_year_target": quote.co2_kg_year_target,
        "co2_saved_kg_year": saved,
        "payback_years": quote.payback_years,
        "subvencion_eur": quote.subvencion_eur,
        "nearby_chargers": chargers,
        "motorway_pct": quote.motorway_pct,
        "nacional_pct": quote.nacional_pct,
        "urban_pct": quote.urban_pct,
        "charging_mix": quote.charging_mix.to_out() if quote.charging_mix else None,
        "weighted_charging_eur_kwh": quote.weighted_charging_eur_kwh,
        "incentives": quote.incentives.to_out() if quote.incentives else None,
        "wallbox_capex_eur": quote.wallbox_capex_eur,
        "purchase_mode": getattr(quote, "purchase_mode", "switch"),
        "current_age_years": getattr(quote, "current_age_years", None),
        "current_residual_value_eur": getattr(quote, "current_residual_value_eur", None),
        "operational_savings_eur": getattr(quote, "operational_savings_eur", None),
        "purchase_savings_eur": getattr(quote, "purchase_savings_eur", None),
        "total_net_savings_eur": getattr(quote, "total_net_savings_eur", None),
    }


# ============ endpoints ============


@router.get("/health")
def health(request):
    return {"status": "ok", "module": "advisor"}


@router.get("/vehicles", response=List[VehicleSummary])
def list_vehicles(
    request,
    q: Optional[str] = Query(None),
    propulsion: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Catálogo Vehicle. Filtra por texto libre `q` (tolerante a typos vía
    trigram, usa el índice GIN `vehicle_text_trgm` de la migración 0005) y
    propulsión."""
    qs = Vehicle.objects.all()
    if propulsion:
        if propulsion.upper() == "ICE_ALL":
            qs = qs.filter(propulsion__in=["ICE", "DIESEL", "HEV"])
        elif propulsion.upper() == "EV_ALL":
            qs = qs.filter(propulsion__in=["BEV", "PHEV"])
        else:
            qs = qs.filter(propulsion=propulsion.upper())
    if q:
        q = q.strip()
        # Umbral bajo (0.08) porque las queries cortas tipo "mer" o "gol"
        # tienen similitud trigram baja por construcción aunque el usuario
        # vaya bien encaminado. Subirlo descarta resultados válidos en
        # autocomplete de 2-3 chars; ya lo afinaré con dataset real.
        # Boost +1.0 cuando la query es prefijo de make/model: en autocomplete
        # el usuario casi siempre escribe el principio del nombre, no el
        # medio. Sin esto, "gol" rankea GoldenLion antes que Golf, "mer"
        # rankea Mercury antes que Mercedes — pierdes el caso común.
        qs = qs.annotate(
            sim=Greatest(
                TrigramSimilarity("make", q),
                TrigramSimilarity("model", q),
            ),
            prefix_boost=Case(
                When(Q(make__istartswith=q) | Q(model__istartswith=q), then=Value(1.0)),
                default=Value(0.0),
                output_field=FloatField(),
            ),
        ).filter(sim__gt=0.08).order_by("-prefix_boost", "-sim", "make", "model")
    else:
        qs = qs.order_by("make", "model")

    # Cast wide net (limit×8) y agrupamos por (make, model_base) para
    # que el autocomplete devuelva un card por modelo, no por variante
    # IDAE. Sin esto, una búsqueda "vito" devuelve 8 Mercedes-Benz Vito
    # casi idénticos (decisión fatiga). Ver `advisor/grouping.py`.
    raw = list(qs[: limit * 8])
    grouped = group_by_model_base(raw, propulsion_hint=propulsion)
    return [_grouped_summary(g) for g in grouped[:limit]]


@router.get("/recommend", response={200: RecommendOut, 404: dict})
def recommend_vehicles(
    request,
    size: Optional[str] = Query(None, description="small | mid | large | van"),
    range_bucket: Optional[str] = Query(None, description="low | mid | high"),
    price_min: Optional[int] = Query(None, ge=0),
    price_max: Optional[int] = Query(None, ge=0),
    limit: int = Query(6, ge=1, le=20),
):
    """Path C del Step 1 del advisor: el usuario filtra por tamaño / autonomía
    / presupuesto y devolvemos los `limit` BEVs que mejor encajan, junto al id
    del seed `ICE genérico medio` para usar como `vehicle_current_id` en el
    quote posterior.

    Orden: más autonomía primero, precio ascendente como desempate. Es lo que
    el usuario espera al pedir "recomiéndame un eléctrico": a igualdad de
    range, el más barato gana.
    """
    try:
        ice_generic_id = Vehicle.objects.get(**ICE_GENERIC_LOOKUP).id
    except Vehicle.DoesNotExist:
        return 404, {"message": "Seed 'ICE genérico medio' no existe. Aplica migración mubil 0012."}

    qs = Vehicle.objects.filter(propulsion="BEV")
    if size:
        flt = SIZE_FILTERS.get(size.lower())
        if flt is None:
            raise HttpError(400, f"size inválido: {size}. Opciones: {list(SIZE_FILTERS)}")
        qs = qs.filter(**flt)
    if range_bucket:
        flt = RANGE_FILTERS.get(range_bucket.lower())
        if flt is None:
            raise HttpError(400, f"range_bucket inválido: {range_bucket}. Opciones: {list(RANGE_FILTERS)}")
        qs = qs.filter(**flt)
    if price_min is not None:
        qs = qs.filter(price_eur__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price_eur__lte=price_max)

    # Más range gana; a igualdad, precio asc.
    qs = qs.exclude(range_wltp_km__isnull=True).order_by("-range_wltp_km", "price_eur", "make", "model")
    raw = list(qs[: limit * 8])
    grouped = group_by_model_base(raw, propulsion_hint="BEV")
    candidates = [_grouped_summary(g) for g in grouped[:limit]]
    return 200, {"ice_generic_id": ice_generic_id, "candidates": candidates}


@router.get("/vehicles/alternatives", response=List[VehicleSummary])
def list_alternatives(
    request,
    vehicle_id: int = Query(..., description="ID del Vehicle de referencia"),
    limit: int = Query(3, ge=1, le=10),
):
    """Alternativas al EV que el usuario acaba de elegir, para el sidebar
    comparador del wizard. Mismo bucket de tamaño + autonomía, precio
    en ±20 %, excluyendo el propio modelo base. Agrupado para evitar
    devolver 3 variantes del mismo modelo.
    """
    try:
        ref = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        raise HttpError(404, f"Vehicle {vehicle_id} no existe")

    if ref.propulsion != "BEV":
        # Sólo damos alternativas a BEVs (el comparador está pensado para
        # ayudar al usuario a explorar EVs; comparar ICE entre sí no aporta).
        return []

    ref_base = extract_model_base(ref.model)
    qs = Vehicle.objects.filter(propulsion="BEV").exclude(id=ref.id)

    if ref.category:
        qs = qs.filter(category=ref.category)
    if ref.range_wltp_km:
        qs = qs.filter(
            range_wltp_km__gte=int(ref.range_wltp_km * 0.85),
            range_wltp_km__lte=int(ref.range_wltp_km * 1.15),
        )
    if ref.price_eur:
        qs = qs.filter(
            price_eur__gte=int(ref.price_eur * 0.8),
            price_eur__lte=int(ref.price_eur * 1.2),
        )

    qs = qs.order_by("-range_wltp_km", "price_eur", "make", "model")
    raw = [v for v in qs[: limit * 10] if extract_model_base(v.model) != ref_base]
    grouped = group_by_model_base(raw, propulsion_hint="BEV")
    return [_grouped_summary(g) for g in grouped[:limit]]


@router.get("/cp/{cp}")
def get_cp_centroid(request, cp: str):
    """Devuelve el centroide hardcoded de un CP de Gipuzkoa (o vecinos)."""
    centroid = cp_centroids.lookup(cp)
    if centroid is None:
        raise HttpError(404, f"CP {cp} no está en el set demo. Ver cp_centroids.py")
    lat, lon, name = centroid
    return {"cp": cp, "name": name, "latitude": lat, "longitude": lon}


@router.post("/quote", response={200: AdvisorQuoteOut, 400: dict, 404: dict})
def post_quote(request, payload: AdvisorQuoteIn):
    """Calcula la comparativa TCO."""
    try:
        quote = services.calculate_tco_quote(
            cp=payload.cp,
            km_year=payload.km_year,
            vehicle_current_id=payload.vehicle_current_id,
            vehicle_target_id=payload.vehicle_target_id,
            years_horizon=payload.years_horizon,
            night_charging=payload.night_charging,
            subvencion_eur=payload.subvencion_eur,
            motorway_pct=payload.motorway_pct,
            nacional_pct=payload.nacional_pct,
            profile=payload.profile,
            scrapping=payload.scrapping,
            wallbox_state=payload.wallbox_state,
            home_pct=payload.home_pct,
            work_pct=payload.work_pct,
            public_ac_pct=payload.public_ac_pct,
            public_dc_pct=payload.public_dc_pct,
            subvencion_override_eur=payload.subvencion_override_eur,
            vehicle_current_price_override_eur=payload.vehicle_current_price_override_eur,
            purchase_mode=payload.purchase_mode or "switch",
            current_age_years=payload.current_age_years,
            vehicle_target_price_override_eur=payload.vehicle_target_price_override_eur,
        )
    except Vehicle.DoesNotExist:
        return 404, {"message": "Vehículo no encontrado"}
    except ValueError as e:
        return 400, {"message": str(e)}
    return 200, _quote_to_out(quote)


@router.post("/route-commute", response={200: RouteCommuteOut, 400: dict})
def post_route_commute(request, payload: RouteCommuteIn):
    """Calcula la ruta óptima de pgRouting entre origen y destino."""
    try:
        res = services.get_commute_route(
            start_lng=payload.start_lng,
            start_lat=payload.start_lat,
            end_lng=payload.end_lng,
            end_lat=payload.end_lat
        )
        return 200, res
    except Exception as e:
        return 400, {"message": str(e)}
