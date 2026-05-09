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
        'icon': app.icon,
        'accent': app.primary_color,
        'is_live': False,
    }


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
    return {
        **_base(app),
        'headline': _("Aire en %(city)s: %(label)s") % {'city': city, 'label': label},
        'subline': _("Eco-score %(s)s/100") % {'s': score} if score else None,
        'meta': _humanize_age(latest.timestamp),
        'is_live': True,
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
        return {
            **_base(app),
            'headline': headline,
            'subline': subline,
            'meta': _("Esta noche"),
        }

    upcoming = (CulturalEvent.objects
        .filter(start_date__date__gt=today)
        .order_by('start_date')
        .first())
    if not upcoming:
        return None

    title = upcoming.title_es or upcoming.title_eu or _("Evento")
    return {
        **_base(app),
        'headline': title,
        'subline': upcoming.venue_name_es or upcoming.venue_name_eu or None,
        'meta': upcoming.start_date.strftime('%d %b'),
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

    return {
        **_base(app),
        'headline': _("Próxima social: %(s)s") % {'s': style},
        'subline': next_event.city or None,
        'meta': meta,
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

    return {
        **_base(app),
        'headline': top.name,
        'subline': _("en %(r)s") % {'r': top.restaurant.name} if top.restaurant_id else None,
        'meta': f"★ {top.avg_rating:.1f} · {top.rating_count}",
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
