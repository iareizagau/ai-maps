import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Let's count how many ways are within 5 km of Donostia (-1.9812, 43.3183)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ways
        WHERE ST_DWithin(the_geom, ST_SetSRID(ST_Point(-1.9812, 43.3183), 4326), 0.05)
    """)
    print("Ways in Donostia (~5km):", cursor.fetchone()[0])

    # Let's count how many ways are within 5 km of Tolosa (-2.0722, 43.1369)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ways
        WHERE ST_DWithin(the_geom, ST_SetSRID(ST_Point(-2.0722, 43.1369), 4326), 0.05)
    """)
    print("Ways in Tolosa (~5km):", cursor.fetchone()[0])
    
    # Let's count how many ways are in Bilbao (-2.9349, 43.2630)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ways
        WHERE ST_DWithin(the_geom, ST_SetSRID(ST_Point(-2.9349, 43.2630), 4326), 0.05)
    """)
    print("Ways in Bilbao (~5km):", cursor.fetchone()[0])
