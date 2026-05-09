from django.core.management.base import BaseCommand
from apps.core.models import AppRegistry

class Command(BaseCommand):
    help = 'Initialize the AppRegistry with standard apps'

    def handle(self, *args, **options):
        apps = [
            {
                'slug': 'inguru',
                'name': 'Inguru',
                'tagline': 'Datu Bizidunak: Monitorización ambiental.',
                'domain': 'https://ai.maps.eus/inguru/',
                'icon': 'leaf',
                'primary_color': '#10b981', # Emerald
                'hero_title': 'Euskal Herriko airea',
                'description': 'Calidad del aire, clima y biodiversidad en tiempo real.'
            },
            {
                'slug': 'pintxos',
                'name': 'Pintxos Maps',
                'tagline': 'La guía definitiva de los mejores pintxos.',
                'domain': 'https://ai.maps.eus/pintxos/',
                'icon': 'utensils',
                'primary_color': '#f97316', # Orange
                'hero_title': 'Descubre el sabor local',
                'description': 'Explora los bares y tabernas con los mejores pintxos de la ciudad.'
            },
            {
                'slug': 'kultur',
                'name': 'Kultur Maps',
                'tagline': 'Agenda cultural y eventos en vivo.',
                'domain': 'https://ai.maps.eus/kultur/',
                'icon': 'music',
                'primary_color': '#8b5cf6', # Violet
                'hero_title': 'La cultura a tu alcance',
                'description': 'Conciertos, teatro, exposiciones y mucho más en un solo mapa.'
            },
            {
                'slug': 'sbk',
                'name': 'SBK Hub',
                'tagline': 'Comunidad de Salsa, Bachata y Kizomba.',
                'domain': 'https://ai.maps.eus/sbk/',
                'icon': 'users',
                'primary_color': '#ec4899', # Pink
                'hero_title': 'Baila sin parar',
                'description': 'Encuentra escuelas, sociales y talleres de baile en todo el mundo.'
            },
            {
                'slug': 'gailur',
                'name': 'Gailur',
                'tagline': 'Montañismo y Escalada en Euskadi.',
                'domain': 'https://ai.maps.eus/gailur/',
                'icon': 'mountain',
                'primary_color': '#10b981', # Emerald
                'hero_title': 'Conquista cada cima',
                'description': 'Gestión de salidas de monte y reseñas de vías de escalada con croquis.',
                'is_featured': True
            }
        ]

        for app_data in apps:
            app, created = AppRegistry.objects.update_or_create(
                slug=app_data['slug'],
                defaults=app_data
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} {app.name}")

        self.stdout.write(self.style.SUCCESS('AppRegistry successfully initialized'))
