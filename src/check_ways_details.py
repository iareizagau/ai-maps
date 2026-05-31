import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Let's check if cost and reverse_cost contain very small or zero values or negative values
    cursor.execute("""
        SELECT gid, source, target, cost, reverse_cost, length_m, name, tag_id
        FROM ways
        WHERE source IS NOT NULL AND target IS NOT NULL
        LIMIT 10
    """)
    print("Sample ways:")
    for row in cursor.fetchall():
        print(" -", row)
