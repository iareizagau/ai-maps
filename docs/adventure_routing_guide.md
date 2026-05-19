# Guía de Mantenimiento y Configuración: pgRouting y Enrutamiento de Aventura

Este documento sirve como manual técnico para diagnosticar, configurar y recuperar el motor de enrutamiento y análisis de superficies en el ecosistema **Maps.eus (Adventure)**.

---

## 🔍 1. ¿Qué falló en producción? (Análisis Técnico)

El enrutador de aventura no devolvía caminos y el panel mostraba *"No se encontró camino entre esos puntos"*. Al inspeccionar la consola de red, descubrimos que la API de Django `/api/adventure/route` devolvía un código `200` pero con una lista vacía de tramos (`features: []`).

### Las causas raíz del problema:
1. **La tabla de topología de vértices (`pgr_ways_vertices_pgr`) estaba vacía (0 filas)** en el servidor VPS. pgRouting necesita esta tabla física para encontrar los cruces de caminos más cercanos a las coordenadas del usuario (`find_nearest_node`).
2. **pgRouting 4.0+ eliminó la función heredada `pgr_createTopology`** (la cual fue deprecada en 3.8.0). Intentar ejecutarla en producción arrojó un error de función no encontrada (`function does not exist`).
3. **El backend ignoraba los errores en silencio**: Si un segmento de ruta fallaba por falta de base de datos, el backend hacía un `continue` silencioso devolviendo una lista vacía, ocultando el error al desarrollador y al usuario.
4. **Falta de datos en `adventure_trails`**: La tabla que calcula los tipos de terreno tenía 0 filas en producción, lo cual impedía realizar el fallback de estadísticas en el servidor.
5. **Precisión Errónea de Distancias**: El frontend y el perfil de elevación consumían la columna lógica de dificultad `cost` para calcular distancias, reportando distancias físicas sumamente reducidas e incorrectas (ej. mostrar "5.56 km" en una ruta real de más de 50 km).
6. **Bounding Box restrictivo en Enrutamientos Especiales**: Vías fuertemente penalizadas (por perfil `camper` o configuración de ruta escénica panorámica) forzaban grandes rodeos espaciales que se salían de la caja delimitadora fija (~5km) del enrutador, rompiendo la continuidad lógica del grafo y provocando el fallo `"No se encontró camino"`.
7. **Puntos de Interés (POIs) Vacíos en Vista de Detalle**: Las fuentes de agua potable sólo residían en el modelo heredado `Fountain` (`adventure_fountains`), mientras que la vista detallada de la ruta (`route_detail_view`) requería consultar el nuevo modelo táctico unificado `PointOfInterest` (`adventure_pois`), el cual estaba vacío (0 registros).

---

## 🛠️ 2. Arquitectura de Solución Implementada

Para resolver esto y prevenir futuros fallos ciegos, implementamos la siguiente arquitectura de soluciones:

*   **Propagación de Errores Activa ([api.py](file:///c:/Users/imanol/projects/imanol/saas/maps/src/apps/adventure/api.py))**: Modificado para capturar errores de base de datos y retornarlos al cliente de manera explícita en lugar de omitirlos.
*   **Mensajes de Autodiagnóstico ([selectors.py](file:///c:/Users/imanol/projects/imanol/saas/maps/src/apps/adventure/selectors.py))**: Si el enrutador no encuentra caminos, realiza consultas en caliente y añade estadísticas del estado de la base de datos de producción directamente en el mensaje de error.
*   **Comando de Poblado de Terrenos ([populate_adventure_trails.py](file:///c:/Users/imanol/projects/imanol/saas/maps/src/apps/adventure/management/commands/populate_adventure_trails.py))**: Un comando Django robusto que limpia la tabla `adventure_trails` e inserta los caminos clasificando inteligentemente las superficies en base a sus etiquetas de OSM.
*   **Cálculo Geográfico Preciso (`length_m`)**: Modificamos el SQL de `get_adventure_route` para calcular la longitud real exacta de cada tramo mediante `ST_Length(geometry::geography)` en PostGIS, actualizando la integración del frontend (mapa, barra de estadísticas, eje X del gráfico de perfil y proporciones de asfalto/tierra).
*   **Bounding Box Dinámico según Perfil**: Ajuste inteligente de la caja delimitadora espacial en `selectors.py`. En perfiles de alta tolerancia o vehículos pesados como `camper`, ampliamos el buffer de búsqueda espaciotemporal hasta un factor de **2.5x** (mínimo ~20km) para garantizar margen ante desvíos masivos panorámicos.
*   **Pipeline de POIs Tácticos unificado**: Implementación del modelo `PointOfInterest` (`adventure_pois`) integrando campings de pago (`camp_paid`), zonas de pernocta gratuitas (`camp_free`), refugios/hostales (`shelter`), cafeterías/bares (`cafe`) y estaciones (`station`), junto a las fuentes (`water`).

---

## 🚀 3. Guía de Configuración y Recuperación Paso a Paso (Playbook)

Si se vuelve a importar cartografía OSM, se migra de servidor o se vacía la base de datos, sigue esta secuencia exacta de comandos en el VPS:

### Paso 1: Habilitar el motor pgRouting
Accede a la base de datos de producción y asegúrate de que la extensión espacial pgRouting está activa:
```bash
docker exec -it maps_db_prod psql -U postgres -d maps_db -c "CREATE EXTENSION IF NOT EXISTS pgrouting CASCADE;"
```

### Paso 2: Reconstruir los Vértices Físicos (Topología pgRouting 4.0+)
Dado que `pgr_createTopology` ya no existe, ejecuta esta consulta optimizada que extrae de forma ultra-rápida todos los puntos de inicio/fin de `pgr_ways`, elimina duplicados y los inserta en `pgr_ways_vertices_pgr` (tarda aprox 3 segundos para 1M de registros):
```bash
docker exec -it maps_db_prod psql -U postgres -d maps_db -c "
TRUNCATE TABLE pgr_ways_vertices_pgr CASCADE;

INSERT INTO pgr_ways_vertices_pgr (id, lon, lat, the_geom)
SELECT DISTINCT ON (id) id, lon, lat, the_geom
FROM (
    SELECT 
        source as id,
        ST_X(ST_StartPoint(the_geom))::numeric(11,8) as lon,
        ST_Y(ST_StartPoint(the_geom))::numeric(11,8) as lat,
        ST_SetSRID(ST_StartPoint(the_geom), 4326) as the_geom
    FROM pgr_ways
    UNION ALL
    SELECT 
        target as id,
        ST_X(ST_EndPoint(the_geom))::numeric(11,8) as lon,
        ST_Y(ST_EndPoint(the_geom))::numeric(11,8) as lat,
        ST_SetSRID(ST_EndPoint(the_geom), 4326) as the_geom
    FROM pgr_ways
) sub;
"
```

### Paso 3: Aplicar Costes Dinámicos de Enrutamiento
Ejecuta la calibración de costes de ciclismo y senderismo sobre la red:
```bash
docker exec -it maps_web_prod python manage.py setup_routing_costs
```

### Paso 3.5: Inicializar Costes de Enrutamiento Camper (Overland / Vanlife) [NUEVO]
Ejecuta la calibración de costes específica para vehículos pesados / furgonetas camper sobre el contenedor de base de datos de producción:
```bash
docker exec -it maps_db_prod psql -U postgres -d maps_db -c "
-- 1. Añadir columna si no existe
ALTER TABLE pgr_ways ADD COLUMN IF NOT EXISTS camper_cost double precision;

-- 2. Inicializar con coste de tiempo base (segundos)
UPDATE pgr_ways SET camper_cost = cost_s;

-- 3. Penalizar masivamente (pero mantener conectados) caminos, sendas, aceras y carriles bici
UPDATE pgr_ways 
SET camper_cost = cost_s * 100000 
WHERE tag_id IN (
    SELECT tag_id FROM configuration 
    WHERE tag_value IN ('path', 'steps', 'footway', 'pedestrian', 'cycleway', 'bridleway', 'grade4', 'grade5')
) AND cost_s > 0;

-- 4. Penalizar (multiplicador x20) pistas forestales y caminos de tierra de grado 3 (transitables pero no óptimos)
UPDATE pgr_ways 
SET camper_cost = camper_cost * 20 
WHERE tag_id IN (
    SELECT tag_id FROM configuration 
    WHERE tag_value IN ('track', 'grade3')
);

-- 5. Limpiar valores inválidos o negativos que puedan romper Dijkstra
UPDATE pgr_ways SET camper_cost = NULL WHERE camper_cost < 0;
"
```

### Paso 4: Rellenar la Tabla de Senderos y Terrenos
Lanza nuestro comando de mapeado inteligente de superficies:
```bash
docker exec -it maps_web_prod python manage.py populate_adventure_trails
```

### Paso 5: Poblar Puntos de Interés Enriquecidos (POIs) [NUEVO]
Poblar el ecosistema de POIs (campings, zonas camper, refugios, hostelería, transporte) de forma rápida mediante consulta directa a la API Overpass para Euskadi:
```bash
# 1. Ejecutar la importación remota de POIs de Overpass
docker exec -it maps_web_prod python manage.py import_overpass_pois

# 2. (Opcional) Migrar fuentes ya existentes en el modelo Fountain a la tabla unificada
docker exec -it maps_web_prod python manage.py shell -c "
from apps.adventure.models import Fountain, PointOfInterest
fountains = Fountain.objects.all()
pois = [PointOfInterest(osm_id=f.osm_id, poi_type='water', name=f.name, location=f.location, tags={'description': f.description}) for f in fountains]
PointOfInterest.objects.bulk_create(pois, ignore_conflicts=True)
print('Migración completada con éxito')
"
```

---

## 📊 4. Comandos de Diagnóstico Rápido

Ejecuta estas consultas en el VPS si tienes sospechas de fallos de enrutamiento o inconsistencia de datos:

*   **Comprobar número de vértices cargados**:
    ```bash
    docker exec -it maps_db_prod psql -U postgres -d maps_db -c "SELECT COUNT(*) FROM pgr_ways_vertices_pgr;"
    ```
    *Debería devolver en torno a 370k+ para Euskadi.*

*   **Comprobar caminos de aventura poblados**:
    ```bash
    docker exec -it maps_db_prod psql -U postgres -d maps_db -c "SELECT COUNT(*), surface FROM adventure_trails GROUP BY surface;"
    ```
    *Te mostrará el número de caminos clasificados por asfalto, tierra, etc.*

*   **Comprobar la salud de los Puntos de Interés (POIs)**:
    ```bash
    docker exec -it maps_db_prod psql -U postgres -d maps_db -c "SELECT COUNT(*), poi_type FROM adventure_pois GROUP BY poi_type;"
    ```
    *Muestra la distribución de POIs tácticos cargados (water, shelter, cafe, station, camp_paid, camp_free).*

*   **Simular y depurar consulta de enrutamiento desde la CLI de Django**:
    ```bash
    docker exec -it maps_web_prod python manage.py shell -c "
    from apps.adventure.selectors import get_adventure_route
    print(get_adventure_route([-1.981, 43.318], [-1.99, 43.32], profile='camper'))
    "
    ```
