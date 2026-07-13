#!/usr/bin/env python
"""
Script de importacion progresiva y escalable para pgRouting (Maps.eus).
Divide una region/pais en una cuadricula de teselas (tiles) pequenas,
las extrae y filtra progresivamente, y las añade a la base de datos
sin saturar la memoria RAM del contenedor Docker.

Uso:
    python scripts/import_progressive.py --pbf /tmp/switzerland-latest.osm.pbf --bbox 5.9,45.8,10.5,47.8 --step 0.5
"""

import argparse
import subprocess
import sys

# Configurar UTF-8 en Windows para evitar fallos de codificacion
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def run_cmd(cmd, shell=True):
    print(f" [RUN] Ejecutando: {cmd}")
    result = subprocess.run(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode != 0:
        print(f" [ERROR] ({result.returncode}): {result.stderr}")
    return result.returncode == 0, result.stdout, result.stderr


def main():
    parser = argparse.ArgumentParser(
        description="Importacion progresiva de carreteras en pgRouting"
    )
    parser.add_argument(
        "--pbf",
        type=str,
        required=True,
        help="Ruta al archivo PBF dentro del contenedor maps_db (ej: /tmp/switzerland-latest.osm.pbf)",
    )
    parser.add_argument(
        "--bbox",
        type=str,
        required=True,
        help="Bounding box global (min_lon,min_lat,max_lon,max_lat)",
    )
    parser.add_argument(
        "--step",
        type=float,
        default=0.5,
        help="Tamano de la tesela en grados (defecto: 0.5)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Vaciar las tablas antes de comenzar la importacion",
    )

    args = parser.parse_args()

    # 1. Parsear el Bbox global
    try:
        min_lon, min_lat, max_lon, max_lat = map(float, args.bbox.split(","))
    except ValueError:
        print(
            " [ERROR] Formato de BBOX invalido. Debe ser: min_lon,min_lat,max_lon,max_lat"
        )
        sys.exit(1)

    print("=" * 60)
    print(" [START] INICIANDO IMPORTACION PROGRESIVA Y ESCALABLE")
    print(f"   Archivo PBF: {args.pbf}")
    print(f"   BBox global: {args.bbox}")
    print(f"   Tamano paso: {args.step} grados")
    print("=" * 60)

    # 2. Si se pide --clean, vaciar las tablas al inicio
    if args.clean:
        print(" [CLEAN] Vaciando tablas existentes de pgRouting...")
        clean_cmd = (
            'docker exec maps_db psql -U postgres -d maps_db -c "'
            "TRUNCATE TABLE ways CASCADE; "
            'TRUNCATE TABLE ways_vertices_pgr CASCADE;"'
        )
        run_cmd(clean_cmd)

    # Crear indices de rendimiento en la tabla ways para acelerar las comparaciones geometricas de osm2pgrouting
    print(" [INDEX] Asegurando indices de rendimiento en la tabla ways...")
    index_cmd = (
        'docker exec maps_db psql -U postgres -d maps_db -c "'
        "CREATE INDEX IF NOT EXISTS ways_the_geom_idx ON ways USING GIST (the_geom); "
        'CREATE INDEX IF NOT EXISTS ways_osm_id_idx ON ways (osm_id);"'
    )
    run_cmd(index_cmd)

    # 3. Generar la cuadricula de teselas
    tiles = []
    curr_lat = min_lat
    while curr_lat < max_lat:
        next_lat = min(curr_lat + args.step, max_lat)
        curr_lon = min_lon
        while curr_lon < max_lon:
            next_lon = min(curr_lon + args.step, max_lon)
            tiles.append((curr_lon, curr_lat, next_lon, next_lat))
            curr_lon = next_lon
        curr_lat = next_lat

    total_tiles = len(tiles)
    print(f" [LIST] Total de teselas generadas a procesar: {total_tiles}")

    successful_tiles = 0

    for idx, (t_min_lon, t_min_lat, t_max_lon, t_max_lat) in enumerate(tiles):
        tile_bbox = f"{t_min_lon:.4f},{t_min_lat:.4f},{t_max_lon:.4f},{t_max_lat:.4f}"
        print(f"\n [STEP] [{idx + 1}/{total_tiles}] Procesando tesela: {tile_bbox}...")

        # A. Recortar la tesela a formato o5m (rapido y compacto)
        clip_cmd = (
            f'docker exec maps_db sh -c "'
            f'osmconvert {args.pbf} -b={tile_bbox} --out-o5m -o=/tmp/tile.o5m"'
        )
        ok, _, err = run_cmd(clip_cmd)
        if not ok:
            print(f" [WARN] Error al recortar tesela {tile_bbox}. Saltando...")
            continue

        # B. Filtrar unicamente las carreteras (highway)
        filter_cmd = (
            'docker exec maps_db sh -c "'
            "osmfilter /tmp/tile.o5m --keep='highway=' -o=/tmp/tile_roads.osm\""
        )
        ok, _, _ = run_cmd(filter_cmd)
        if not ok:
            print(
                f" [WARN] Error al filtrar carreteras de la tesela {tile_bbox}. Saltando..."
            )
            continue

        # C. Comprobar si la tesela contiene datos
        size_cmd = "docker exec maps_db ls -lh /tmp/tile_roads.osm"
        ok, out, _ = run_cmd(size_cmd)
        if " 0 " in out or " 0B " in out:
            print(f" [INFO] La tesela {tile_bbox} no contiene carreteras. Saltando...")
            continue

        # D. Importar a la base de datos sin limpiar (modo Append)
        import_cmd = (
            "docker exec maps_db osm2pgrouting "
            "-f /tmp/tile_roads.osm "
            "-c /usr/share/osm2pgrouting/mapconfig.xml "
            "-d maps_db -U postgres -h localhost -p 5432 -W postgres_password"
        )
        ok, _, _ = run_cmd(import_cmd)
        if ok:
            successful_tiles += 1
            print(f" [OK] Tesela {tile_bbox} importada con exito.")
        else:
            print(f" [ERROR] Error al importar la tesela {tile_bbox} en pgRouting.")

    print("\n" + "=" * 60)
    print(" [DEDUP] LIMPIANDO DUPLICADOS EN LA BASE DE DATOS...")
    # Eliminar carreteras duplicadas que se solapan en los bordes de las teselas usando un join ultra-rapido
    dedup_cmd = (
        'docker exec maps_db psql -U postgres -d maps_db -c "'
        'DELETE FROM ways a USING ways b WHERE a.osm_id = b.osm_id AND a.gid > b.gid;"'
    )
    run_cmd(dedup_cmd)

    print("\n [SYNC] SINCRONIZANDO TABLA DE ENRUTAMIENTO pgr_ways...")
    sync_cmd = (
        'docker exec maps_db psql -U postgres -d maps_db -c "'
        "TRUNCATE TABLE pgr_ways CASCADE; "
        "INSERT INTO pgr_ways (gid, length, length_m, name, source, target, source_osm, target_osm, cost, reverse_cost, cost_s, reverse_cost_s, rule, one_way, oneway, x1, y1, x2, y2, maxspeed_forward, maxspeed_backward, priority, the_geom, tag_id) "
        "SELECT gid, length, length_m, name, source, target, source_osm, target_osm, cost, reverse_cost, cost_s, reverse_cost_s, rule, one_way, oneway, x1, y1, x2, y2, maxspeed_forward, maxspeed_backward, priority, the_geom, tag_id "
        'FROM ways;"'
    )
    run_cmd(sync_cmd)

    print("\n [GEOM] RECONSTRUYENDO TOPOLOGIA DE VERTICES (pgRouting 4.0+)...")
    topology_cmd = (
        'docker exec maps_db psql -U postgres -d maps_db -c "'
        "TRUNCATE TABLE pgr_ways_vertices_pgr CASCADE; "
        "INSERT INTO pgr_ways_vertices_pgr (id, lon, lat, the_geom) "
        "SELECT DISTINCT ON (id) id, lon, lat, the_geom "
        "FROM ( "
        "    SELECT source as id, ST_X(ST_StartPoint(the_geom))::numeric(11,8) as lon, "
        "           ST_Y(ST_StartPoint(the_geom))::numeric(11,8) as lat, ST_SetSRID(ST_StartPoint(the_geom), 4326) as the_geom "
        "    FROM ways "
        "    UNION ALL "
        "    SELECT target as id, ST_X(ST_EndPoint(the_geom))::numeric(11,8) as lon, "
        "           ST_Y(ST_EndPoint(the_geom))::numeric(11,8) as lat, ST_SetSRID(ST_EndPoint(the_geom), 4326) as the_geom "
        "    FROM ways "
        ') sub;"'
    )
    run_cmd(topology_cmd)

    print(
        "\n [COST] CALIBRANDO COSTES DE ENRUTAMIENTO (Bikepacking / Hiking / Camper)..."
    )
    # Configurar costes de bikepacking y hiking en Django
    run_cmd("docker exec maps_web python manage.py setup_routing_costs")

    # Configurar costes especificos para furgonetas Camper
    camper_costs_cmd = (
        'docker exec maps_db psql -U postgres -d maps_db -c "'
        "ALTER TABLE pgr_ways ADD COLUMN IF NOT EXISTS camper_cost double precision; "
        "UPDATE pgr_ways SET camper_cost = cost_s; "
        "UPDATE pgr_ways SET camper_cost = cost_s * 100000 WHERE tag_id IN ("
        "    SELECT tag_id FROM configuration WHERE tag_value IN ('path', 'steps', 'footway', 'pedestrian', 'cycleway', 'bridleway', 'grade4', 'grade5')"
        ") AND cost_s > 0; "
        "UPDATE pgr_ways SET camper_cost = camper_cost * 20 WHERE tag_id IN ("
        "    SELECT tag_id FROM configuration WHERE tag_value IN ('track', 'grade3')"
        "); "
        'UPDATE pgr_ways SET camper_cost = NULL WHERE camper_cost < 0;"'
    )
    run_cmd(camper_costs_cmd)

    print("\n [TRAIL] CLASIFICANDO TIPOS DE TERRENOS DE SENDEROS...")
    run_cmd("docker exec maps_web python manage.py populate_adventure_trails")

    print("=" * 60)
    print(" [DONE] PROCESO COMPLETADO CON EXITO!")
    print(f"   Teselas procesadas con exito: {successful_tiles}/{total_tiles}")
    print("=" * 60)


if __name__ == "__main__":
    main()
