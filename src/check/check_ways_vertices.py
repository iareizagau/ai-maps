import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='ways_vertices_pgr'")
    cols = cursor.fetchall()
    print("ways_vertices_pgr columns:")
    for c, t in sorted(cols):
        print(f" - {c}: {t}")
