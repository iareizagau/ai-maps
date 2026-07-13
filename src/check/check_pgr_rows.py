import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM ways")
    print("ways count:", cursor.fetchone()[0])

    try:
        cursor.execute("SELECT COUNT(*) FROM pgr_ways")
        print("pgr_ways count:", cursor.fetchone()[0])
    except Exception as e:
        print("pgr_ways count failed:", e)

    try:
        cursor.execute("SELECT gid, source, target, cost FROM ways LIMIT 3")
        print("ways rows:", cursor.fetchall())
    except Exception as e:
        print("ways limit failed:", e)

    try:
        cursor.execute("SELECT gid, source, target, cost FROM pgr_ways LIMIT 3")
        print("pgr_ways rows:", cursor.fetchall())
    except Exception as e:
        print("pgr_ways limit failed:", e)
