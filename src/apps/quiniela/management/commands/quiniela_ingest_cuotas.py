from django.core.management.base import BaseCommand, CommandError

from apps.quiniela.services_ingest import IngestError, ingest_cuotas_jornada

from ._comun import obtener_jornada


class Command(BaseCommand):
    help = "Asocia las cuotas de fixtures.csv a los partidos de la jornada."

    def add_arguments(self, parser):
        parser.add_argument("--jornada", type=int, help="Id de la jornada (por defecto, la más reciente).")

    def handle(self, *args, jornada, **options):
        obj = obtener_jornada(jornada)
        try:
            res = ingest_cuotas_jornada(obj)
        except IngestError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{obj}: cuotas {res}"))
