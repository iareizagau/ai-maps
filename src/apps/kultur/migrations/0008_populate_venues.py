"""
Data migration: backfill Venue rows from existing CulturalEvent data.

For each unique (venue_name_es, municipality_es) pair found in events with a
non-empty venue name and a non-null location, creates a Venue using the
event's current location as a placeholder (the municipal centroid) and links
the event to it via FK.

geocoded_at stays NULL so the geocode_venues management command knows which
venues still need real Nominatim resolution.
"""

from django.db import migrations


def populate_venues(apps, schema_editor):
    CulturalEvent = apps.get_model('kultur', 'CulturalEvent')
    Venue = apps.get_model('kultur', 'Venue')

    qs = (
        CulturalEvent.objects
        .exclude(venue_name_es__isnull=True)
        .exclude(venue_name_es='')
        .exclude(location__isnull=True)
    )

    cache = {}
    to_update = []

    for event in qs.iterator(chunk_size=500):
        key = (event.venue_name_es.strip(), (event.municipality_es or '').strip())
        venue_id = cache.get(key)
        if venue_id is None:
            venue, _ = Venue.objects.get_or_create(
                name_es=key[0],
                municipality=key[1],
                defaults={
                    'name_eu': (event.venue_name_eu or '').strip(),
                    'province': (event.province or '').strip(),
                    'location': event.location,
                    'geocoding_source': 'municipality_centroid',
                },
            )
            venue_id = venue.pk
            cache[key] = venue_id
        event.venue_id = venue_id
        to_update.append(event)

        if len(to_update) >= 1000:
            CulturalEvent.objects.bulk_update(to_update, ['venue'])
            to_update.clear()

    if to_update:
        CulturalEvent.objects.bulk_update(to_update, ['venue'])


def reverse(apps, schema_editor):
    # The next migration in the reverse direction (0007) drops the FK column
    # and the Venue table entirely, so nothing needs undoing here.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kultur', '0007_venue_culturalevent_venue'),
    ]

    operations = [
        migrations.RunPython(populate_venues, reverse),
    ]
