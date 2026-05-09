from collections import defaultdict
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import BooleanField, Case, Q, Value, When
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import CulturalEvent


def map_view(request):
    """
    Main view that renders the Leaflet map.
    """
    return render(request, 'kultur/map.html')


_OWM_ICONS = {
    'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Drizzle': '🌦️',
    'Snow': '❄️', 'Thunderstorm': '⛈️', 'Mist': '🌫️', 'Fog': '🌫️',
}


@require_GET
def weather_forecast(request):
    """
    Server-side proxy for OpenWeatherMap 5-day/3h forecast.

    Aggregates 3h slots into daily summaries and caches per ~11km grid cell
    so the API key never reaches the browser and a region's forecast is
    fetched at most once per hour regardless of concurrent users.
    """
    try:
        lat = round(float(request.GET['lat']), 1)
        lng = round(float(request.GET['lng']), 1)
    except (KeyError, ValueError):
        return HttpResponseBadRequest('lat/lng required')

    cache_key = f'kultur:forecast:{lat}:{lng}'
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)

    api_key = settings.OPENWEATHERMAP_API_KEY
    if not api_key:
        return JsonResponse({'days': [], 'location': '', 'now': None})

    try:
        r = requests.get(
            'https://api.openweathermap.org/data/2.5/forecast',
            params={'lat': lat, 'lon': lng, 'units': 'metric', 'appid': api_key},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return JsonResponse({'days': [], 'location': '', 'now': None})

    by_day = defaultdict(list)
    for slot in data.get('list', []):
        dt = datetime.fromtimestamp(slot['dt'])
        by_day[dt.date().isoformat()].append(slot)

    days = []
    for date_key in sorted(by_day.keys())[:6]:
        slots = by_day[date_key]
        temps = [s['main']['temp'] for s in slots]
        midday = min(slots, key=lambda s: abs(datetime.fromtimestamp(s['dt']).hour - 13))
        cond = midday['weather'][0]['main'] if midday.get('weather') else 'Clouds'
        rain_mm = sum(s.get('rain', {}).get('3h', 0) for s in slots)
        days.append({
            'date': date_key,
            'temp_max': round(max(temps)),
            'temp_min': round(min(temps)),
            'condition': cond,
            'icon': _OWM_ICONS.get(cond, '⛅'),
            'rain_mm': round(rain_mm, 1),
        })

    first = data.get('list', [{}])[0]
    now = None
    if first:
        cond = first.get('weather', [{}])[0].get('main', 'Clouds')
        now = {
            'temp': round(first.get('main', {}).get('temp', 0)),
            'condition': cond,
            'icon': _OWM_ICONS.get(cond, '⛅'),
        }

    payload = {
        'days': days,
        'location': data.get('city', {}).get('name', ''),
        'now': now,
    }
    cache.set(cache_key, payload, 60 * 60)
    return JsonResponse(payload)


# Server-side detection of "family-friendly" events.
# Why: avoids shipping description fields (~50% of payload). Matches only
# on category + title (short fields, fast). Description ICONTAINS would
# add ~1.3s to the query at 3k rows — not worth it for a fuzzy mood filter.
_IS_FAMILY_Q = (
    Q(event_type_es__icontains='infantil')
    | Q(event_type_es__icontains='taller')
    | Q(event_type_eu__icontains='haur')
    | Q(title_es__icontains='familia')
    | Q(title_es__icontains='infantil')
    | Q(title_es__icontains='niños')
    | Q(title_eu__icontains='haur')
    | Q(title_eu__icontains='familia')
)


def events_geojson(request):
    """
    Returns upcoming CulturalEvents as GeoJSON.

    Coordinates come from the linked Venue (real geocoded position when
    available, municipal centroid as fallback). Falls back to the legacy
    CulturalEvent.location only for events with no venue link yet.
    """
    cutoff = timezone.localdate()

    qs = (
        CulturalEvent.objects
        .filter(start_date__date__gte=cutoff)
        .filter(Q(venue__isnull=False) | Q(location__isnull=False))
        .annotate(
            is_family=Case(
                When(_IS_FAMILY_Q, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )
        .values(
            'id',
            'location',
            'venue__location',
            'title_es', 'title_eu',
            'event_type_es', 'event_type_eu',
            'venue_name_es', 'venue_name_eu',
            'municipality_es', 'municipality_eu',
            'opening_hours_es', 'opening_hours_eu',
            'price_es', 'price_eu',
            'start_date',
            'image_url',
            'is_family',
        )
    )

    features = [
        {
            'type': 'Feature',
            'id': row['id'],
            'geometry': {
                'type': 'Point',
                'coordinates': [
                    (row['venue__location'] or row['location']).x,
                    (row['venue__location'] or row['location']).y,
                ],
            },
            'properties': {
                'title_es': row['title_es'],
                'title_eu': row['title_eu'],
                'event_type_es': row['event_type_es'],
                'event_type_eu': row['event_type_eu'],
                'venue_name_es': row['venue_name_es'],
                'venue_name_eu': row['venue_name_eu'],
                'municipality_es': row['municipality_es'],
                'municipality_eu': row['municipality_eu'],
                'opening_hours_es': row['opening_hours_es'],
                'opening_hours_eu': row['opening_hours_eu'],
                'price_es': row['price_es'],
                'price_eu': row['price_eu'],
                'start_date': row['start_date'].isoformat() if row['start_date'] else None,
                'image_url': row['image_url'],
                'is_family': row['is_family'],
            },
        }
        for row in qs
    ]

    return JsonResponse({'type': 'FeatureCollection', 'features': features})
