import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

# We select 20 random vertices that are sources/targets of ways
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT DISTINCT source 
        FROM ways 
        LIMIT 20
    """)
    nodes = [r[0] for r in cursor.fetchall()]

print("Testing reachability from 20 nodes:")
for node in nodes:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM pgr_drivingDistance(
                'SELECT gid as id, source, target, length_m as cost, length_m as reverse_cost FROM ways',
                %s, 5000, directed := false
            )
        """,
            [node],
        )
        count = cursor.fetchone()[0]
        print(f" - Node {node}: reached {count} nodes within 5km")
