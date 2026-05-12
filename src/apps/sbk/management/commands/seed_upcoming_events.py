from django.core.management.base import BaseCommand
from apps.sbk.models import Event, Person, DanceStyle, EventType, EventOccurrence
from django.utils import timezone
from datetime import datetime
import uuid

class Command(BaseCommand):
    help = 'Seeds specific upcoming Bachata events with Teachers'

    def handle(self, *args, **options):
        # 1. Get the dancers
        try:
            yul = Person.objects.get(artistic_name='Yulgarmendia')
            maddi = Person.objects.get(artistic_name='Maddi')
        except Person.DoesNotExist:
            self.stdout.write(self.style.ERROR("Dancers not found. Run seed_dancers first."))
            return

        # 2. Define events
        events_data = [
            {
                'name': 'Jauregi, Bailando se entiende la gente',
                'description': 'Social de Bachata en Hernani con Yulgarmendia y Maddi.',
                'city': 'Hernani',
                'address': 'Jauregi Bailara, 29, 20120 Hernani, Gipuzkoa',
                'lat': 43.2662,
                'lng': -1.9757,
                'start_date': datetime(2026, 5, 23, 22, 0),
                'primary_style': DanceStyle.BACHATA,
                'event_type': EventType.PARTY,
            },
            {
                'name': 'La Clandestina',
                'description': 'Evento de Bachata en la sala Pagoa con Yulgarmendia y Maddi.',
                'city': 'Oiartzun',
                'address': 'Pagoaldea Pol., 7, 20180 Ergoien, Gipuzkoa',
                'lat': 43.3087,
                'lng': -1.8631,
                'start_date': datetime(2026, 5, 30, 22, 0),
                'primary_style': DanceStyle.BACHATA,
                'event_type': EventType.PARTY,
            },
            {
                'name': 'Cumbita',
                'description': 'Social de Bachata en el restaurante Fogón (Miramón) con Yulgarmendia y Maddi.',
                'city': 'Donostia / San Sebastián',
                'address': 'P.º de Miramón, 190, 20009 Donostia / San Sebastián, Gipuzkoa',
                'lat': 43.2977,
                'lng': -1.9723,
                'start_date': datetime(2026, 6, 13, 22, 0),
                'primary_style': DanceStyle.BACHATA,
                'event_type': EventType.PARTY,
            },
        ]

        # Clean up old ones to avoid duplicates if slugs match
        for data in events_data:
             Event.objects.filter(name=data['name']).delete()

        for data in events_data:
            from django.utils.text import slugify
            slug = slugify(data['name']) + "-" + data['start_date'].strftime("%Y-%m-%d")
            
            event = Event.objects.create(
                slug=slug,
                name=data['name'],
                description=data['description'],
                city=data['city'],
                address=data['address'],
                lat=data['lat'],
                lng=data['lng'],
                start_date=data['start_date'],
                end_date=data['start_date'] + timezone.timedelta(hours=6),
                primary_style=data['primary_style'],
                event_type=data['event_type'],
                is_verified=True,
                moderation_status='verified',
            )
            
            # Add teachers
            event.teachers.add(yul, maddi)
            
            # Create occurrence
            EventOccurrence.objects.create(
                event=event,
                start_date=data['start_date'],
                end_date=event.end_date
            )

            self.stdout.write(self.style.SUCCESS(f"Updated event {event.name} with Yulgarmendia and Maddi."))
