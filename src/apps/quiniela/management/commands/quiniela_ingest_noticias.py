from django.core.management.base import BaseCommand

from apps.quiniela.services_ingest import ingest_noticias

from ._comun import obtener_jornada


class Command(BaseCommand):
    help = "Recoge noticias RSS (últimos 7 días) de los equipos de la jornada."

    def add_arguments(self, parser):
        parser.add_argument("--jornada", type=int, help="Id de la jornada (por defecto, la más reciente).")

    def handle(self, *args, jornada, **options):
        obj = obtener_jornada(jornada)
        res = ingest_noticias(obj)
        self.stdout.write(self.style.SUCCESS(f"{obj}: noticias {res}"))
