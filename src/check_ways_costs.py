import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT 
            MIN(cost), MAX(cost), COUNT(CASE WHEN cost <= 0 THEN 1 END),
            MIN(reverse_cost), MAX(reverse_cost), COUNT(CASE WHEN reverse_cost <= 0 THEN 1 END)
        FROM ways
    """)
    row = cursor.fetchone()
    print("Ways costs statistics:")
    print(" - Min cost:", row[0])
    print(" - Max cost:", row[1])
    print(" - Cost <= 0 count:", row[2])
    print(" - Min reverse_cost:", row[3])
    print(" - Max reverse_cost:", row[4])
    print(" - Reverse_cost <= 0 count:", row[5])
