"""Pulso: un dato 'vivo' por app activa para la sección 'Hoy en Euskal Herria'.

Cada provider retorna un dict (o None) con la forma:
    {url, app_name, icon, accent, headline, subline, meta, is_live}

Fallos por provider son silenciosos (logged) — la home nunca rompe por datos.
"""
import logging
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import get_language, gettext as _

logger = logging.getLogger(__name__)

PULSE_CACHE_TTL = 60 * 5


def get_pulse_items():
    cache_key = f"home:pulse_items:{get_language()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.core.models import AppRegistry
    apps_by_slug = {a.slug: a for a in AppRegistry.objects.filter(is_active=True)}

    providers = [
        ('inguru', _inguru_pulse),
        ('kultur', _kultur_pulse),
        ('sbk', _sbk_pulse),
        ('pintxos', _pintxos_pulse),
    ]

    items = []
    had_failure = False
    for slug, provider in providers:
        app = apps_by_slug.get(slug)
        if not app:
            continue
        try:
            item = provider(app)
            if item:
                items.append(item)
        except Exception:
            had_failure = True
            logger.exception("pulse provider failed: %s", slug)

    # Don't poison the cache: skip caching when everything failed or returned nothing.
    # A partial success (some providers OK, others raised) is still cached — those
    # failures are likely persistent (missing fields, schema mismatch) and re-trying
    # every request would just re-spam the logs.
    if items or not had_failure:
        cache.set(cache_key, items, PULSE_CACHE_TTL)
    return items


def invalidate():
    """Call after data ingestion to refresh the pulse before TTL."""
    for lang in ('es', 'eu', 'en'):
        cache.delete(f"home:pulse_items:{lang}")


def _base(app):
    return {
        'url': app.get_absolute_url,
        'app_name': app.name,
        'app_slug': app.slug,
        'icon': app.icon,
        'accent': app.primary_color,
        'is_live': False,
        'lat': None,
        'lon': None,
    }


def _coords_from_point(point):
    """PostGIS Point → (lat, lon) tuple or (None, None)."""
    if point is None:
        return None, None
    try:
        return point.y, point.x
    except Exception:
        return None, None


# Fallback solo si la ciudad/municipio es de Euskal Herria; no fabricamos
# coordenadas para eventos fuera (e.g. SBK en Francia se queda fuera del mapa,
# que es lo honesto: la card de pulse igualmente aparece en texto).
_EH_CITY_COORDS = {
    'bilbao': (43.263, -2.935),
    'bilbo': (43.263, -2.935),
    'donostia': (43.318, -1.981),
    'donostia / san sebastián': (43.318, -1.981),
    'san sebastián': (43.318, -1.981),
    'san sebastian': (43.318, -1.981),
    'vitoria': (42.846, -2.672),
    'vitoria-gasteiz': (42.846, -2.672),
    'gasteiz': (42.846, -2.672),
    'iruñea': (42.812, -1.645),
    'iruña': (42.812, -1.645),
    'pamplona': (42.812, -1.645),
    'pamplona/iruña': (42.812, -1.645),
    'bizkaia': (43.263, -2.935),
    'vizcaya': (43.263, -2.935),
    'gipuzkoa': (43.318, -1.981),
    'guipúzcoa': (43.318, -1.981),
    'álava': (42.846, -2.672),
    'araba': (42.846, -2.672),
    'navarra': (42.812, -1.645),
    'nafarroa': (42.812, -1.645),
}


def _coords_or_city_fallback(point, *cities):
    """Real Point if available, else first known EH city/province match."""
    lat, lon = _coords_from_point(point)
    if lat is not None and lon is not None:
        return lat, lon
    for city in cities:
        if not city:
            continue
        key = str(city).strip().lower()
        if key in _EH_CITY_COORDS:
            return _EH_CITY_COORDS[key]
    return None, None


def _inguru_pulse(app):
    from apps.inguru.models import Measurement

    latest = (Measurement.objects
        .filter(station__municipality__icontains='Bilbao')
        .select_related('station')
        .order_by('-timestamp')
        .first())
    if not latest:
        latest = (Measurement.objects
            .select_related('station')
            .order_by('-timestamp')
            .first())
    if not latest:
        return None

    score = latest.eco_score or 0
    if score >= 80:
        label = _("Excelente")
    elif score >= 60:
        label = _("Buena")
    elif score >= 40:
        label = _("Moderada")
    else:
        label = _("Baja")

    city = latest.station.municipality or latest.station.name
    lat, lon = _coords_or_city_fallback(latest.station.location, city, latest.station.province)
    return {
        **_base(app),
        'headline': _("Aire en %(city)s: %(label)s") % {'city': city, 'label': label},
        'subline': _("Eco-score %(s)s/100") % {'s': score} if score else None,
        'meta': _humanize_age(latest.timestamp),
        'is_live': True,
        'lat': lat,
        'lon': lon,
    }


def _kultur_pulse(app):
    from apps.kultur.models import CulturalEvent

    today = timezone.localdate()
    today_qs = (CulturalEvent.objects
        .filter(start_date__date=today)
        .order_by('start_date'))
    count = today_qs.count()

    if count >= 1:
        first = today_qs.first()
        title = first.title_es or first.title_eu or _("Evento")
        venue = first.venue_name_es or first.venue_name_eu or ''
        if count > 1:
            headline = _("%(n)s eventos hoy") % {'n': count}
            subline = title
        else:
            headline = title
            subline = venue or None
        lat, lon = _coords_or_city_fallback(
            first.location, first.municipality_es, first.municipality_eu, first.province
        )
        return {
            **_base(app),
            'headline': headline,
            'subline': subline,
            'meta': _("Esta noche"),
            'lat': lat,
            'lon': lon,
        }

    upcoming = (CulturalEvent.objects
        .filter(start_date__date__gt=today)
        .order_by('start_date')
        .first())
    if not upcoming:
        return None

    title = upcoming.title_es or upcoming.title_eu or _("Evento")
    lat, lon = _coords_or_city_fallback(
        upcoming.location, upcoming.municipality_es, upcoming.municipality_eu, upcoming.province
    )
    return {
        **_base(app),
        'headline': title,
        'subline': upcoming.venue_name_es or upcoming.venue_name_eu or None,
        'meta': upcoming.start_date.strftime('%d %b'),
        'lat': lat,
        'lon': lon,
    }


def _sbk_pulse(app):
    from apps.sbk.models import Event

    now = timezone.now()
    next_event = (Event.objects
        .filter(start_date__gte=now, moderation_status__in=['verified', 'pending'])
        .order_by('start_date')
        .first())
    if not next_event:
        return None

    delta = next_event.start_date - now
    if delta.total_seconds() < 12 * 3600:
        meta = _("Esta noche") + f" · {next_event.start_date.strftime('%H:%M')}"
    elif delta.days < 7:
        meta = next_event.start_date.strftime('%a %H:%M').capitalize()
    else:
        meta = next_event.start_date.strftime('%d %b')

    style = (next_event.get_primary_style_display()
             if hasattr(next_event, 'get_primary_style_display')
             else next_event.primary_style)

    lat, lon = _coords_or_city_fallback(getattr(next_event, 'location', None), next_event.city)
    return {
        **_base(app),
        'headline': _("Próxima social: %(s)s") % {'s': style},
        'subline': next_event.city or None,
        'meta': meta,
        'lat': lat,
        'lon': lon,
    }


def _pintxos_pulse(app):
    from apps.pintxos.models import Dish

    top = (Dish.objects
        .filter(rating_count__gte=1)
        .select_related('restaurant')
        .order_by('-avg_rating', '-rating_count')
        .first())
    if not top:
        return None

    lat, lon = (None, None)
    if top.restaurant_id:
        lat, lon = _coords_or_city_fallback(top.restaurant.location, top.restaurant.address)
    return {
        **_base(app),
        'headline': top.name,
        'subline': _("en %(r)s") % {'r': top.restaurant.name} if top.restaurant_id else None,
        'meta': f"★ {top.avg_rating:.1f} · {top.rating_count}",
        'lat': lat,
        'lon': lon,
    }


def _humanize_age(ts):
    if not ts:
        return ''
    secs = int((timezone.now() - ts).total_seconds())
    if secs < 60:
        return _("ahora")
    if secs < 3600:
        return _("hace %(m)smin") % {'m': secs // 60}
    if secs < 86400:
        return _("hace %(h)sh") % {'h': secs // 3600}
    return _("hace %(d)sd") % {'d': secs // 86400}
