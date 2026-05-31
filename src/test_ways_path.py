import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

# Let's find a source node and target node of the same way or connected ways
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT w1.source, w2.target, ST_Distance(w1.the_geom, w2.the_geom)
        FROM ways w1
        JOIN ways w2 ON w1.target = w2.source
        WHERE w1.source IS NOT NULL AND w2.target IS NOT NULL
        LIMIT 1
    """)
    row = cursor.fetchone()
    print("Directly connected vertices via 2 edges:", row)
    
    if row:
        src, tgt, dist = row
        # Dijkstra
        cursor.execute("""
            SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
                'SELECT gid as id, source, target, CASE WHEN cost <= 0 THEN 0.00001 ELSE cost END as cost FROM ways',
                %s, %s, directed := false
            )
        """, [src, tgt])
        print("Dijkstra 2-hop result:", cursor.fetchall())

    # Let's check if there is any larger path (e.g. 5 steps)
    cursor.execute("""
        SELECT w1.source, w5.target
        FROM ways w1
        JOIN ways w2 ON w1.target = w2.source
        JOIN ways w3 ON w2.target = w3.source
        JOIN ways w4 ON w3.target = w4.source
        JOIN ways w5 ON w4.target = w5.source
        WHERE w1.source IS NOT NULL AND w5.target IS NOT NULL
        LIMIT 1
    """)
    row = cursor.fetchone()
    print("5-hop connected vertices:", row)
    if row:
        src, tgt = row
        cursor.execute("""
            SELECT seq, node, edge, cost, agg_cost FROM pgr_dijkstra(
                'SELECT gid as id, source, target, CASE WHEN cost <= 0 THEN 0.00001 ELSE cost END as cost FROM ways',
                %s, %s, directed := false
            )
        """, [src, tgt])
        print("Dijkstra 5-hop result count:", len(cursor.fetchall()))
