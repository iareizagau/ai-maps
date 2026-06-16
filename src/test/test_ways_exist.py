import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM ways WHERE source=1477582 OR target=1477582")
    print("Ways connected to 1477582:", cursor.fetchone()[0])
    
    cursor.execute("SELECT COUNT(*) FROM ways WHERE source=1427446 OR target=1427446")
    print("Ways connected to 1427446:", cursor.fetchone()[0])
    
    # Let's find one connected node and trace a very short path
    cursor.execute("SELECT gid, source, target, cost FROM ways WHERE source IS NOT NULL AND target IS NOT NULL LIMIT 1")
    row = cursor.fetchone()
    print("Sample edge:", row)
    
    if row:
        gid, src, tgt, cost = row
        # Run dijkstra between src and tgt
        cursor.execute("""
            SELECT * FROM pgr_dijkstra(
                'SELECT gid as id, source, target, cost FROM ways',
                %s, %s, directed := false
            )
        """, [src, tgt])
        print("Dijkstra 1-hop result count:", len(cursor.fetchall()))
