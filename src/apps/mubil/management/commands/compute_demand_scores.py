"""Pre-computa DemandHex.score_now / score_y3 / score_y5 para el módulo `plan`.

PROPUESTA.md §3.4: score heurístico =
    registrations_ev * 0.4 + od_density * 0.4 - current_chargers * 0.2

Ejecutar mensualmente tras ingest MITMA + DGT (vía celery beat o n8n).
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-compute demand scores per H3 hex for the plan module.'

    def add_arguments(self, parser):
        parser.add_argument('--municipality', type=str, default=None, help='NAIA code or empty for all Gipuzkoa.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'compute_demand_scores: not implemented yet — see PROPUESTA.md §3.4 / §6.'
        ))
