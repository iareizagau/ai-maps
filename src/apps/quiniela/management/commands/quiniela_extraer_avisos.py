from django.core.management.base import BaseCommand

from apps.quiniela.services_avisos import extraer_avisos

from ._comun import obtener_jornada


class Command(BaseCommand):
    help = "Extrae con Gemini los avisos (bajas, sanciones, dudas) de las noticias de la jornada."

    def add_arguments(self, parser):
        parser.add_argument("--jornada", type=int, help="Id de la jornada (por defecto, la más reciente).")

    def handle(self, *args, jornada, **options):
        obj = obtener_jornada(jornada)
        res = extraer_avisos(obj)
        if not res.disponible:
            self.stderr.write(self.style.WARNING(f"{obj}: avisos no disponibles ({res.error})"))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"{obj}: {res.creados} avisos de {res.noticias} titulares ({res.descartados} descartados)"
            )
        )
