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

---

## 🛠️ 2. Arquitectura de Solución Implementada

Para resolver esto y prevenir futuros fallos ciegos, implementamos tres pilares en el código:

*   **Propagación de Errores Activa ([api.py](file:///c:/Users/imanol/projects/imanol/saas/maps/src/apps/adventure/api.py))**: Modificado para capturar errores de base de datos y retornarlos al cliente de manera explícita en lugar de omitirlos.
*   **Mensajes de Autodiagnóstico ([selectors.py](file:///c:/Users/imanol/projects/imanol/saas/maps/src/apps/adventure/selectors.py))**: Si el enrutador no encuentra caminos, realiza consultas en caliente y añade estadísticas del estado de la base de datos de producción directamente en el mensaje de error.
*   **Comando de Poblado de Terrenos ([populate_adventure_trails.py](file:///c:/Users/imanol/projects/imanol/saas/maps/src/apps/adventure/management/commands/populate_adventure_trails.py))**: Un comando Django robusto que limpia la tabla `adventure_trails` e inserta los caminos clasificando inteligentemente las superficies en base a sus etiquetas de OSM.

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

### Paso 4: Rellenar la Tabla de Senderos y Terrenos
Lanza nuestro comando de mapeado inteligente de superficies:
```bash
docker exec -it maps_web_prod python manage.py populate_adventure_trails
```

---

## 📊 4. Comandos de Diagnóstico Rápido

Ejecuta estas consultas en el VPS si tienes sospechas de fallos de enrutamiento:

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
