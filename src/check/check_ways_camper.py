import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT 
            COUNT(*),
            COUNT(camper_cost),
            COUNT(CASE WHEN camper_cost <= 0 THEN 1 END)
        FROM ways
    """)
    row = cursor.fetchone()
    print("Ways camper cost count:")
    print(" - Total rows:", row[0])
    print(" - camper_cost NOT NULL count:", row[1])
    print(" - camper_cost <= 0 count:", row[2])
