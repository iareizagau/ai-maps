import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

# Find what road class the nearest edge of Donostia (-1.9812, 43.3183) is.
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT gid, source, target, name, tag_id, ST_AsText(the_geom)
        FROM ways
        ORDER BY the_geom <-> ST_SetSRID(ST_Point(-1.9812, 43.3183), 4326)
        LIMIT 3
    """)
    print("Nearest edges in Donostia:")
    for row in cursor.fetchall():
        print(" -", row[:5])
        
    cursor.execute("""
        SELECT gid, source, target, name, tag_id, ST_AsText(the_geom)
        FROM ways
        ORDER BY the_geom <-> ST_SetSRID(ST_Point(-2.0722, 43.1369), 4326)
        LIMIT 3
    """)
    print("Nearest edges in Tolosa:")
    for row in cursor.fetchall():
        print(" -", row[:5])
