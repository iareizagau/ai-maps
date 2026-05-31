import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT gid, source, target, length_m, name 
        FROM ways 
        ORDER BY gid ASC 
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("--- Sample ways rows ---")
    for r in rows:
        print(" -", r)

    cursor.execute("""
        SELECT id, ST_AsText(the_geom) 
        FROM ways_vertices_pgr 
        ORDER BY id ASC 
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("\n--- Sample vertices rows ---")
    for r in rows:
        print(" -", r)

    # Let's count how many distinct source values actually exist in ways_vertices_pgr!
    cursor.execute("""
        SELECT count(*) 
        FROM ways w 
        LEFT JOIN ways_vertices_pgr v ON w.source = v.id 
        WHERE v.id IS NULL
    """)
    missing_sources = cursor.fetchone()[0]
    print(f"\nWays with source vertex NOT in ways_vertices_pgr: {missing_sources}")

    cursor.execute("""
        SELECT count(*) 
        FROM ways w 
        LEFT JOIN ways_vertices_pgr v ON w.target = v.id 
        WHERE v.id IS NULL
    """)
    missing_targets = cursor.fetchone()[0]
    print(f"Ways with target vertex NOT in ways_vertices_pgr: {missing_targets}")
