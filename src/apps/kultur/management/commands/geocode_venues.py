"""
Geocode kultur Venues against Nominatim.

Idempotent: only processes venues with geocoded_at IS NULL. Re-run safely after
new ingest cycles to resolve any new venues. Honors Nominatim's 1 req/s policy.

Strategy per venue:
  1. Try `"{name}, {municipality}, Euskadi, Spain"` constrained to a bbox over
     Euskal Herria (rejects matches in other regions with same name).
  2. If no result, fall back to `"{name}, {municipality}"` without the bbox.
  3. If still nothing, leave geocoded_at = NULL so the next run retries.
     The municipal-centroid location stays as fallback.
"""

import time

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.kultur.models import Venue

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'MapsEus/1.0 kultur (https://maps.eus)'

# Bbox covering Euskal Herria (Hegoalde + Iparralde) — viewbox is left,top,right,bottom
EH_VIEWBOX = '-3.5,43.6,-1.0,42.4'

REQUEST_DELAY_S = 1.1


class Command(BaseCommand):
    help = 'Geocodes pending Venues using Nominatim'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Max venues to process (default: all pending)',
        )
        parser.add_argument(
            '--retry-failed', action='store_true',
            help='Also retry venues whose source is municipality_centroid',
        )

    def handle(self, *args, **options):
        qs = Venue.objects.filter(geocoded_at__isnull=True)
        if options['retry_failed']:
            qs = Venue.objects.filter(
                geocoding_source=Venue.SOURCE_MUNICIPALITY,
            )
        if options['limit']:
            qs = qs[:options['limit']]

        venues = list(qs)
        total = len(venues)
        self.stdout.write(self.style.SUCCESS(f'Found {total} venues to geocode.'))

        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT})

        resolved = 0
        for i, venue in enumerate(venues, 1):
            label = f'{venue.name_es} / {venue.municipality}'
            self.stdout.write(f'[{i}/{total}] {label}')

            point = self._geocode(session, venue.name_es, venue.municipality)
            if point is not None:
                venue.location = point
                venue.geocoding_source = Venue.SOURCE_NOMINATIM
                venue.geocoded_at = timezone.now()
                venue.save(update_fields=['location', 'geocoding_source', 'geocoded_at', 'updated_at'])
                self.stdout.write(self.style.SUCCESS(f'  ✓ {point.y:.5f}, {point.x:.5f}'))
                resolved += 1
            else:
                self.stdout.write(self.style.WARNING('  ✗ no match (kept municipality centroid)'))

        self.stdout.write(self.style.SUCCESS(
            f'Done. Resolved {resolved}/{total} venues.'
        ))

    def _geocode(self, session, name, municipality):
        # Multiple passes, narrowest first. Each later pass relaxes the query
        # because OSM entries vary wildly in how they're tagged: some include
        # the municipality, some don't; some carry the full official name,
        # most carry the short colloquial one.
        clean = self._clean_name(name)

        # 1. Full name + municipality, constrained to Euskal Herria bbox
        point = self._query(
            session, f'{name}, {municipality}',
            viewbox=EH_VIEWBOX, bounded=True,
        )
        if point is not None:
            return point

        # 2. Cleaned name + municipality, bbox
        if clean and clean != name:
            point = self._query(
                session, f'{clean}, {municipality}',
                viewbox=EH_VIEWBOX, bounded=True,
            )
            if point is not None:
                return point

        # 3. Cleaned name alone, bbox — catches well-tagged OSM POIs whose
        # entry doesn't include the municipality string. Bbox keeps us in EH.
        if clean:
            point = self._query(
                session, clean,
                viewbox=EH_VIEWBOX, bounded=True,
            )
            if point is not None:
                return point

        # 4. Last resort: relaxed, no bbox. Risk of false positives is real
        # (same venue name elsewhere in Spain), but at this point we'd
        # otherwise fall back to municipal centroid — usually worse.
        return self._query(session, f'{name}, {municipality}')

    @staticmethod
    def _clean_name(name):
        """
        Strip noise that hurts Nominatim matching: text after `.` or `(`,
        leading institutional prefixes (Fundación, Centro Cultural, Sede de…).
        Returns '' if nothing meaningful remains.
        """
        # Drop "Sagardoetxea. Museo de la Sidra Vasca" → "Sagardoetxea"
        for sep in ('.', '('):
            idx = name.find(sep)
            if idx > 0:
                name = name[:idx]
        return name.strip(' ,-')

    def _query(self, session, q, viewbox=None, bounded=False):
        # Throttle on every individual call. Nominatim's policy is 1 req/s and
        # each venue can fan out into up to 4 queries; sleeping per-venue would
        # blow the budget by 3-4x and trigger 429s.
        time.sleep(REQUEST_DELAY_S)

        params = {'q': q, 'format': 'json', 'limit': 1}
        if viewbox:
            params['viewbox'] = viewbox
        if bounded:
            params['bounded'] = 1
        try:
            r = session.get(NOMINATIM_URL, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            self.stdout.write(self.style.ERROR(f'  ! {exc}'))
            return None
        if not data:
            return None
        return Point(float(data[0]['lon']), float(data[0]['lat']), srid=4326)
