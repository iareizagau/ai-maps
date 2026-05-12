from django.core.management.base import BaseCommand
from apps.sbk.models import DanceVenue, DanceVenueType
from django.utils.text import slugify
from django.contrib.gis.geos import Point

class Command(BaseCommand):
    help = 'Seeds initial dance venues and academies with coordinates'

    def handle(self, *args, **options):
        venues_data = [
            {
                'name': 'Cafe Irun',
                'city': 'Irun',
                'address': 'Letxumborro Hiribidea, 91, 20305 Irun, Gipuzkoa',
                'venue_type': DanceVenueType.BAR,
                'weekly_schedule': {
                    'fri': {'social': ['23:00 - 03:00']},
                    'sun': {'social': ['18:00 - 00:00']}
                },
                'styles': ['bachata', 'salsa'],
                'lat': 43.3411, 'lng': -1.8023,
                'is_verified': True
            },
            {
                'name': 'Gu Donostia',
                'city': 'Donostia / San Sebastián',
                'address': 'Ijentea Kalea, 9, 20004 Donostia / San Sebastián, Gipuzkoa',
                'venue_type': DanceVenueType.SOCIAL,
                'weekly_schedule': {
                    'sun': {'social': ['18:30 - 00:00']}
                },
                'styles': ['bachata', 'salsa', 'kizomba'],
                'lat': 43.3216, 'lng': -1.9856,
                'is_verified': True
            },
            {
                'name': 'Pagoa',
                'city': 'Oiartzun',
                'address': 'Pagoaldea Pol., 7, 20180 Ergoien, Gipuzkoa',
                'venue_type': DanceVenueType.SOCIAL,
                'styles': ['bachata', 'salsa'],
                'lat': 43.3087, 'lng': -1.8631,
                'is_verified': True
            },
            {
                'name': 'Hotel & Thalasso Villa Antilla',
                'city': 'Orio',
                'address': 'Hondartza Bidea, 1, 20810 Orio, Gipuzkoa',
                'venue_type': DanceVenueType.MULTI,
                'styles': ['bachata', 'salsa'],
                'lat': 43.2877, 'lng': -2.1278,
                'is_verified': True
            },
            {
                'name': 'Mola Mola',
                'city': 'Orio',
                'address': 'Antilla Kalea, 3, 20810 Orio, Gipuzkoa',
                'venue_type': DanceVenueType.BAR,
                'weekly_schedule': {
                    'thu': {'social': ['Julio y Agosto']}
                },
                'styles': ['bachata', 'salsa'],
                'lat': 43.2872, 'lng': -2.1284,
                'is_verified': True
            },
            {
                'name': 'Jauregi Hernani',
                'city': 'Hernani',
                'address': 'Jauregi Bailara, 29, 20120 Hernani, Gipuzkoa',
                'venue_type': DanceVenueType.MULTI,
                'styles': ['bachata'],
                'lat': 43.2662, 'lng': -1.9757,
                'is_verified': True
            },
            {
                'name': 'BitanBat',
                'city': 'Hernani',
                'address': 'Agustindarren Plaza, 20120 Hernani, Gipuzkoa',
                'venue_type': DanceVenueType.ACADEMY,
                'styles': ['bachata', 'salsa', 'kizomba'],
                'lat': 43.2655, 'lng': -1.9745,
                'is_verified': True
            },
            {
                'name': 'Dany y Yara | Yulgarmendia y Maddi',
                'city': 'Donostia / San Sebastián',
                'address': 'Pablo Gorosabel Kalea, 3, 20014 Donostia / San Sebastián, Gipuzkoa',
                'venue_type': DanceVenueType.ACADEMY,
                'styles': ['bachata', 'salsa'],
                'lat': 43.3150, 'lng': -1.9780,
                'is_verified': True
            },
        ]

        for data in venues_data:
            slug = slugify(data['name'])
            lat = data.pop('lat')
            lng = data.pop('lng')
            data['location'] = Point(lng, lat)
            
            venue, created = DanceVenue.objects.update_or_create(
                slug=slug,
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created venue: {venue.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Updated venue: {venue.name}"))
