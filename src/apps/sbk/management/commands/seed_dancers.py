from django.core.management.base import BaseCommand
from apps.sbk.models import Person, DanceStyle

class Command(BaseCommand):
    help = 'Seeds the database with initial dancers'

    def handle(self, *args, **options):
        dancers_data = [
            {
                'first_name': 'Julen',
                'last_name': 'Garmendia',
                'artistic_name': 'Yulgarmendia',
                'roles': [Person.Role.TEACHER, Person.Role.ORGANIZER, Person.Role.DANCER],
                'styles': [DanceStyle.BACHATA],
                'is_verified': True,
                'city': 'Donostia / San Sebastián',
            },
            {
                'first_name': 'Maddi',
                'last_name': 'Erauskin',
                'artistic_name': 'Maddi',
                'roles': [Person.Role.TEACHER, Person.Role.DANCER],
                'styles': [DanceStyle.BACHATA],
                'is_verified': True,
                'city': 'Donostia / San Sebastián',
            },
            {
                'first_name': 'Oihane',
                'last_name': '',
                'artistic_name': 'Vexdance',
                'roles': [Person.Role.TEACHER, Person.Role.DANCER],
                'styles': [DanceStyle.BACHATA],
                'is_verified': True,
                'city': 'Donostia / San Sebastián',
            },
        ]

        for data in dancers_data:
            person, created = Person.objects.update_or_create(
                artistic_name=data['artistic_name'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created dancer: {person.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Updated dancer: {person.name}"))
