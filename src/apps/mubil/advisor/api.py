"""`advisor` sub-router — TCO eléctrico vs combustión (MUST, demo en vivo).

Endpoints (PROPUESTA.md §3.1):
  GET  /vehicles?q=&propulsion=  → autocompletar catálogo
  POST /quote                    → AdvisorQuoteIn → AdvisorQuoteOut
  GET  /cp/{cp}                  → centroide CP (helper para el formulario)
  POST /route-commute            → RouteCommuteIn → RouteCommuteOut
"""

from typing import List, Optional

from ninja import Query, Router
from ninja.errors import HttpError

from apps.mubil.data import cp_centroids
from apps.mubil.models import Vehicle

from . import services
from .schemas import (
    AdvisorQuoteIn,
    AdvisorQuoteOut,
    ChargerOut,
    CostBreakdownOut,
    VehicleSummary,
    RouteCommuteIn,
    RouteCommuteOut,
)

router = Router()


# ============ helpers ============


def _vehicle_to_summary(v: Vehicle) -> dict:
    return {
        "id": v.id,
        "make": v.make,
        "model": v.model,
        "year": v.year,
        "propulsion": v.propulsion,
        "price_eur": v.price_eur,
        "price_source": v.price_source,
        "dgt_label": v.dgt_label or "C",
        "range_wltp_km": v.range_wltp_km,
        "consumption_kwh_100km": v.consumption_kwh_100km,
        "consumption_l_100km": v.consumption_l_100km,
    }


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
    """Catálogo Vehicle. Filtra por texto libre `q` y propulsión."""
    qs = Vehicle.objects.all()
    if q:
        # Permite buscar por make o model
        qs = qs.filter(make__icontains=q) | qs.filter(model__icontains=q)
    if propulsion:
        if propulsion.upper() == "ICE_ALL":
            qs = qs.filter(propulsion__in=["ICE", "DIESEL", "HEV"])
        elif propulsion.upper() == "EV_ALL":
            qs = qs.filter(propulsion__in=["BEV", "PHEV"])
        else:
            qs = qs.filter(propulsion=propulsion.upper())
    return [_vehicle_to_summary(v) for v in qs.order_by("make", "model")[:limit]]


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
