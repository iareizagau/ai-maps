-- Scripts para definir costes personalizados en la red de pgRouting
-- Estos costes permiten que el algoritmo elija rutas según el perfil (Bikepacking vs Monte)

-- 1. Añadir columnas de coste específicas
ALTER TABLE pgr_ways ADD COLUMN IF NOT EXISTS bikepacking_cost float8;
ALTER TABLE pgr_ways ADD COLUMN IF NOT EXISTS hiking_cost float8;

-- 2. Inicializar con la longitud real en metros
UPDATE pgr_ways SET bikepacking_cost = length_m, hiking_cost = length_m;

-- 3. Lógica para BIKEPACKING (Priorizar pistas y evitar tráfico)
-- Penalizar carreteras ruidosas/peligrosas (Multiplicamos el coste x 10)
UPDATE pgr_ways SET bikepacking_cost = bikepacking_cost * 10.0 
WHERE tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('primary', 'secondary', 'trunk', 'motorway'));

-- Bonificar vías ciclistas y pistas forestales (Reducimos el coste un 20%)
UPDATE pgr_ways SET bikepacking_cost = bikepacking_cost * 0.8
WHERE tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('track', 'cycleway'));

-- 4. Lógica para MONTE / HIKING
-- Priorizar senderos (paths) y escaleras
UPDATE pgr_ways SET hiking_cost = hiking_cost * 0.5
WHERE tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('path', 'footway', 'steps'));

-- Penalizar caminar por carreteras
UPDATE pgr_ways SET hiking_cost = hiking_cost * 20.0
WHERE tag_id IN (SELECT tag_id FROM configuration WHERE tag_value IN ('primary', 'secondary', 'trunk', 'motorway'));

-- 5. Ejemplo de consulta usando estos costes:
-- SELECT * FROM pgr_dijkstra('SELECT gid as id, source, target, bikepacking_cost as cost FROM pgr_ways', 1, 500, directed := false);
