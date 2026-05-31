"""HTMX views for mubil. PROPUESTA.md §3, §6."""

import json

from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .advisor import services as advisor_services
from .advisor.api import _quote_to_out
from .ask import services as ask_services
from .models import (
    ChargingStation,
    DemandHex,
    EVRoutePlan,
    FuelStation,
    MobilityDocument,
    Vehicle,
)
from .plan import services as plan_services
from .route import services as route_services


def index(request):
    """Public landing of the mubil sub-domain (PROPUESTA.md §6 deliverables).

    Stats below are read live from the production DB — counts are cheap (≤600
    rows on the heaviest tables) so the page stays sub-50 ms without caching.
    Numbers feed the headline "datos reales en producción" claim of the
    submission.
    """
    from apps.mubil.data import pvpc_ingest

    embedded_docs = MobilityDocument.objects.filter(embedding__isnull=False).count()
    stats = {
        'vehicles': Vehicle.objects.count(),
        'charging_stations': ChargingStation.objects.count(),
        'fuel_stations': FuelStation.objects.count(),
        'docs_indexed': MobilityDocument.objects.count(),
        'docs_embedded': embedded_docs,
        'demand_hexes': DemandHex.objects.count(),
        'route_demos': EVRoutePlan.objects.count(),
    }

    # Live PVPC for the hero card. Falls back to the static constant if the
    # table is empty (e.g. fresh deploy before the first cron tick).
    pvpc_blended = pvpc_ingest.current_price_eur_kwh(night_charging=False)
    pvpc_valley = pvpc_ingest.current_price_eur_kwh(night_charging=True)

    # Highest-scoring DemandHex — backs the third hero card.
    top_hex = DemandHex.objects.order_by('-score_now').first()

    hero_live = {
        'pvpc_eur_kwh': float(pvpc_blended),
        'pvpc_valley_eur_kwh': float(pvpc_valley),
        'top_hex_slug': top_hex.h3_index if top_hex else None,
        'top_hex_score': float(top_hex.score_now) if top_hex else None,
    }

    tech_tags = [
        'Django 6', 'PostGIS', 'pgvector', 'TimescaleDB', 'Django Ninja',
        'HTMX', 'Alpine.js', 'Tailwind', 'Cotton', 'Leaflet', 'ECharts',
        'Gemini', 'Celery', 'Docker', 'Coolify',
    ]
    return render(request, 'mubil/index.html', {
        'stats': stats,
        'hero_live': hero_live,
        'tech_tags': tech_tags,
    })


def advisor_page(request):
    """TCO advisor form (MUST). PROPUESTA.md §3.1."""
    vehicles = list(Vehicle.objects.all().order_by('propulsion', 'make', 'model'))
    ice_vehicles = [v for v in vehicles if v.propulsion in (
        Vehicle.Propulsion.ICE, Vehicle.Propulsion.DIESEL, Vehicle.Propulsion.HEV,
    )]
    ev_vehicles = [v for v in vehicles if v.propulsion in (
        Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV,
    )]
    # Defaults to drive the live demo: Golf TDI → Kia Niro EV
    default_current = next(
        (v for v in ice_vehicles if 'Golf' in v.model), ice_vehicles[0] if ice_vehicles else None
    )
    default_target = next(
        (v for v in ev_vehicles if 'Niro' in v.model), ev_vehicles[0] if ev_vehicles else None
    )
    return render(request, 'mubil/advisor.html', {
        'ice_vehicles': ice_vehicles,
        'ev_vehicles': ev_vehicles,
        'default_current_id': default_current.id if default_current else None,
        'default_target_id': default_target.id if default_target else None,
    })


@require_http_methods(["POST"])
def advisor_quote(request):
    """HTMX endpoint that returns the result partial.

    Pure orchestration over `advisor.services.calculate_tco_quote`. JSON API for
    the same calculation lives in `advisor/api.py` (`POST /api/v1/advisor/quote`).
    """
    try:
        payload = _parse_advisor_payload(request.POST)
    except (KeyError, ValueError) as e:
        return HttpResponseBadRequest(f"Datos del formulario inválidos: {e}")

    try:
        quote = advisor_services.calculate_tco_quote(**payload)
    except Vehicle.DoesNotExist:
        return HttpResponseBadRequest("Vehículo no encontrado")
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    out = _quote_to_out(quote)
    context = {
        'q': out,
        'q_json': json.dumps(out, default=str),
        'night_charging': payload['night_charging'],
    }
    return render(request, 'mubil/_advisor_result.html', context)


def _parse_advisor_payload(src):
    """Normaliza un QueryDict (POST o GET) al kwargs de calculate_tco_quote."""

    def _opt_float(key):
        raw = src.get(key)
        if raw is None or not str(raw).strip():
            return None
        return float(str(raw).replace(',', '.'))

    def _opt_int(key):
        raw = src.get(key)
        if raw is None or not str(raw).strip():
            return None
        return int(raw)

    night = src.get('night_charging')
    night_charging = (
        night in ('on', '1', 'true', 'True', True)
        if night is not None
        else False
    )

    return {
        'cp': src['cp'].strip(),
        'km_year': int(src['km_year']),
        'vehicle_current_id': int(src['vehicle_current_id']),
        'vehicle_target_id': int(src['vehicle_target_id']),
        'years_horizon': int(src.get('years_horizon', 10)),
        'night_charging': night_charging,
        'subvencion_eur': int(src.get('subvencion_eur', 0) or 0),
        'motorway_pct': _opt_float('motorway_pct'),
        'nacional_pct': _opt_float('nacional_pct'),
        'profile': (src.get('profile') or 'particular').strip(),
        'scrapping': src.get('scrapping') in ('on', '1', 'true', 'True'),
        'wallbox_state': (src.get('wallbox_state') or 'installed').strip(),
        'home_pct': _opt_int('home_pct'),
        'work_pct': _opt_int('work_pct'),
        'public_ac_pct': _opt_int('public_ac_pct'),
        'public_dc_pct': _opt_int('public_dc_pct'),
        'subvencion_override_eur': _opt_int('subvencion_override_eur'),
        'vehicle_current_price_override_eur': _opt_int('vehicle_current_price_override_eur'),
        'vehicle_target_price_override_eur': _opt_int('vehicle_target_price_override_eur'),
    }


def advisor_pdf(request):
    """Print-friendly advisor result for client-side PDF export (html2pdf.js).

    Recomputes the quote from query params instead of relying on session/POST
    state — keeps the URL shareable (jurors can paste it) and idempotent.
    """
    try:
        payload = _parse_advisor_payload(request.GET)
    except (KeyError, ValueError) as e:
        return HttpResponseBadRequest(f"Datos inválidos: {e}")

    try:
        quote = advisor_services.calculate_tco_quote(**payload)
    except Vehicle.DoesNotExist:
        return HttpResponseBadRequest("Vehículo no encontrado")
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    out = _quote_to_out(quote)
    savings_total = out['total_cost_current'] - out['total_cost_target']
    return render(request, 'mubil/advisor_pdf.html', {
        'q': out,
        'q_json': json.dumps(out, default=str),
        'savings_total': savings_total,
        'savings_per_month': savings_total / (out['years_horizon'] * 12),
    })


def ask_page(request):
    """Q&A console with Gemini + RAG (MUST). PROPUESTA.md §3.2."""
    return render(request, 'mubil/ask.html', {
        'suggested': ask_services.SUGGESTED_PROMPTS,
    })


@require_http_methods(["POST"])
def ask_query(request):
    """HTMX endpoint — returns the answer + sources partial."""
    query = (request.POST.get('q') or '').strip()
    if not query:
        return HttpResponseBadRequest("Falta la pregunta.")
    try:
        k = int(request.POST.get('k', 8))
    except ValueError:
        k = 8
    municipality = (request.POST.get('municipality_naia') or '').strip() or None

    try:
        result = ask_services.answer(query=query, k=k, municipality_naia=municipality)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    return render(request, 'mubil/_ask_result.html', {
        'query': query,
        'answer': result.to_out(),
    })


def route_page(request):
    """EV-aware route planner (MOCK). PROPUESTA.md §3.3."""
    ev_vehicles = list(Vehicle.objects.filter(
        propulsion__in=(Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV),
    ).order_by('make', 'model'))
    default_vehicle = next(
        (v for v in ev_vehicles if 'Niro' in v.model),
        ev_vehicles[0] if ev_vehicles else None,
    )
    return render(request, 'mubil/route.html', {
        'demos': route_services.list_demos(),
        'default_slug': route_services.ROUTE_DEMOS[0]['slug'],
        'ev_vehicles': ev_vehicles,
        'default_vehicle_id': default_vehicle.id if default_vehicle else None,
    })


@require_http_methods(["GET", "POST"])
def route_plan(request):
    """HTMX endpoint — returns the route plan partial.

    Accepts both GET (used for the page's initial preload via
    ``hx-trigger="load"``) and POST (used by form submission / change).
    """
    src = request.POST if request.method == "POST" else request.GET
    slug = (src.get('slug') or '').strip()
    if not slug:
        slug = route_services.ROUTE_DEMOS[0]['slug']
    try:
        vehicle_id_raw = src.get('vehicle_id') or ''
        vehicle_id = int(vehicle_id_raw) if vehicle_id_raw else None
        soc_start = float(src.get('soc_start', 80))
    except ValueError as e:
        return HttpResponseBadRequest(f"Datos del formulario inválidos: {e}")

    try:
        result = route_services.plan(
            slug=slug, vehicle_id=vehicle_id, soc_start_pct=soc_start,
        )
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    out = result.to_dict()
    return render(request, 'mubil/_route_result.html', {
        'r': out,
        'r_json': json.dumps(out),
    })


def plan_page(request):
    """Demand heatmap (MOCK). PROPUESTA.md §3.4."""
    try:
        horizon = int(request.GET.get('horizon', 3))
    except ValueError:
        horizon = 3
    if horizon not in (1, 3, 5):
        horizon = 3
    return render(request, 'mubil/plan.html', {
        'horizon': horizon,
        'top_locations': plan_services.top_locations(horizon=horizon, limit=10),
        'hex_count': DemandHex.objects.count(),
    })
