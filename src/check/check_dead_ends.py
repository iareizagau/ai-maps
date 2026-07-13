import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

for node in [1488217, 1518545]:
    print(f"\n--- Edges for {node} ---")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT gid, source, target, name, length_m 
            FROM ways 
            WHERE source = %s OR target = %s
        """,
            [node, node],
        )

        rows = cursor.fetchall()
        for r in rows:
            print(" -", r)
