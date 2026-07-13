import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT name, count(*) 
        FROM ways 
        WHERE name LIKE 'N-I%' OR name LIKE 'AP-8%' OR name LIKE 'Autovía%' OR name LIKE 'Autopista%'
        GROUP BY name
        ORDER BY count(*) DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    print("Highway names in database:")
    for r in rows:
        print(" -", r)

    cursor.execute("""
        SELECT count(*) 
        FROM ways 
        WHERE source IS NULL OR target IS NULL
    """)
    nulls = cursor.fetchone()[0]
    print("Ways with NULL source or target:", nulls)
