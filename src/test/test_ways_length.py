import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

def find_nearest_node_ways(lon, lat):
    with connection.cursor() as cursor:
        cursor.execute("""
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
        """, [lon, lat, lon, lat])
        row = cursor.fetchone()
        return row[0] if row else None

start_node = find_nearest_node_ways(-1.9812, 43.3183) # Donostia
end_node = find_nearest_node_ways(-2.0722, 43.1369) # Tolosa
print("Nearest nodes:", start_node, end_node)

if start_node and end_node:
    # Use length_m as cost and reverse_cost!
    cost_expr = "CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END"
    
    query = f"""
        SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
            'SELECT gid as id, source, target, 
                    {cost_expr} as cost,
                    {cost_expr} as reverse_cost 
             FROM ways',
            %s, %s, directed := false
        )
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node, end_node])
        rows = cursor.fetchall()
        print("Tolosa path segments with length_m:", len(rows))
        if rows:
            print("Total distance (km) from agg_cost:", rows[-1][4] / 1000.0)
