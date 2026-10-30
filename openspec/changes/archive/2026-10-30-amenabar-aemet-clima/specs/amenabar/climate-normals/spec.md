## Purpose

Esta capacidad permite consultar las normales climatológicas mensuales (temperatura, precipitación y horas de sol) de cada promoción de Amenabar en el periodo de referencia 1991-2020, usando la estación AEMET más próxima dentro de un umbral de distancia aceptable, cacheando el resultado para la ficha pública.

## ADDED Requirements

### Requirement: El sistema SHALL mantener un inventario local de estaciones AEMET

El sistema SHALL replicar localmente el inventario público de estaciones AEMET (identificador oficial, nombre, provincia, altitud y ubicación geográfica) para poder resolver qué estación corresponde a cada promoción sin depender de llamadas externas en caliente. La sincronización SHALL ser idempotente: ejecutarla varias veces no duplica estaciones ni rompe las referencias existentes.

#### Scenario: Primera sincronización desde cero

- **WHEN** se solicita sincronizar el inventario y no existe ninguna estación en el almacén local
- **THEN** el sistema crea una entrada por cada estación devuelta por la fuente oficial, con su identificador, nombre, provincia, altitud y ubicación en WGS84

#### Scenario: Sincronización repetida sin cambios

- **WHEN** se solicita sincronizar el inventario y las mismas estaciones ya existen localmente
- **THEN** el sistema actualiza en sitio sin crear filas duplicadas y preserva las referencias existentes desde las promociones

#### Scenario: Estación nueva o modificada

- **WHEN** la fuente oficial añade una estación nueva o cambia los datos de una existente
- **THEN** el sistema inserta la nueva o actualiza la existente, dejando trazable el estado anterior (payload original persistido para auditoría)

### Requirement: El sistema SHALL calcular el clima de una promoción desde la estación AEMET más cercana dentro del umbral

Para cada promoción con ubicación conocida, el sistema SHALL seleccionar la estación AEMET más cercana en línea recta y aceptarla sólo si la distancia es menor o igual a 50 km. Si se acepta, SHALL registrar las normales mensuales (12 valores de temperatura media °C, precipitación mm y horas de sol) del periodo oficial más reciente, junto con la distancia resuelta y una etiqueta del periodo.

#### Scenario: Estación aceptada dentro del umbral

- **WHEN** la estación más cercana a la promoción está a 50 km o menos y la fuente responde con normales válidas
- **THEN** el sistema persiste las tres series mensuales de 12 valores, la referencia a la estación, la distancia en metros y la etiqueta de periodo

#### Scenario: Ninguna estación dentro del umbral

- **WHEN** la estación más cercana a la promoción está a más de 50 km
- **THEN** el sistema no crea registro climático para esa promoción y no interrumpe los flujos superiores

#### Scenario: Promoción sin ubicación

- **WHEN** se intenta calcular el clima para una promoción sin coordenadas
- **THEN** el sistema no crea registro y no lanza error que detenga procesos de ingesta

#### Scenario: Fuente externa indisponible o clave ausente

- **WHEN** la clave de acceso al servicio externo está vacía o la fuente responde con error
- **THEN** el sistema registra el fallo en logs, no crea ni actualiza el registro climático y no bloquea otras tareas

### Requirement: El sistema SHALL cachear el clima y permitir reingesta controlada

Las normales calculadas SHALL quedar persistidas por promoción y no recomputarse en cada visita pública. El sistema SHALL proporcionar un modo de reingesta explícita que admite forzado total o filtrado por una promoción concreta, con rate-limit entre llamadas al servicio externo.

#### Scenario: Reingesta sin forzar respeta datos existentes

- **WHEN** se ejecuta la reingesta climática sobre un conjunto que ya tiene registros y no se solicita forzado
- **THEN** el sistema deja intactos los registros existentes y sólo recalcula las promociones sin datos climáticos

#### Scenario: Reingesta forzada recalcula

- **WHEN** se ejecuta la reingesta climática en modo forzado
- **THEN** el sistema sobrescribe los registros existentes con el resultado nuevo

#### Scenario: Reingesta filtrada por una promoción

- **WHEN** se solicita la reingesta climática restringida al identificador de una promoción
- **THEN** el sistema recalcula únicamente esa promoción y no toca el resto

### Requirement: La ficha pública SHALL exponer el clima de la promoción de forma retrocompatible

La respuesta pública que alimenta el panel de una promoción SHALL incluir un bloque climático identificable cuando la promoción tenga datos cacheados, con las tres series mensuales, el nombre de la estación de referencia, la distancia resuelta y la etiqueta del periodo. Si la promoción no tiene datos, el bloque SHALL aparecer ausente o nulo sin romper el resto del contrato ni los clientes previos.

#### Scenario: Promoción con datos climáticos

- **WHEN** un cliente consulta la ficha pública de una promoción con registro climático
- **THEN** la respuesta incluye un bloque climático con las tres series de 12 valores, el nombre de la estación, la distancia en metros y la etiqueta del periodo

#### Scenario: Promoción sin datos climáticos

- **WHEN** un cliente consulta la ficha pública de una promoción sin registro climático
- **THEN** la respuesta sigue el mismo esquema general y el bloque climático aparece ausente o nulo, dejando intactos los bloques ya existentes (promoción, servicios, solar)

### Requirement: La interfaz de usuario SHALL representar el clima de forma legible y accesible

Cuando la ficha de una promoción incluya datos climáticos, la interfaz pública SHALL presentar tres mini-climogramas apilados verticalmente (temperatura, precipitación, horas de sol) legibles en pantallas de 375 px de ancho sin desbordamiento, con unidades y periodo visibles, el nombre y distancia de la estación de referencia como contexto, y en el idioma activo del usuario. Si la promoción no tiene datos climáticos, la interfaz SHALL omitir completamente la sección sin huecos visuales ni etiquetas de "no disponible".

#### Scenario: Promoción con datos — vista móvil 375 px

- **WHEN** el usuario abre la ficha de una promoción con clima calculado en un ancho de 375 px
- **THEN** la interfaz muestra las tres series mensuales graficadas verticalmente, con unidades visibles, el nombre de la estación y su distancia, sin scroll horizontal

#### Scenario: Promoción sin datos climáticos

- **WHEN** el usuario abre la ficha de una promoción sin registro climático
- **THEN** la interfaz no muestra la sección climática ni ningún placeholder referido a ella

#### Scenario: Idioma activo del usuario

- **WHEN** el usuario cambia el idioma de la interfaz
- **THEN** las etiquetas de la sección climática (unidades, títulos, periodo, meses) se renderizan en el idioma activo según los recursos de traducción del proyecto
