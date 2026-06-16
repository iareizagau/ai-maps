import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection
import json

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
    # Use standard bounding box containing both coords
    min_lon = min(-1.9812, -2.0722) - 0.2
    max_lon = max(-1.9812, -2.0722) + 0.2
    min_lat = min(43.3183, 43.1369) - 0.2
    max_lat = max(43.3183, 43.1369) + 0.2
    
    bbox_filter = f"WHERE the_geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)"
    
    query = f"""
        SELECT
            ST_AsGeoJSON(ways.the_geom) as geometry,
            ways.name,
            di.cost,
            di.agg_cost,
            ST_Length(ways.the_geom::geography) as length_m,
            ways.tag_id
        FROM pgr_dijkstra(
            'SELECT gid as id, source, target, cost FROM ways {bbox_filter}',
            %s, %s, directed := false
        ) AS di
        JOIN ways ON di.edge = ways.gid
        ORDER BY di.seq
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node, end_node])
        rows = cursor.fetchall()
    
    print("Segments found with bbox:", len(rows))
    if rows:
        print("Total cost:", rows[-1][3])
        total_dist = sum(r[4] for r in rows)
        print("Total distance (m):", total_dist)
        # print some highway tag ids
        tag_ids = [r[5] for r in rows[:10]]
        print("Sample tag ids:", tag_ids)
