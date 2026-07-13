import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.db import connection

from apps.mubil.advisor.services import find_nearest_drivable_node, get_commute_route

# Coordinates roughly Beasain to Errenteria
start_lon, start_lat = -2.203, 43.048
end_lon, end_lat = -1.902, 43.313

start_node = find_nearest_drivable_node(start_lon, start_lat)
end_node = find_nearest_drivable_node(end_lon, end_lat)

print("Nearest Nodes found:")
print(" - Start Node (Beasain):", start_node)
print(" - End Node (Errenteria):", end_node)

if start_node and end_node:
    # Let's see if we can do a path without any bbox filter!
    query = """
        SELECT seq, node, edge, cost FROM pgr_dijkstra(
            'SELECT gid as id, source, target, length_m as cost, length_m as reverse_cost FROM ways',
            %s, %s, directed := false
        )
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [start_node, end_node])
        rows = cursor.fetchall()
        print("Dijkstra without bbox filter - segment count:", len(rows))

    # Let's see if we can do a path WITH the bbox filter from get_commute_route!
    res = get_commute_route(start_lon, start_lat, end_lon, end_lat)
    print("get_commute_route result distance:", res["distance_km"])
    print(
        "get_commute_route notes:", res["route_geojson"].get("metadata", {}).get("note")
    )
