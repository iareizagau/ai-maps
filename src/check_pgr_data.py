import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(cost) as c,
            COUNT(reverse_cost) as rc
        FROM ways
    """)
    row = cursor.fetchone()
    print("ways counts:")
    print(" - Total rows:", row[0])
    print(" - cost:", row[1])
    print(" - reverse_cost:", row[2])
