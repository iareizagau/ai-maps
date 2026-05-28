"""HTMX views for mubil. PROPUESTA.md §3, §6."""

import json

from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .advisor import services as advisor_services
from .advisor.api import _quote_to_out
from .ask import services as ask_services
from .models import Vehicle


def index(request):
    """Landing of the mubil sub-domain — 4 module cards."""
    return render(request, 'mubil/index.html')


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
        payload = {
            'cp': request.POST['cp'].strip(),
            'km_year': int(request.POST['km_year']),
            'vehicle_current_id': int(request.POST['vehicle_current_id']),
            'vehicle_target_id': int(request.POST['vehicle_target_id']),
            'years_horizon': int(request.POST.get('years_horizon', 10)),
            'night_charging': request.POST.get('night_charging') == 'on',
            'subvencion_eur': int(request.POST.get('subvencion_eur', 0) or 0),
        }
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
    }
    return render(request, 'mubil/_advisor_result.html', context)


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
    return render(request, 'mubil/route.html')


def plan_page(request):
    """Demand heatmap (MOCK). PROPUESTA.md §3.4."""
    return render(request, 'mubil/plan.html')
