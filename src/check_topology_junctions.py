import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT count(*) FROM (
            SELECT vertex_id, count(*) as deg FROM (
                SELECT source as vertex_id FROM ways
                UNION ALL
                SELECT target as vertex_id FROM ways
            ) sub
            GROUP BY vertex_id
        ) deg_sub
        WHERE deg > 1
    """)
    junctions = cursor.fetchone()[0]
    print("Vertices connected to MORE than 1 edge (junctions):", junctions)

    cursor.execute("""
        SELECT count(*) FROM (
            SELECT vertex_id, count(*) as deg FROM (
                SELECT source as vertex_id FROM ways
                UNION ALL
                SELECT target as vertex_id FROM ways
            ) sub
            GROUP BY vertex_id
        ) deg_sub
        WHERE deg = 1
    """)
    dead_ends = cursor.fetchone()[0]
    print("Vertices connected to EXACTLY 1 edge (dead ends):", dead_ends)

    # Let's count how many distinct sources and targets there are in ways compared to vertices
    cursor.execute("SELECT count(distinct id) FROM ways_vertices_pgr")
    distinct_verts = cursor.fetchone()[0]
    print("Distinct vertices in vertices table:", distinct_verts)
