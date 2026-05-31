import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    print("--- Edges connected to 1477582 (Donostia center node) ---")
    cursor.execute("""
        SELECT gid, source, target, name, length_m 
        FROM ways 
        WHERE source = 1477582 OR target = 1477582
    """)
    rows = cursor.fetchall()
    for r in rows:
        print(" -", r)

    print("\n--- Edges connected to reached nodes: 1477345, 1506019, 1506020 ---")
    for node in [1477345, 1506019, 1506020]:
        cursor.execute("""
            SELECT gid, source, target, name, length_m 
            FROM ways 
            WHERE source = %s OR target = %s
        """, [node, node])
        rows = cursor.fetchall()
        print(f"Node {node}:")
        for r in rows:
            print("   -", r)
