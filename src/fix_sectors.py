import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.adventure.models import Route
from apps.adventure.services import discover_sectors_from_route

def run():
    routes = Route.objects.all()
    print(f"Iniciando reconstrucción de {routes.count()} rutas...")
    for r in routes:
        print(f" -> Procesando: {r.name}")
        res = discover_sectors_from_route(r)
        print(f"    Sectores nuevos: {res['new_sectors']}")
    print("Misión completada.")

if __name__ == '__main__':
    run()
