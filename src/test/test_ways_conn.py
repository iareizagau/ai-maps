import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

# Find two vertices close to each other
with connection.cursor() as cursor:
    # Let's find two vertices that are within 5 km of each other
    cursor.execute("""
        SELECT w1.source, w2.target
        FROM ways w1, ways w2
        WHERE w1.gid <> w2.gid 
          AND w1.source IS NOT NULL 
          AND w2.target IS NOT NULL
          AND ST_DWithin(w1.the_geom, w2.the_geom, 0.05)
        LIMIT 1
    """)
    row = cursor.fetchone()
    print("Close vertices:", row)
    
    if row:
        src, tgt = row
        cursor.execute("""
            SELECT count(*) FROM pgr_dijkstra(
                'SELECT gid as id, source, target, cost FROM ways',
                %s, %s, directed := false
            )
        """, [src, tgt])
        print("Dijkstra count:", cursor.fetchone()[0])
