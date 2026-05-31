import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

start_node = 1477582 # Donostia center node

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
            'SELECT gid as id, source, target, 
                    CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END as cost,
                    CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END as reverse_cost 
             FROM ways',
            %s, ARRAY[1477582, 1477345, 1506019, 1506020, 1479212], directed := false
        )
    """, [start_node])
    print("Reachable nodes with length_m:", cursor.fetchall())
