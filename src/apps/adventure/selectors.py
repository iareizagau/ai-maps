from django.db import connection
import json

def find_nearest_node(lon, lat, profile='bikepacking'):
    """Encuentra el nodo de la red más cercano a una coordenada, válido para el perfil."""
    cost_column = 'bikepacking_cost' if profile == 'bikepacking' else 'hiking_cost'
    if profile == 'camper':
        cost_column = 'camper_cost'
        
    with connection.cursor() as cursor:
        cursor.execute(f"""
            WITH nearest_edge AS (
                SELECT source, target 
                FROM pgr_ways
                WHERE {cost_column} IS NOT NULL
                ORDER BY the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
                LIMIT 1
            )
            SELECT v.id 
            FROM pgr_ways_vertices_pgr v
            JOIN nearest_edge e ON v.id = e.source OR v.id = e.target
            ORDER BY v.the_geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
            LIMIT 1
        """, [lon, lat, lon, lat])
        row = cursor.fetchone()
        return row[0] if row else None

def get_adventure_route(start_coords, end_coords, profile='bikepacking', scenic=False):
    """
    Calcula la ruta óptima entre dos coordenadas usando pgRouting.
    Perfiles disponibles: 'bikepacking', 'hiking', 'camper'
    """
    start_node = find_nearest_node(start_coords[0], start_coords[1], profile=profile)
    end_node = find_nearest_node(end_coords[0], end_coords[1], profile=profile)

    if not start_node or not end_node:
        return {"error": "No se encontraron nodos cercanos."}

    if profile == 'bikepacking':
        cost_column = 'bikepacking_cost'
    elif profile == 'hiking':
        cost_column = 'hiking_cost'
    else:
        cost_column = 'camper_cost'

    cost_expr = f"{cost_column} as cost"
    if profile == 'camper' and scenic:
        cost_expr = f"CASE WHEN tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN (''motorway'', ''trunk'', ''motorway_link'', ''trunk_link'')) THEN {cost_column} * 20 ELSE {cost_column} END as cost"

    # Bounding box dinámico ampliado para evitar "No se encontró camino" por desvíos grandes
    lon_dist = abs(end_coords[0] - start_coords[0])
    lat_dist = abs(end_coords[1] - start_coords[1])
    
    if profile == 'camper':
        # Las furgonetas camper a menudo requieren grandes desvíos por carreteras principales
        buffer = max(max(lon_dist, lat_dist) * 2.5, 0.2)
    else:
        buffer = max(max(lon_dist, lat_dist) * 1.5, 0.1)

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
            c.tag_value as highway_type,
            ST_Length(pgr_ways.the_geom::geography) as length_m
        FROM pgr_dijkstra(
            'SELECT gid as id, source, target, {cost_expr}
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
    total_distance_m = 0
    for row in rows:
        length_m = row[5]
        total_distance_m += length_m
        features.append({
            "type": "Feature",
            "geometry": json.loads(row[0]),
            "properties": {
                "name": row[1],
                "cost": row[2],
                "agg_cost": row[3],
                "highway_type": row[4],
                "length_m": length_m
            }
        })

    if not features:
        # Para facilitar el diagnóstico, comprobamos si la tabla pgr_ways tiene datos en el bbox
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM pgr_ways WHERE the_geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)")
            ways_count = cursor.fetchone()[0]
        
        # También comprobamos cuántos vértices hay en total
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM pgr_ways_vertices_pgr")
            vertices_count = cursor.fetchone()[0]
            
        return {
            "error": f"No se encontró camino entre los nodos {start_node} y {end_node}. "
                     f"[Diagnóstico: {ways_count} vías en la zona, {vertices_count} vértices en la base de datos]"
        }

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "start_node": start_node,
            "end_node": end_node,
            "total_cost": rows[-1][3] if rows else 0,
            "total_distance_m": total_distance_m,
            "elevation_gain": 0,
            "elevation_loss": 0
        }
    }
