"""
Management command para configurar los costes de pgRouting.
Ejecuta el script define_costs.sql que añade las columnas bikepacking_cost
y hiking_cost a la tabla pgr_ways.

Uso:
    python manage.py setup_routing_costs
    python manage.py setup_routing_costs --check   # Solo verifica si ya están aplicados
"""
from django.core.management.base import BaseCommand
from django.db import connection
import os


COSTS_SQL_PATH = os.path.join(
    os.path.dirname(__file__),
    '..', '..', 'scripts', 'define_costs.sql'
)


class Command(BaseCommand):
    help = 'Aplica los costes de enrutamiento (bikepacking/hiking) a la tabla pgr_ways'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Solo verifica si las columnas ya existen, sin modificar nada',
        )

    def handle(self, *args, **options):
        check_only = options['check']

        # 1. Verificar si pgr_ways existe
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'pgr_ways'
                )
            """)
            table_exists = cursor.fetchone()[0]

        if not table_exists:
            self.stderr.write(self.style.ERROR(
                '✗ La tabla pgr_ways no existe. '
                'Importa los datos OSM con osm2pgrouting primero.'
            ))
            return

        # 2. Verificar si las columnas de coste ya existen
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'pgr_ways'
                AND column_name IN ('bikepacking_cost', 'hiking_cost')
            """)
            existing_cols = {row[0] for row in cursor.fetchall()}

        has_bikepacking = 'bikepacking_cost' in existing_cols
        has_hiking = 'hiking_cost' in existing_cols

        self.stdout.write(f"  bikepacking_cost : {'✓ existe' if has_bikepacking else '✗ falta'}")
        self.stdout.write(f"  hiking_cost      : {'✓ existe' if has_hiking else '✗ falta'}")

        if check_only:
            if has_bikepacking and has_hiking:
                self.stdout.write(self.style.SUCCESS('✓ Costes ya configurados correctamente.'))
            else:
                self.stdout.write(self.style.WARNING(
                    'Costes incompletos. Ejecuta sin --check para aplicarlos.'
                ))
            return

        if has_bikepacking and has_hiking:
            self.stdout.write(self.style.SUCCESS('✓ Costes ya configurados. Nada que hacer.'))
            return

        # 3. Ejecutar el SQL
        sql_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../scripts/define_costs.sql'))
        if not os.path.exists(sql_path):
            self.stderr.write(self.style.ERROR(f'✗ No se encuentra el script: {sql_path}'))
            return

        self.stdout.write(f'Ejecutando {sql_path} ...')
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        # Separar por sentencias (el script tiene varios ALTER TABLE y UPDATE)
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

        with connection.cursor() as cursor:
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                    self.stdout.write(f'  OK: {stmt[:60].replace(chr(10), " ")}...')
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  ERROR: {e}'))
                    raise

        self.stdout.write(self.style.SUCCESS(
            '✓ Costes de pgRouting aplicados correctamente. '
            'El enrutador ya puede calcular rutas de bikepacking e hiking.'
        ))
