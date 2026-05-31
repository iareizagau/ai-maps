import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT 
            MIN(ST_X(ST_StartPoint(the_geom))), MAX(ST_X(ST_StartPoint(the_geom))),
            MIN(ST_Y(ST_StartPoint(the_geom))), MAX(ST_Y(ST_StartPoint(the_geom)))
        FROM ways
    """)
    row = cursor.fetchone()
    print("ways bounding box:")
    print(" - Min X (Lng):", row[0])
    print(" - Max X (Lng):", row[1])
    print(" - Min Y (Lat):", row[2])
    print(" - Max Y (Lat):", row[3])
