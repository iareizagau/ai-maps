from datetime import timedelta

from django.conf import settings
from django.db.models import BooleanField, Case, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import CulturalEvent


def map_view(request):
    """
    Main view that renders the Leaflet map.
    """
    context = {
        'OPENWEATHERMAP_API_KEY': settings.OPENWEATHERMAP_API_KEY
    }
    return render(request, 'kultur/map.html', context)


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

    Filters past events server-side and ships only fields actually used by
    the map UI (popup + card + JS filters). Fields like description/url are
    intentionally excluded — none are rendered.
    """
    cutoff = timezone.localdate() - timedelta(days=30)

    qs = (
        CulturalEvent.objects
        .exclude(location__isnull=True)
        .filter(start_date__date__gte=cutoff)
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
                'coordinates': [row['location'].x, row['location'].y],
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
