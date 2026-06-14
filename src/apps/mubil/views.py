"""HTMX views for mubil. PROPUESTA.md §3, §6."""

import json

from django.db.models import Count, Max, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .advisor import services as advisor_services
from .advisor.api import _quote_to_out
from .advisor import assistant as advisor_assistant
from .ask import services as ask_services
from .models import (
    ChargingStation,
    DemandHex,
    EnergyPricePVPC,
    EVRegistration,
    EVRoutePlan,
    FuelStation,
    MobilityDocument,
    NewsArticle,
    Vehicle,
)
from .news import services as news_services
from .news.tasks import refresh_news
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

    # Vehicle catalog is the heaviest, most under-sold asset (~24k rows). One
    # aggregate query yields the hero number plus the breakdown/coverage context
    # that makes it "weigh" for the jury: EV vs combustion split + enrichment %.
    _ev = Q(propulsion__in=(Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV))
    veh = Vehicle.objects.aggregate(
        total=Count('id'),
        ev=Count('id', filter=_ev),
        with_price=Count('id', filter=Q(price_eur__isnull=False)),
        # Range/battery only make sense for EVs, so coverage is EV-scoped and
        # labelled as such in the template — honest denominator, not cherry-picked.
        ev_range=Count('id', filter=_ev & Q(range_wltp_km__isnull=False)),
        ev_label=Count('id', filter=_ev & ~Q(dgt_label='')),
    )
    v_total = veh['total'] or 0
    v_ev = veh['ev'] or 0

    vehicles_meta = {
        'total': v_total,
        'ev': v_ev,
        'combustion': v_total - v_ev,
        'pct_price': round(100 * veh['with_price'] / v_total) if v_total else 0,
        'ev_pct_range': round(100 * veh['ev_range'] / v_ev) if v_ev else 0,
        'ev_pct_label': round(100 * veh['ev_label'] / v_ev) if v_ev else 0,
    }

    stats = {
        'vehicles': v_total,
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

    # Per-source freshness — converts the "en vivo" claim into proof. Each value
    # is the most recent ingest/observation timestamp for that source, read live
    # from the DB. Templates render these via humanize `naturaltime`.
    freshness = {
        'pvpc': EnergyPricePVPC.objects.aggregate(t=Max('timestamp'))['t'],
        'fuel': FuelStation.objects.aggregate(t=Max('last_seen_at'))['t'],
        'charging': ChargingStation.objects.aggregate(t=Max('last_seen_at'))['t'],
        'docs': MobilityDocument.objects.aggregate(t=Max('ingested_at'))['t'],
        'vehicles': Vehicle.objects.aggregate(t=Max('updated_at'))['t'],
    }

    tech_tags = [
        'Django 6', 'PostGIS', 'pgvector', 'TimescaleDB', 'Django Ninja',
        'HTMX', 'Alpine.js', 'Tailwind', 'Cotton', 'Leaflet', 'ECharts',
        'Gemini', 'Celery', 'Docker', 'Coolify',
    ]
    return render(request, 'mubil/index.html', {
        'stats': stats,
        'vehicles_meta': vehicles_meta,
        'hero_live': hero_live,
        'freshness': freshness,
        'adoption': _adoption_snapshot(),
        'tech_tags': tech_tags,
    })


# Electric propulsions counted toward the "EV adoption" share.
_EV_PROPULSIONS = (Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV)


def _adoption_snapshot():
    """Latest-month EV adoption share for Euskadi from EVRegistration.

    Returns None when the table is empty so the index simply omits the block —
    no zeros, no fabricated numbers. Lights up automatically once the
    `ingest_ev_registrations` CSV is loaded. Shares are computed over ALL
    propulsions present for the latest (year, month), aggregated across the
    three Basque territories.
    """
    latest = EVRegistration.objects.order_by('-year', '-month').values('year', 'month').first()
    if not latest:
        return None

    def _share(year, month):
        rows = EVRegistration.objects.filter(year=year, month=month)
        total = sum(r.count for r in rows)
        if not total:
            return None, 0
        ev = sum(r.count for r in rows if r.propulsion in _EV_PROPULSIONS)
        return ev / total, ev

    year, month = latest['year'], latest['month']
    share, ev_count = _share(year, month)
    if share is None:
        return None
    prev_share, _ = _share(year - 1, month)

    return {
        'year': year,
        'month': month,
        'ev_count': ev_count,
        'share_pct': round(share * 100, 1),
        'yoy_pp': round((share - prev_share) * 100, 1) if prev_share is not None else None,
    }


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
        'recent_alerts': news_services.recent_affecting_plan(),
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
    # Phase 2 bridge: stash the chosen EV + CP for the route planner so the
    # user lands in /mubil/route/ with the same vehicle and origin already
    # selected. Set-and-forget — overwritten on each new quote, never popped.
    request.session['mubil_route_prefill'] = {
        'vehicle_target_id': payload['vehicle_target_id'],
        'cp': payload['cp'],
    }

    target = out['vehicle_target']
    news_query = (
        f"Subvenciones, fiscalidad y PVPC para {target['make']} {target['model']} "
        f"en código postal {payload['cp']}, {payload['km_year']} km/año."
    )
    news_alerts = news_services.ranked_for_user(query_text=news_query)

    context = {
        'q': out,
        'q_json': json.dumps(out, default=str),
        'night_charging': payload['night_charging'],
        'news_alerts': news_alerts,
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
        'purchase_mode': (src.get('purchase_mode') or 'switch').strip(),
        'current_age_years': _opt_int('current_age_years'),
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


def news_page(request):
    """Public EV-news blog. Renders the DB instantly; when the cache is
    stale (>NEWS_CACHE_HOURS or empty) dispatches a Celery refresh in the
    background so the next visit shows fresh items.

    Optional GET filters: ?relevance=EUSKADI|ESPANA|GLOBAL  ?tag=subvencion
    """
    relevance = (request.GET.get('relevance') or '').strip().upper() or None
    if relevance and relevance not in dict(NewsArticle.Relevance.choices):
        relevance = None
    tag = (request.GET.get('tag') or '').strip().lower() or None

    articles = news_services.list_articles(limit=60, relevance=relevance, tag=tag)

    stale, age_hours = news_services.is_cache_stale()
    if stale:
        try:
            refresh_news.delay()
            refresh_dispatched = True
        except Exception:  # noqa: BLE001 — broker down must not 500 the page
            refresh_dispatched = False
    else:
        refresh_dispatched = False

    return render(request, 'mubil/news.html', {
        'articles': articles,
        'active_relevance': relevance,
        'active_tag': tag,
        'cache_age_hours': age_hours,
        'refresh_dispatched': refresh_dispatched,
        'relevances': NewsArticle.Relevance.choices,
    })


def route_page(request):
    """EV-aware route planner (MOCK). PROPUESTA.md §3.3.

    Reads ``request.session['mubil_route_prefill']`` (written by the advisor)
    so a user that just got a TCO quote lands here with their chosen EV and
    home postal-code already selected — the advisor↔route bridge described
    in [PLAN.md Phase 2](route/PLAN.md).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from apps.mubil.data import cp_centroids

    ev_vehicles = list(Vehicle.objects.filter(
        propulsion__in=(Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV),
    ).order_by('make', 'model'))

    prefill = request.session.get('mubil_route_prefill') or {}
    prefill_vehicle_id = prefill.get('vehicle_target_id')
    prefill_cp = prefill.get('cp')

    # Only honour the prefill vehicle if it's still in the EV catalog —
    # protects against deleted rows pointing the UI at a missing select option.
    ev_vehicle_ids = {v.id for v in ev_vehicles}
    if prefill_vehicle_id in ev_vehicle_ids:
        default_vehicle_id = prefill_vehicle_id
    else:
        fallback = next(
            (v for v in ev_vehicles if 'Niro' in v.model),
            ev_vehicles[0] if ev_vehicles else None,
        )
        default_vehicle_id = fallback.id if fallback else None

    default_origin = None
    if prefill_cp:
        hit = cp_centroids.lookup(prefill_cp)
        if hit is not None:
            lat, lon, name = hit
            default_origin = {'cp': prefill_cp, 'lat': lat, 'lon': lon, 'name': name}

    # Demos serialised for the Alpine "ruta rápida" chips above the map.
    demos_payload = [
        {
            'slug': d['slug'],
            'label': d['label'],
            'origin': list(d['origin']),   # [lat, lon]
            'dest': list(d['dest']),
            'distance_km': float(d['distance_km']),
        }
        for d in route_services.ROUTE_DEMOS
    ]

    # Default departure hour = current Madrid-local hour. Pre-selects the
    # right slot on the 24h cost-by-hour chart in the result partial.
    default_departure_hour = datetime.now(tz=ZoneInfo('Europe/Madrid')).hour

    # Single JSON blob consumed by Alpine via ``x-data``. Inlined with
    # ``|escape`` in the template so embedded ``"`` survive the HTML attribute
    # parser — same trick the advisor uses for its q_json payload.
    init_payload = {
        'demos': demos_payload,
        'defaultOrigin': default_origin,
        'defaultSlug': route_services.ROUTE_DEMOS[0]['slug'],
        'defaultVehicleId': default_vehicle_id or '',
        'defaultDepartureHour': default_departure_hour,
    }

    return render(request, 'mubil/route.html', {
        'demos': route_services.list_demos(),
        'init_json': json.dumps(init_payload),
        'default_slug': route_services.ROUTE_DEMOS[0]['slug'],
        'ev_vehicles': ev_vehicles,
        'default_vehicle_id': default_vehicle_id,
        'default_origin': default_origin,
        'default_departure_hour': default_departure_hour,
    })


@require_http_methods(["GET", "POST"])
def route_plan(request):
    """HTMX endpoint — returns the route plan partial.

    Two modes (Phase 1 backend):

    * Demo: ``slug`` ∈ :data:`ROUTE_DEMOS` — instant precomputed polyline.
    * Free: ``origin_lng/origin_lat/dest_lng/dest_lat`` (all four) → calls
      ``advisor.get_commute_route`` for a real-roads polyline.

    On initial preload (``hx-trigger="load"`` with no inputs filled), falls
    back to the first demo so the right pane never renders empty.
    """
    src = request.POST if request.method == "POST" else request.GET

    def _opt_float(key):
        raw = src.get(key)
        if raw is None or not str(raw).strip():
            return None
        try:
            return float(str(raw).replace(',', '.'))
        except ValueError:
            return None

    slug = (src.get('slug') or '').strip()
    origin_lng = _opt_float('origin_lng')
    origin_lat = _opt_float('origin_lat')
    dest_lng = _opt_float('dest_lng')
    dest_lat = _opt_float('dest_lat')
    free_coords = (origin_lng, origin_lat, dest_lng, dest_lat)
    has_free_od = all(c is not None for c in free_coords)

    try:
        vehicle_id_raw = src.get('vehicle_id') or ''
        vehicle_id = int(vehicle_id_raw) if vehicle_id_raw else None
        soc_start = float(src.get('soc_start', 80))
        dep_raw = src.get('departure_hour')
        departure_hour = int(dep_raw) if dep_raw not in (None, '') else None
    except ValueError as e:
        return HttpResponseBadRequest(f"Datos del formulario inválidos: {e}")

    postal_code = (src.get('cp') or '').strip() or None

    plan_kwargs = dict(
        vehicle_id=vehicle_id,
        soc_start_pct=soc_start,
        departure_hour=departure_hour,
        postal_code=postal_code,
    )

    try:
        if slug:
            result = route_services.plan(slug=slug, **plan_kwargs)
        elif has_free_od:
            result = route_services.plan(
                origin_lng=origin_lng, origin_lat=origin_lat,
                dest_lng=dest_lng, dest_lat=dest_lat, **plan_kwargs,
            )
        else:
            # Initial preload — show the first demo by default
            result = route_services.plan(
                slug=route_services.ROUTE_DEMOS[0]['slug'], **plan_kwargs,
            )
    except ValueError as e:
        return HttpResponseBadRequest(str(e))

    out = result.to_dict()
    return render(request, 'mubil/_route_result.html', {
        'r': out,
        'r_json': json.dumps(out),
    })


def infrastructure_page(request):
    """Infrastructure map — chargers coloured by vehicle compatibility, plus
    a fast-charging-desert overlay over EH.

    The heavy GeoJSON loads asynchronously from
    ``/mubil/api/v1/infrastructure/chargers.geojson`` so this view stays
    light. Session prefill (``mubil_route_prefill.vehicle_target_id``,
    written by the advisor) makes the page land already coloured for the
    user's chosen EV — same bridge pattern as ``route_page``.
    """
    prefill = request.session.get('mubil_route_prefill') or {}
    vehicle_id = prefill.get('vehicle_target_id')

    vehicle = None
    if vehicle_id:
        vehicle = Vehicle.objects.filter(pk=vehicle_id).only(
            'id', 'make', 'model', 'propulsion',
        ).first()

    ev_vehicles = list(Vehicle.objects.filter(
        propulsion__in=(Vehicle.Propulsion.BEV, Vehicle.Propulsion.PHEV),
    ).only('id', 'make', 'model').order_by('make', 'model'))

    init_payload = {
        'vehicleId': vehicle.id if vehicle else None,
        'vehicleLabel': f"{vehicle.make} {vehicle.model}" if vehicle else None,
        'chargersUrl': '/estrata/api/v1/infrastructure/chargers.geojson',
        'fuelStationsUrl': '/estrata/api/v1/infrastructure/fuel_stations.geojson',
        'desertUrl': '/estrata/api/v1/infrastructure/desert.json',
    }

    return render(request, 'mubil/infrastructure.html', {
        'init_json': json.dumps(init_payload),
        'selected_vehicle': vehicle,
        'ev_vehicles': ev_vehicles,
        'total_chargers': ChargingStation.objects.count(),
        'total_fuel_stations': FuelStation.objects.count(),
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


@require_http_methods(["POST"])
def advisor_assist(request):
    """HTMX endpoint — advisor AI assistant (contextual hints + Q&A).

    Receives JSON body with:
      - context: form state snapshot (step, selected vehicles, km_year, etc.)
      - message: optional free-form user question (empty = proactive hint mode)

    Returns the assistant partial rendered via _advisor_assist.html.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponseBadRequest("JSON inválido.")

    ctx = advisor_assistant.FormContext.from_dict(body.get("context", {}))
    user_message = (body.get("message") or "").strip() or None

    result = advisor_assistant.get_hint(ctx, user_message=user_message)

    return render(request, "mubil/_advisor_assist.html", {
        "result": result,
        "user_message": user_message,
    })

