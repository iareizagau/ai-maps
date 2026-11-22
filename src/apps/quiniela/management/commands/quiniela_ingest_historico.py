from django.core.management.base import BaseCommand, CommandError

from apps.quiniela.models import cargar_catalogo
from apps.quiniela.services_ingest import DIVISIONES, IngestError, ingest_temporada


class Command(BaseCommand):
    help = "Importa resultados y cuotas de cierre de football-data.co.uk (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--divisiones", nargs="+", default=list(DIVISIONES), choices=DIVISIONES)
        parser.add_argument(
            "--temporadas", nargs="+", required=True, help="Códigos yyYY, p. ej. 2425 2526 2627."
        )

    def handle(self, *args, divisiones, temporadas, **options):
        self.stdout.write(f"Catálogo: {cargar_catalogo()} equipos semilla")
        errores = 0
        for temporada in temporadas:
            for division in divisiones:
                try:
                    res = ingest_temporada(division, temporada)
                except IngestError as exc:
                    errores += 1
                    self.stderr.write(self.style.ERROR(f"{division} {temporada}: {exc}"))
                    continue
                self.stdout.write(self.style.SUCCESS(f"{division} {temporada}: {res}"))
        if errores:
            raise CommandError(f"{errores} temporada(s) sin importar")
