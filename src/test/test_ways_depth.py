import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

start_node = 1477582  # Donostia center node

# Let's find all nodes reachable from start_node within 3 hops
with connection.cursor() as cursor:
    cursor.execute(
        """
        SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
            'SELECT gid as id, source, target, 
                    CASE WHEN cost <= 0 THEN 0.00001 ELSE cost END as cost,
                    CASE WHEN reverse_cost <= 0 THEN 0.00001 ELSE reverse_cost END as reverse_cost 
             FROM ways',
            %s, ARRAY[1477582, 1477345, 1506019, 1506020, 1479212], directed := false
        )
    """,
        [start_node],
    )
    print("Reachable nodes:", cursor.fetchall())
