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

    if start_node == end_node:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {
                "start_node": start_node,
                "end_node": end_node,
                "total_cost": 0.0,
                "total_distance_m": 0.0,
                "elevation_gain": 0.0,
                "elevation_loss": 0.0
            }
        }

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

def get_vanlife_tsp_route(waypoints, pernocta_preference='both', max_driving_hours=3.0, vehicle_height=2.0, vehicle_width=1.9, scenic=False):
    """
    Calcula la ruta circular óptima (TSP) que visita todos los waypoints para una furgoneta camper,
    aplicando restricciones de dimensiones de vehículo, modo escénico y sugiriendo paradas de pernocta en ruta.
    """
    from apps.adventure.models import PointOfInterest
    from django.contrib.gis.geos import LineString, MultiLineString, Point
    
    # 1. Encontrar nodos de pgRouting más cercanos a cada coordenada con comprobación de cercanía
    nodes = []
    for idx, coord in enumerate(waypoints):
        node = find_nearest_node(coord[0], coord[1], profile='camper')
        if not node:
            return {"error": f"No se pudo encontrar ningún nodo de carretera cercano para el punto #{idx+1} ({coord[1]}, {coord[0]})."}
            
        # Comprobar si el nodo encontrado está demasiado lejos (> 0.15 grados, aprox 15-17 km)
        # Esto indica que se ha hecho clic en una zona sin red de pgRouting cargada (ej: Francia, Suiza)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT ST_Distance(the_geom, ST_SetSRID(ST_Point(%s, %s), 4326))
                FROM pgr_ways_vertices_pgr
                WHERE id = %s
            """, [coord[0], coord[1], node])
            row = cursor.fetchone()
            if row and row[0] > 0.15:
                distance_km = round(row[0] * 111.32, 1)
                return {
                    "error": f"El punto #{idx+1} ({coord[1]}, {coord[0]}) está a {distance_km} km de la carretera activa más cercana. "
                             f"Diagnóstico: Has seleccionado un punto en una región exterior (como Francia, Suiza o España exterior) "
                             f"donde aún no se han cargado las carreteras en la base de datos de pgRouting. "
                             f"Por favor, limita tus puntos a la zona con cartografía activa (actualmente Euskadi / País Vasco)."
                }
        nodes.append(node)
            
    if len(nodes) < 2:
        return {"error": "Se necesitan al menos 2 puntos de paso válidos para calcular la ruta."}
        
    n_nodes = len(nodes)
    
    # 2. Configurar coste dinámico basado en dimensiones y modo escénico
    cost_column = 'camper_cost'
    cost_expr = f"{cost_column} as cost"
    
    if scenic:
        cost_expr = f"CASE WHEN tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('motorway', 'trunk', 'motorway_link', 'trunk_link')) THEN {cost_column} * 15 ELSE {cost_column} END as cost"
        
    if vehicle_height > 2.6 or vehicle_width > 2.1:
        # Gran Volumen: Penalizar fuertemente caminos rurales, pistas de tierra y vías residenciales estrechas
        cost_expr = f"""
            CASE 
                WHEN tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('track', 'living_street', 'service')) THEN {cost_column} * 10
                WHEN tag_id IN (SELECT tag_id FROM configuration WHERE tag_value = 'residential') THEN {cost_column} * 2
                ELSE ({cost_expr})
            END
        """
    elif vehicle_height > 2.0 or vehicle_width > 1.9:
        # Furgoneta Mediana: Evitar pistas forestales complejas y living_streets
        cost_expr = f"""
            CASE 
                WHEN tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('track', 'living_street')) THEN {cost_column} * 4
                ELSE ({cost_expr})
            END
        """
        
    # Bounding box dinámico ampliado conteniendo todos los puntos
    lngs = [p[0] for p in waypoints]
    lats = [p[1] for p in waypoints]
    min_lon, max_lon = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)
    buffer = 1.0 # Buffer generoso de 1 grado
    
    min_lon -= buffer
    max_lon += buffer
    min_lat -= buffer
    max_lat += buffer
    
    bbox_filter = f"AND the_geom && ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)"
    
    # 3. Calcular la matriz de costes por pares con pgr_dijkstraCost
    vids_sql = ",".join(str(n) for n in nodes)
    query_cost = f"""
        SELECT start_vid, end_vid, agg_cost FROM pgr_dijkstraCost(
            'SELECT gid as id, source, target, {cost_expr}
             FROM pgr_ways
             WHERE {cost_column} IS NOT NULL {bbox_filter}',
            ARRAY[{vids_sql}], ARRAY[{vids_sql}], directed := false
        )
    """
    
    matrix = [[float('inf')] * n_nodes for _ in range(n_nodes)]
    for i in range(n_nodes):
        matrix[i][i] = 0.0
        
    with connection.cursor() as cursor:
        cursor.execute(query_cost)
        rows = cursor.fetchall()
        for start_vid, end_vid, agg_cost in rows:
            try:
                i = nodes.index(start_vid)
                j = nodes.index(end_vid)
                matrix[i][j] = agg_cost
                matrix[j][i] = agg_cost
            except ValueError:
                continue
                
    # 4. Solucionador TSP de Bucle Cerrado (Held-Karp en Python)
    memo = {}
    
    def tsp(mask, last):
        if mask == (1 << n_nodes) - 1:
            return matrix[last][0], 0
            
        state = (mask, last)
        if state in memo:
            return memo[state]
            
        min_cost = float('inf')
        best_next = -1
        
        for nxt in range(n_nodes):
            if not (mask & (1 << nxt)):
                cost = matrix[last][nxt] + tsp(mask | (1 << nxt), nxt)[0]
                if cost < min_cost:
                    min_cost = cost
                    best_next = nxt
                    
        memo[state] = (min_cost, best_next)
        return min_cost, best_next
        
    # Reconstrucción del orden óptimo de índices
    mask = 1
    curr = 0
    path_indices = [0]
    while len(path_indices) < n_nodes:
        _, nxt = tsp(mask, curr)
        if nxt == -1:
            break
        path_indices.append(nxt)
        mask |= (1 << nxt)
        curr = nxt
    path_indices.append(0)
    
    opt_sequence = [nodes[idx] for idx in path_indices]
    
    # 5. Generar geometrías detalladas tramo a tramo
    features = []
    total_distance_m = 0
    
    for i in range(len(opt_sequence) - 1):
        if opt_sequence[i] == opt_sequence[i+1]:
            continue
        query_seg = f"""
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
            cursor.execute(query_seg, [opt_sequence[i], opt_sequence[i+1]])
            seg_rows = cursor.fetchall()
            
        if not seg_rows:
            w_idx_start = path_indices[i]
            w_idx_end = path_indices[i+1]
            coord_start = waypoints[w_idx_start]
            coord_end = waypoints[w_idx_end]
            return {
                "error": f"No se pudo encontrar una ruta por carretera transitable entre el punto #{w_idx_start+1} ({coord_start[1]}, {coord_start[0]}) "
                         f"y el punto #{w_idx_end+1} ({coord_end[1]}, {coord_end[0]}). "
                         f"Diagnóstico: Has seleccionado puntos desconectados de la red de carreteras actual. "
                         f"Esto suele deberse a que uno o ambos puntos están fuera de la región cartográfica cargada "
                         f"(actualmente Euskadi / País Vasco)."
            }
            
        for row in seg_rows:
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
                    "length_m": length_m,
                    "segment_index": i
                }
            })
            
    if not features:
        return {"error": "No se pudo trazar la geometría física de los caminos para el bucle circular."}
        
    # 6. Búsqueda de POIs tácticos cercanos en corredor de 2 km (0.018 grados)
    lines = []
    for f in features:
        lines.append(LineString(f['geometry']['coordinates']))
    route_geom = MultiLineString(*lines)
    
    pois = PointOfInterest.objects.filter(location__dwithin=(route_geom, 0.018))
    
    poi_list = []
    for p in pois:
        if p.poi_type == 'camp_free' and pernocta_preference == 'paid':
            continue
        if p.poi_type == 'camp_paid' and pernocta_preference == 'free':
            continue
            
        poi_list.append({
            "id": p.id,
            "poi_type": p.poi_type,
            "poi_type_display": p.get_poi_type_display(),
            "name": p.name or p.get_poi_type_display(),
            "location": [p.location.x, p.location.y],
            "tags": p.tags
        })
        
    # 7. Segmentación diaria por presupuesto de horas (Velocidad camper promedio: 60 km/h)
    max_driving_distance_m = max_driving_hours * 60000.0
    daily_stages = []
    current_stage_dist = 0
    current_day = 1
    
    for f in features:
        length_m = f['properties']['length_m']
        current_stage_dist += length_m
        
        if current_stage_dist >= max_driving_distance_m:
            coord = f['geometry']['coordinates'][0]
            pnt = Point(coord[0], coord[1], srid=4326)
            
            pernoctas = PointOfInterest.objects.filter(poi_type__in=['camp_free', 'camp_paid'])
            if pernocta_preference == 'free':
                pernoctas = pernoctas.filter(poi_type='camp_free')
            elif pernocta_preference == 'paid':
                pernoctas = pernoctas.filter(poi_type='camp_paid')
                
            closest_options = sorted(pernoctas, key=lambda p: p.location.distance(pnt))[:3]
            options_list = []
            
            for op in closest_options:
                options_list.append({
                    "id": op.id,
                    "name": op.name or op.get_poi_type_display(),
                    "poi_type": op.poi_type,
                    "poi_type_display": op.get_poi_type_display(),
                    "location": [op.location.x, op.location.y],
                    "distance_km": round((op.location.distance(pnt) * 111.32), 2)
                })
                
            daily_stages.append({
                "day": current_day,
                "distance_km": round(current_stage_dist / 1000.0, 2),
                "stop_coordinate": coord,
                "recommended_overnights": options_list
            })
            
            current_stage_dist = 0
            current_day += 1
            
    if current_stage_dist > 0:
        daily_stages.append({
            "day": current_day,
            "distance_km": round(current_stage_dist / 1000.0, 2),
            "stop_coordinate": waypoints[0],
            "recommended_overnights": []
        })
        
    return {
        "route_geojson": {
            "type": "FeatureCollection",
            "features": features
        },
        "waypoints_optimal_order": [waypoints[idx] for idx in path_indices[:-1]],
        "pois": poi_list,
        "daily_stages": daily_stages,
        "metadata": {
            "total_distance_km": round(total_distance_m / 1000.0, 2),
            "total_driving_time_hours": round((total_distance_m / 60000.0) / 1.0, 2)
        }
    }
