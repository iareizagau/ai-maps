import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM ways")
    count = cursor.fetchone()[0]
    print("Total ways count:", count)

    cursor.execute("""
        SELECT 
            ST_XMin(extent), ST_YMin(extent), ST_XMax(extent), ST_YMax(extent)
        FROM (
            SELECT ST_Extent(the_geom) as extent FROM ways
        ) sub
    """)
    extent = cursor.fetchone()
    print("Extent of ways:", extent)

    cursor.execute("SELECT count(*) FROM ways_vertices_pgr")
    vert_count = cursor.fetchone()[0]
    print("Total vertices count:", vert_count)
