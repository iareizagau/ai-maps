import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

# Donostia and Hernani nodes
start_node = 1477582
end_node = 1482215

query = """
    SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
        'SELECT gid as id, source, target, 
                CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END as cost,
                CASE WHEN length_m <= 0 THEN 0.1 ELSE length_m END as reverse_cost 
         FROM ways',
        %s, %s, directed := false
    )
"""
with connection.cursor() as cursor:
    cursor.execute(query, [start_node, end_node])
    rows = cursor.fetchall()
    print("Dijkstra with length_m - segment count:", len(rows))
    if rows:
        print("First steps:", rows[:5])
        print("Last steps:", rows[-5:])
