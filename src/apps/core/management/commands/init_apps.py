from django.core.management.base import BaseCommand

from apps.core.models import AppRegistry


class Command(BaseCommand):
    help = "Initialize the AppRegistry with standard apps"

    def handle(self, *args, **options):
        apps = [
            {
                "slug": "inguru",
                "name": "Inguru",
                "tagline": "Datu Bizidunak: Monitorización ambiental.",
                "domain": "https://ai.maps.eus/inguru/",
                "icon": "leaf",
                "primary_color": "#10b981",  # Emerald
                "hero_title": "Euskal Herriko airea",
                "description": "Calidad del aire, clima y biodiversidad en tiempo real.",
            },
            {
                "slug": "pintxos",
                "name": "Pintxos Maps",
                "tagline": "La guía definitiva de los mejores pintxos.",
                "domain": "https://ai.maps.eus/pintxos/",
                "icon": "utensils",
                "primary_color": "#f97316",  # Orange
                "hero_title": "Descubre el sabor local",
                "description": "Explora los bares y tabernas con los mejores pintxos de la ciudad.",
            },
            {
                "slug": "kultur",
                "name": "Kultur Maps",
                "tagline": "Agenda cultural y eventos en vivo.",
                "domain": "https://ai.maps.eus/kultur/",
                "icon": "music",
                "primary_color": "#8b5cf6",  # Violet
                "hero_title": "La cultura a tu alcance",
                "description": "Conciertos, teatro, exposiciones y mucho más en un solo mapa.",
            },
            {
                "slug": "sbk",
                "name": "SBK Hub",
                "tagline": "Comunidad de Salsa, Bachata y Kizomba.",
                "domain": "https://ai.maps.eus/sbk/",
                "icon": "users",
                "primary_color": "#ec4899",  # Pink
                "hero_title": "Baila sin parar",
                "description": "Encuentra escuelas, sociales y talleres de baile en todo el mundo.",
            },
            {
                "slug": "gailur",
                "name": "Gailur",
                "tagline": "Montañismo y Escalada en Euskadi.",
                "domain": "https://ai.maps.eus/gailur/",
                "icon": "mountain",
                "primary_color": "#10b981",  # Emerald
                "hero_title": "Conquista cada cima",
                "description": "Gestión de salidas de monte y reseñas de vías de escalada con croquis.",
                "is_featured": True,
            },
            {
                "slug": "zbe",
                "name": "ZBE Maps",
                "tagline": "Zonas de Bajas Emisiones de Euskadi.",
                "domain": "https://ai.maps.eus/zbe/",
                "icon": "car",
                "primary_color": "#22c55e",  # Green
                "hero_title": "Conoce las ZBE",
                "description": "Visualiza las Zonas de Bajas Emisiones para planificar tus desplazamientos.",
            },
            {
                "slug": "adventure",
                "name": "Adventure Lab",
                "tagline": "Rutas inteligentes de bikepacking y montaña.",
                "domain": "https://ai.maps.eus/adventure/",
                "icon": "compass",
                "primary_color": "#d97706",  # Amber
                "hero_title": "Tu próxima aventura empieza aquí",
                "description": "Calcula rutas personalizadas para bikepacking, senderismo y escalada usando pgRouting.",
            },
            {
                "slug": "solar",
                "name": "Solar 3D",
                "tagline": "Mapa de Potencial Fotovoltaico.",
                "domain": "https://ai.maps.eus/solar/",
                "icon": "sun",
                "primary_color": "#facc15",  # Yellow
                "hero_title": "Energía limpia para tu tejado",
                "description": "Visualiza el potencial solar de tu edificio en 3D y calcula tus ahorros con PVGIS.",
            },
            {
                "slug": "oceania",
                "name": "Pacific Climate Horizon",
                "tagline": "Justicia climática y monitorización del Pacífico.",
                "domain": "https://ai.maps.eus/oceania/",
                "icon": "globe",
                "primary_color": "#14b8a6",  # Teal
                "hero_title": "Horizonte Climático del Pacífico",
                "description": "Cartografía interactiva del aumento de nivel del mar, trayectorias de ciclones e inequidad de carbono en Oceanía.",
                "is_featured": True,
            },
            {
                # Naming display provisional — decisión final pendiente (§1, §17 PROPUESTA.md)
                "slug": "mubil",
                "name": "eStrata",
                "tagline": "Inteligencia abierta de movilidad sostenible vasca.",
                "domain": "https://ai.maps.eus/estrata/",
                "icon": "route",
                "primary_color": "#06b6d4",  # Cyan
                "hero_title": "Movilidad inteligente para Euskal Herria",
                "description": "Asesor TCO (EV vs combustión), Q&A con IA sobre datos abiertos, planificador EV multimodal y heatmap de demanda de carga. Candidatura MUBIL Mobility Awards 2026.",
                "is_featured": True,
            },
            {
                "slug": "blog",
                "name": "Developer Blog",
                "tagline": "Bitácora técnica de desarrollo y WebGIS.",
                "domain": "https://ai.maps.eus/blog/",
                "icon": "book-open",
                "primary_color": "#f97316",  # Orange
                "hero_title": "Detrás de escena de Maps.eus",
                "description": "Artículos técnicos, tutoriales y novedades sobre Django, PostGIS, pgrouting, pgvector y IA en Euskal Herria.",
                "is_featured": True,
            },
        ]

        for app_data in apps:
            app, created = AppRegistry.objects.update_or_create(
                slug=app_data["slug"], defaults=app_data
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status} {app.name}")

        self.stdout.write(self.style.SUCCESS("AppRegistry successfully initialized"))
