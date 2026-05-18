from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Pobla la tabla adventure_trails desde pgr_ways aplicando mapeos de superficie'

    def handle(self, *args, **options):
        # 1. Verificar si pgr_ways existe
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'pgr_ways'
                )
            """)
            pgr_exists = cursor.fetchone()[0]

        if not pgr_exists:
            self.stderr.write(self.style.ERROR(
                '✗ La tabla pgr_ways no existe. Ejecuta el importador de OSM primero.'
            ))
            return

        # 2. Verificar si adventure_trails existe
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'adventure_trails'
                )
            """)
            trails_exists = cursor.fetchone()[0]

        if not trails_exists:
            self.stderr.write(self.style.ERROR(
                '✗ La tabla adventure_trails no existe. Ejecuta las migraciones de Django primero.'
            ))
            return

        self.stdout.write('Limpiando y poblando la tabla adventure_trails...')

        with connection.cursor() as cursor:
            # Limpiamos para evitar duplicados si se vuelve a ejecutar
            cursor.execute("TRUNCATE TABLE adventure_trails RESTART IDENTITY;")
            
            # Insertar con mapeo inteligente de superficies
            query = """
                INSERT INTO adventure_trails (
                    source, target, cost, reverse_cost, name, surface, highway, 
                    tracktype, sac_scale, mtb_scale, geom
                )
                SELECT 
                    pgr_ways.source, 
                    pgr_ways.target,
                    COALESCE(pgr_ways.bikepacking_cost, pgr_ways.length_m) as cost,
                    COALESCE(pgr_ways.bikepacking_cost, pgr_ways.length_m) as reverse_cost,
                    COALESCE(pgr_ways.name, '') as name,
                    CASE 
                        WHEN c.tag_value IN ('motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential', 'living_street', 'service') THEN 'asphalt'
                        WHEN c.tag_value IN ('track', 'path', 'bridleway') THEN 'unpaved'
                        WHEN c.tag_value = 'cycleway' THEN 'cycleway'
                        ELSE 'other'
                    END as surface,
                    COALESCE(c.tag_value, '') as highway,
                    '' as tracktype,
                    '' as sac_scale,
                    '' as mtb_scale,
                    pgr_ways.the_geom as geom
                FROM pgr_ways
                JOIN configuration c ON pgr_ways.tag_id = c.tag_id;
            """
            cursor.execute(query)
            rows_inserted = cursor.rowcount

        self.stdout.write(self.style.SUCCESS(
            f'✓ Completado. Se han insertado {rows_inserted} tramos en la tabla adventure_trails con clasificación de superficie.'
        ))
