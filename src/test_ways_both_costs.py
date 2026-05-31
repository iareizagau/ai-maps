import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

start_node = 1477582 # Donostia
end_node = 1427446 # Tolosa

# Test with both cost and reverse_cost properly selected and positive!
query = """
    SELECT
        ST_AsGeoJSON(ways.the_geom) as geometry,
        ways.name,
        di.cost,
        di.agg_cost,
        ST_Length(ways.the_geom::geography) as length_m
    FROM pgr_dijkstra(
        'SELECT gid as id, source, target, 
                CASE WHEN cost <= 0 THEN 0.00001 ELSE cost END as cost,
                CASE WHEN reverse_cost <= 0 THEN 0.00001 ELSE reverse_cost END as reverse_cost 
         FROM ways',
        %s, %s, directed := false
    ) AS di
    JOIN ways ON di.edge = ways.gid
    ORDER BY di.seq
"""
with connection.cursor() as cursor:
    try:
        cursor.execute(query, [start_node, end_node])
        rows = cursor.fetchall()
        print("Segments found with both costs:", len(rows))
        if rows:
            print("Total distance (km):", sum(r[4] for r in rows) / 1000.0)
    except Exception as e:
        print("Dijkstra failed:", e)
