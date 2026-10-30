## Purpose

Esta capacidad permite consultar el potencial fotovoltaico anual y mensual de cada promoción de Amenabar sobre su ubicación geográfica, para que la ficha pública muestre un dato objetivo de energía solar aprovechable sin recomputar en cada visita.

## ADDED Requirements

### Requirement: El sistema SHALL calcular el potencial fotovoltaico de una promoción a partir de su ubicación

El sistema SHALL producir, para cada promoción con coordenadas conocidas (`location` no nulo), un conjunto de valores anuales y mensuales de energía fotovoltaica por kWp instalado, basados en una fuente autoritativa (PVGIS v5.3 del JRC de la Comisión Europea) y bajo parámetros estándar documentados (inclinación 30°, acimut sur, pérdidas de sistema 14%, tecnología silicio cristalino, montaje en edificio).

#### Scenario: Cálculo exitoso para una promoción con ubicación

- **WHEN** una promoción tiene coordenadas válidas y el servicio PVGIS responde correctamente
- **THEN** el sistema registra un valor anual `kwh_kwp_year`, los 12 valores mensuales de `kWh/kWp·mes` y la irradiación anual sobre plano inclinado, todos vinculados 1 a 1 con la promoción

#### Scenario: Promoción sin ubicación

- **WHEN** se intenta calcular el potencial para una promoción sin coordenadas
- **THEN** el sistema no crea ningún registro y no lanza error que interrumpa procesos superiores

#### Scenario: Fuente externa no disponible

- **WHEN** la llamada a PVGIS falla con error de red o respuesta no 2xx
- **THEN** el sistema registra el fallo en logs, no crea ni actualiza el registro y no bloquea el flujo que lo invocó

### Requirement: El sistema SHALL cachear el potencial calculado y permitir reingesta controlada

El sistema SHALL persistir el potencial calculado por promoción de forma estable (sin recomputarse en cada petición pública), SHALL conservar el payload original de la fuente externa para auditoría, y SHALL permitir una reingesta explícita total o filtrada por promoción.

#### Scenario: Lecturas repetidas no vuelven a llamar a la fuente externa

- **WHEN** la ficha pública de una promoción se consulta tras un cálculo previo
- **THEN** el sistema sirve los valores desde el almacén local sin invocar la fuente externa

#### Scenario: Reingesta sin forzar respeta datos existentes

- **WHEN** se ejecuta la reingesta sobre un conjunto que ya tiene valores calculados y no se solicita forzado
- **THEN** el sistema deja intactos los registros existentes y solo calcula para promociones sin datos

#### Scenario: Reingesta forzada recalcula

- **WHEN** se ejecuta la reingesta forzada
- **THEN** el sistema sobrescribe los valores existentes con el resultado nuevo

#### Scenario: Reingesta filtrada por una promoción concreta

- **WHEN** se solicita la reingesta restringida al identificador de una promoción
- **THEN** el sistema recalcula únicamente esa promoción y no toca el resto

### Requirement: La ficha pública SHALL exponer los datos solares de la promoción

La respuesta pública que alimenta el panel de una promoción (hoy `GET /amenabar/promociones/<slug>/pois.json`) SHALL incluir un bloque con el valor anual y la serie mensual cuando la promoción tenga potencial calculado, de forma retrocompatible con clientes que ignoren ese bloque.

#### Scenario: Promoción con potencial calculado

- **WHEN** un cliente consulta la ficha pública de una promoción cuyo potencial se ha calculado
- **THEN** la respuesta incluye un bloque identificable que contiene el valor anual `kwh_kwp_year` y la lista de 12 valores mensuales

#### Scenario: Promoción sin potencial calculado

- **WHEN** un cliente consulta la ficha pública de una promoción sin potencial calculado
- **THEN** la respuesta sigue el mismo esquema general pero el bloque solar aparece ausente o nulo, sin romper el resto del contrato

### Requirement: La interfaz de usuario SHALL representar los datos solares de forma legible y accesible

Cuando la ficha de una promoción incluya datos solares, la interfaz pública SHALL presentar el valor anual destacado y una representación gráfica mensual (12 valores) legible en pantallas de 375 px de ancho sin desbordamiento ni truncado, con unidades y periodo visibles, y en el idioma activo del usuario. Si la promoción no tiene datos solares, la interfaz SHALL omitir completamente la sección sin huecos visuales ni etiquetas de "no disponible".

#### Scenario: Promoción con datos — vista móvil 375 px

- **WHEN** el usuario abre la ficha de una promoción con potencial calculado en un ancho de 375 px
- **THEN** la interfaz muestra el valor anual con sus unidades, la serie mensual gráficamente (12 elementos) y una leyenda mínima que identifica qué representa cada eje, sin scroll horizontal

#### Scenario: Promoción sin datos

- **WHEN** el usuario abre la ficha de una promoción sin potencial calculado
- **THEN** la interfaz no muestra la sección solar ni ningún placeholder referido a ella

#### Scenario: Idioma activo del usuario

- **WHEN** el usuario cambia el idioma de la interfaz
- **THEN** las etiquetas de la sección solar (unidades, periodo, meses) se renderizan en el idioma activo según los recursos de traducción del proyecto
