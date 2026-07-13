import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT count(*) FROM (
            SELECT count(*), ST_AsText(the_geom) 
            FROM ways_vertices_pgr 
            GROUP BY ST_AsText(the_geom) 
            HAVING count(*) > 1
        ) sub
    """)
    duplicates = cursor.fetchone()[0]
    print("Coordinates with DUPLICATE vertex IDs:", duplicates)
