from django.db import connection
import json

def find_nearest_node(lon, lat):
    """Encuentra el nodo de la red más cercano a una coordenada."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM pgr_ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
            LIMIT 1
        """, [lon, lat])
        row = cursor.fetchone()
        return row[0] if row else None

def get_adventure_route(start_coords, end_coords, profile='bikepacking'):
    """
    Calcula la ruta óptima entre dos coordenadas usando pgRouting.
    Perfiles disponibles: 'bikepacking', 'hiking'

    IMPORTANTE: el subquery de pgr_dijkstra usa un filtro por bounding box
    para evitar escanear la tabla completa (989K filas para España).
    Sin ese filtro, la query tarda >30s y gunicorn devuelve 502.
    """
    start_node = find_nearest_node(start_coords[0], start_coords[1])
    end_node = find_nearest_node(end_coords[0], end_coords[1])

    if not start_node or not end_node:
        return {"error": "No se encontraron nodos cercanos."}

    cost_column = 'bikepacking_cost' if profile == 'bikepacking' else 'hiking_cost'

    # Bounding box dinámico: buffer = 1.5x la distancia entre puntos, mínimo 0.05° (~5km)
    lon_dist = abs(end_coords[0] - start_coords[0])
    lat_dist = abs(end_coords[1] - start_coords[1])
    buffer = max(max(lon_dist, lat_dist) * 1.5, 0.05)

    min_lon = min(start_coords[0], end_coords[0]) - buffer
    max_lon = max(start_coords[0], end_coords[0]) + buffer
    min_lat = min(start_coords[1], end_coords[1]) - buffer
    max_lat = max(start_coords[1], end_coords[1]) + buffer

    # Los valores del bbox son floats Python — seguros para interpolar directamente
    bbox_filter = (
        f"AND the_geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)"
    )

    query = f"""
        SELECT
            ST_AsGeoJSON(pgr_ways.the_geom) as geometry,
            pgr_ways.name,
            di.cost,
            di.agg_cost,
            c.tag_value as highway_type
        FROM pgr_dijkstra(
            'SELECT gid as id, source, target, {cost_column} as cost
             FROM pgr_ways
             WHERE {cost_column} IS NOT NULL {bbox_filter}',
            %s, %s, directed := false
        ) AS di
        JOIN pgr_ways ON di.edge = pgr_ways.gid
        JOIN configuration c ON pgr_ways.tag_id = c.tag_id
        ORDER BY di.seq
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [start_node, end_node])
        rows = cursor.fetchall()

    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "geometry": json.loads(row[0]),
            "properties": {
                "name": row[1],
                "cost": row[2],
                "agg_cost": row[3],
                "highway_type": row[4]
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "start_node": start_node,
            "end_node": end_node,
            "total_cost": rows[-1][3] if rows else 0,
            "elevation_gain": 0,
            "elevation_loss": 0
        }
    }
