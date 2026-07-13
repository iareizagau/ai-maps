import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

# Let's find two vertices in Donostia
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT v1.id, v2.id, ST_Distance(v1.the_geom, v2.the_geom)
        FROM ways_vertices_pgr v1, ways_vertices_pgr v2
        WHERE v1.id <> v2.id
          AND ST_DWithin(v1.the_geom, ST_SetSRID(ST_Point(-1.9812, 43.3183), 4326), 0.01)
          AND ST_DWithin(v2.the_geom, ST_SetSRID(ST_Point(-1.9812, 43.3183), 4326), 0.01)
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("Vertices in Donostia:")
    for r in rows:
        print(" -", r)

    if rows:
        src, tgt, _ = rows[0]
        cursor.execute(
            """
            SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
                'SELECT gid as id, source, target, 
                        CASE WHEN cost <= 0 THEN 0.00001 ELSE cost END as cost,
                        CASE WHEN reverse_cost <= 0 THEN 0.00001 ELSE reverse_cost END as reverse_cost 
                 FROM ways',
                %s, %s, directed := false
            )
        """,
            [src, tgt],
        )
        print("Dijkstra result:", cursor.fetchall())
