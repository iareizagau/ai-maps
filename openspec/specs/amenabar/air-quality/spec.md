## Purpose

Esta capacidad permite exponer sobre el mapa de Amenabar una capa opcional con las estaciones oficiales de monitoreo de calidad del aire en España (OpenAQ) y sus lecturas más recientes de contaminantes principales, cacheadas localmente para servirse rápido y sin invadir la ficha de cada promoción.

## Requirements

### Requirement: El sistema SHALL mantener un cache local de estaciones OpenAQ de España

El sistema SHALL replicar localmente las estaciones de monitoreo de calidad del aire ubicadas en España (identificador oficial, nombre, ciudad, ubicación geográfica, última lectura por parámetro y timestamp) a partir de la fuente oficial, con sincronización idempotente que acepte reintentos sin duplicar filas. Las estaciones de otros países SHALL quedar excluidas por diseño.

#### Scenario: Primera sincronización desde cero

- **WHEN** se solicita sincronizar y no hay estaciones en el almacén local
- **THEN** el sistema crea una entrada por cada estación de España devuelta por la fuente, con identificador, nombre, ciudad, ubicación en WGS84 y las lecturas más recientes disponibles por parámetro

#### Scenario: Sincronización repetida sin cambios

- **WHEN** se solicita sincronizar y las mismas estaciones ya existen localmente
- **THEN** el sistema actualiza en sitio sin crear filas duplicadas y refresca los valores de lectura si han cambiado

#### Scenario: Estación fuera de España

- **WHEN** la fuente devuelve una estación con país distinto de España
- **THEN** el sistema no la persiste en el almacén local

#### Scenario: Fuente externa indisponible o clave ausente

- **WHEN** la clave de acceso al servicio externo está vacía o la fuente responde con error
- **THEN** el sistema registra el fallo en logs, no corrompe las filas existentes y no propaga el error como crash

### Requirement: La API pública SHALL exponer el cache como endpoint propio

El sistema SHALL proporcionar un endpoint JSON separado de la ficha por promoción que devuelve el conjunto de estaciones España cacheadas con sus últimas lecturas. El endpoint SHALL no requerir identificador de promoción ni paginación, y SHALL ser consultable por cualquier cliente del mapa Amenabar como fuente única de la capa global.

#### Scenario: Cliente solicita todas las estaciones

- **WHEN** un cliente consulta el endpoint de calidad del aire
- **THEN** el sistema devuelve una lista de estaciones con identificador, nombre, coordenadas, parámetros con su lectura más reciente, y timestamp de la medida

#### Scenario: Cache vacío

- **WHEN** no hay estaciones persistidas localmente
- **THEN** el endpoint devuelve una lista vacía con estado 200 (contrato estable, no error)

#### Scenario: El contrato de la ficha por promoción no cambia

- **WHEN** se añade esta capacidad al sistema
- **THEN** el endpoint existente que sirve la ficha por promoción no incluye datos de calidad del aire ni cambia su shape, para que clientes previos sigan funcionando sin tocar código

### Requirement: El mapa público SHALL incluir una capa toggleable con las estaciones

La interfaz del mapa de Amenabar SHALL ofrecer un control que permita activar u ocultar la capa de calidad del aire sin alterar el resto de capas (promociones, radios, servicios OSM). Cuando se active por primera vez, SHALL cargar los datos de forma perezosa y mantenerlos en memoria para activaciones posteriores de la misma sesión.

#### Scenario: Activar la capa por primera vez

- **WHEN** el usuario activa el toggle de calidad del aire con la capa aún no cargada
- **THEN** la interfaz solicita los datos al endpoint una sola vez y pinta las estaciones sobre el mapa

#### Scenario: Reactivar la capa tras haberla ocultado

- **WHEN** el usuario oculta la capa y vuelve a activarla en la misma sesión
- **THEN** la interfaz muestra las estaciones sin volver a solicitar los datos

#### Scenario: Fallo al cargar los datos

- **WHEN** la carga del endpoint falla (red o 5xx)
- **THEN** la interfaz vuelve el toggle a inactivo, registra el error en consola y mantiene el resto del mapa operativo

### Requirement: Las estaciones SHALL representar visualmente la calidad del aire con una escala legible y accesible

El marcador de cada estación SHALL codificar la calidad del aire mediante un color basado en el valor más reciente de PM2.5 según los umbrales WHO 2021 (24h): verde ≤ 12, amarillo ≤ 35, naranja ≤ 55, rojo > 55 µg/m³. Las estaciones sin PM2.5 reciente SHALL mostrarse neutras (gris) para distinguir ausencia de dato. La leyenda SHALL ser visible junto al toggle y legible en pantallas de 375 px de ancho.

#### Scenario: Estación con PM2.5 reciente dentro del rango bueno

- **WHEN** una estación tiene PM2.5 ≤ 12 µg/m³ en su última lectura
- **THEN** el marcador se pinta en verde

#### Scenario: Estación con PM2.5 reciente en rango malo

- **WHEN** una estación tiene PM2.5 > 55 µg/m³ en su última lectura
- **THEN** el marcador se pinta en rojo

#### Scenario: Estación sin lectura de PM2.5

- **WHEN** la estación no publica PM2.5 (pero sí otros parámetros)
- **THEN** el marcador se pinta neutro (gris) y el popup indica los parámetros disponibles

#### Scenario: Click sobre la estación

- **WHEN** el usuario pincha un marcador
- **THEN** la interfaz muestra nombre, parámetros disponibles con su lectura reciente y timestamp relativo, legibles sin desbordamiento a 375 px
