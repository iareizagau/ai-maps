import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection


def find_nearest_node_ways(lon, lat):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH nearest_edge AS (
                SELECT source, target 
                FROM ways
                ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
                LIMIT 1
            )
            SELECT v.id 
            FROM ways_vertices_pgr v
            JOIN nearest_edge e ON v.id = e.source OR v.id = e.target
            ORDER BY v.the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
            LIMIT 1
        """,
            [lon, lat, lon, lat],
        )
        row = cursor.fetchone()
        return row[0] if row else None


start_node = find_nearest_node_ways(-1.9812, 43.3183)  # Donostia
end_node = find_nearest_node_ways(-1.9764, 43.2662)  # Hernani
print("Nearest nodes:", start_node, end_node)

if start_node and end_node:
    # Let's run Dijkstra with positive costs
    query = """
        SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
            'SELECT gid as id, source, target, 
                    CASE WHEN cost <= 0 THEN 0.00001 ELSE cost END as cost,
                    CASE WHEN reverse_cost <= 0 THEN 0.00001 ELSE reverse_cost END as reverse_cost 
             FROM ways',
            %s, %s, directed := false
        )
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node, end_node])
        rows = cursor.fetchall()
        print("Hernani path segments:", len(rows))
