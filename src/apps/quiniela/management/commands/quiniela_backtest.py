import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.quiniela.services_seguimiento import backtest


class Command(BaseCommand):
    help = "Backtest walk-forward del modelo Poisson frente a las cuotas de cierre."

    def add_arguments(self, parser):
        parser.add_argument("--temporadas", nargs="+", required=True, help="Temporadas a evaluar (yyYY).")
        parser.add_argument("--divisiones", nargs="+", default=["SP1", "SP2"])
        parser.add_argument("--xi", type=float, default=settings.QUINIELA_DECAY_XI)
        parser.add_argument("--rho", type=float, default=settings.QUINIELA_DC_RHO)
        parser.add_argument("--minimo", type=int, default=settings.QUINIELA_MIN_PARTIDOS)
        parser.add_argument(
            "--metodo-cuotas", default=settings.QUINIELA_METODO_CUOTAS, choices=["proporcional", "shin"]
        )

    def handle(self, *args, temporadas, divisiones, xi, rho, minimo, metodo_cuotas, **options):
        inicio = time.perf_counter()
        res = backtest(temporadas, divisiones, xi=xi, rho=rho, minimo=minimo, metodo_cuotas=metodo_cuotas)
        segundos = time.perf_counter() - inicio
        self.stdout.write(
            f"Backtest temporadas={temporadas} xi={xi} rho={rho} minimo={minimo} cuotas={metodo_cuotas} "
            f"| {res.ajustes} ajustes, {res.omitidos} omitidos, {segundos:.1f}s"
        )
        cabecera = f"{'ámbito':<8} {'fuente':<8} {'n':>6} {'Brier':>7} {'logloss':>8} {'acierto':>8}"
        self.stdout.write(cabecera)
        self.stdout.write("-" * len(cabecera))
        filas = [*((d, m) for d, m in res.por_division.items()), ("TOTAL", res.total)]
        for ambito, metricas in filas:
            for fuente, m in metricas.items():
                if not m.n:
                    continue
                self.stdout.write(
                    f"{ambito:<8} {fuente:<8} {m.n:>6} {m.brier_medio:>7.4f} {m.logloss_medio:>8.4f} "
                    f"{m.tasa_acierto:>8.1%}"
                )
