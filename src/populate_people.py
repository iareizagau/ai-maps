import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.sbk.models import Person

# Create some verified people
people_data = [
    {
        "name": "DJ Khalid",
        "slug": "dj-khalid",
        "bio": "The best DJ in the world (not that one). Salsa and Bachata specialist.",
        "instagram": "djkhalid_sbk",
        "country": "Spain",
        "city": "Madrid",
        "roles": ["dj", "teacher"],
        "is_verified": True
    },
    {
        "name": "Sara Panero",
        "slug": "sara-panero",
        "bio": "World renowned Bachata dancer and teacher.",
        "instagram": "sarapanero",
        "country": "Spain",
        "city": "Madrid",
        "roles": ["teacher", "dancer"],
        "is_verified": True
    },
    {
        "name": "DJ York",
        "slug": "dj-york",
        "bio": "International Bachata DJ based in Germany.",
        "instagram": "dj_york_official",
        "country": "Germany",
        "city": "Munich",
        "roles": ["dj"],
        "is_verified": True
    },
    {
        "name": "Ataca & La Alemana",
        "slug": "ataca-la-alemana",
        "bio": "The most famous Bachata couple in the world.",
        "instagram": "ataca_la_alemana",
        "country": "USA",
        "city": "Orlando",
        "roles": ["teacher", "dancer", "organizer"],
        "is_verified": True
    }
]

for p in people_data:
    person, created = Person.objects.get_or_create(
        slug=p['slug'],
        defaults={
            "name": p['name'],
            "bio": p['bio'],
            "instagram": p['instagram'],
            "country": p['country'],
            "city": p['city'],
            "roles": p['roles'],
            "is_verified": p['is_verified']
        }
    )
    if created:
        print(f"Created {person.name}")
    else:
        print(f"{person.name} already exists")
