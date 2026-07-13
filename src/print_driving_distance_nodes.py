import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

start_node = 1477582

query = """
    SELECT seq, node, edge, cost, agg_cost FROM pgr_drivingDistance(
        'SELECT gid as id, source, target, length_m as cost, length_m as reverse_cost FROM ways',
        %s, 100000, directed := false
    )
"""
with connection.cursor() as cursor:
    cursor.execute(query, [start_node])
    rows = cursor.fetchall()
    print("Reachable nodes:")
    for r in rows:
        print(" -", r)
