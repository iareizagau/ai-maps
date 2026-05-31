import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

start_node = 1477582

# We will run pgr_dijkstra with a single source, and query how many nodes it reaches!
# (by not passing a target, or passing a node that doesn't exist to force finding all reachable nodes)
query = """
    SELECT count(distinct node) FROM pgr_dijkstra(
        'SELECT gid as id, source, target, length_m as cost, length_m as reverse_cost FROM ways',
        %s, -9999, directed := false
    )
"""
with connection.cursor() as cursor:
    cursor.execute(query, [start_node])
    count = cursor.fetchone()[0]
    print("Total reachable nodes from 1477582 using length_m:", count)
