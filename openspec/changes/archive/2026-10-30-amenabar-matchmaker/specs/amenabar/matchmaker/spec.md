## Purpose

Esta capacidad permite al visitante de la landing de Amenabar describir en lenguaje natural lo que busca ("pareja con dos niños, teletrabajo, costa, 300–400 k, cerca de colegio público") y recibir en respuesta hasta tres promociones rankeadas sobre datos ya cacheados (servicios cercanos, potencial solar, clima, calidad del aire), cada una con un párrafo explicando por qué encaja.

## ADDED Requirements

### Requirement: El sistema SHALL interpretar una descripción libre y traducirla a preferencias estructuradas

El sistema SHALL aceptar un texto libre del usuario y producir un objeto de preferencias con esquema cerrado y conocido (presupuesto, dormitorios mínimos, ciudades deseadas, categorías de servicios cercanos imprescindibles y deseables, preferencia climática, interés por energía solar, interés por calidad del aire, ciudad de destino diario opcional, resumen en una línea). Los valores que no encajen con el esquema SHALL caerse a defaults seguros, nunca romper el flujo.

#### Scenario: Descripción con señales claras

- **WHEN** el usuario escribe un texto que menciona presupuesto, nº de hijos y preferencia de zona
- **THEN** las preferencias resultantes contienen esos valores en los campos correspondientes del esquema

#### Scenario: Valores fuera del esquema

- **WHEN** la fuente externa que extrae preferencias devuelve un valor que no está en el enum permitido para un campo
- **THEN** ese campo recibe el valor por defecto y el resto de la extracción se preserva

#### Scenario: Fuente externa indisponible

- **WHEN** la fuente externa de extracción falla o no responde a tiempo
- **THEN** el sistema aplica una extracción por fallback (parseo keyword mínimo) y continúa, sin bloquear al usuario

### Requirement: El sistema SHALL rankear promociones **únicamente** sobre datos locales, sin delegar la decisión al LLM

El ranking de promociones SHALL ejecutarse como una consulta determinista sobre los datos locales ya cacheados (`Promocion`, `POI`, `SolarPotential`, `PromocionClima`, `AirQualityStation`), sin ninguna llamada a servicio externo. El LLM NO puede añadir, quitar ni reordenar promociones.

#### Scenario: Las promociones del resultado existen en el almacén local

- **WHEN** el sistema devuelve una lista rankeada
- **THEN** cada promoción de la lista corresponde a una fila real de `Promocion` en el almacén local

#### Scenario: Sólo entran promociones disponibles

- **WHEN** se rankea el catálogo
- **THEN** sólo aparecen promociones cuyo `estado` está en {EN_VENTA, PROXIMA}; vendidas y finalizadas quedan fuera

#### Scenario: Promoción sin métricas opcionales

- **WHEN** una promoción no tiene datos de solar, clima o calidad del aire cacheados
- **THEN** el sistema no la excluye por eso: la rankea aplicando sólo los ejes con datos disponibles y degrada su score en los ejes faltantes sin lanzar error

### Requirement: El score SHALL reflejar explícitamente las preferencias extraídas

Cuando el ranking se calcula, cada preferencia activa del usuario SHALL contribuir al score con un peso que mueva el orden de los resultados en la dirección esperada. El sistema SHALL exponer un desglose por eje (distancia a POIs, solar, clima, aire) para que la explicación posterior pueda citarlo.

#### Scenario: Preferencia "soleado" favorece la de mayor potencial solar

- **WHEN** dos promociones comparables sólo difieren en `SolarPotential.kwh_kwp_year` y el usuario expresa preferencia por "soleado"
- **THEN** la promoción con mayor `kwh_kwp_year` queda por delante en el ranking

#### Scenario: Preferencia "aire limpio" usa la estación OpenAQ más cercana

- **WHEN** el usuario expresa preferencia por aire limpio y hay estaciones OpenAQ cacheadas
- **THEN** el eje de aire del score se calcula contra la estación más cercana a cada promoción, no contra una fija

#### Scenario: Preferencia "cerca de colegio" rankea por distancia POI

- **WHEN** el usuario indica que necesita colegio cerca
- **THEN** el eje de servicios del score penaliza las promociones que no tienen un POI de categoría educación en un radio razonable

### Requirement: La explicación por promoción SHALL redactarse sólo sobre datos reales ya rankeados, nunca inventarse

Cuando el sistema produce un párrafo narrativo por promoción, SHALL hacerlo sobre los datos concretos ya seleccionados (nombre, ciudad, métricas del `breakdown`) y SHALL omitir cualquier dato que no esté entre los que se le pasan. Si la generación de la explicación falla o se agota el tiempo, la promoción SHALL mostrarse sin párrafo narrativo, no fallar el flujo entero.

#### Scenario: La explicación cita sólo datos del breakdown

- **WHEN** se genera el párrafo para una promoción con breakdown {distancia_colegio: 350 m, kwh_kwp_year: 1540}
- **THEN** el párrafo puede mencionar colegios y solar, pero no cita precios, rentabilidades u otros datos no incluidos

#### Scenario: Fallo o timeout del generador de explicaciones

- **WHEN** la generación de la explicación para una o más promociones falla
- **THEN** esas promociones se muestran con las cifras del breakdown pero sin párrafo narrativo, y el resto del ranking se renderiza con normalidad

### Requirement: La ficha pública SHALL exponer la búsqueda y los resultados de forma usable y accesible

La landing de Amenabar SHALL ofrecer un acceso visible al match-maker. La página de búsqueda SHALL presentar un formulario con un área de texto libre, enviar la consulta por un flujo que no requiera recarga completa (HTMX u otro) y renderizar los resultados en el mismo contexto como una lista de hasta tres tarjetas legibles en pantallas de 375 px de ancho sin desbordamiento ni truncado. Cada tarjeta SHALL identificar la promoción, mostrar las cifras clave de su breakdown y, cuando esté disponible, el párrafo explicativo, en el idioma activo del usuario.

#### Scenario: Vista móvil 375 px

- **WHEN** el usuario abre la página en un ancho de 375 px y envía una consulta válida
- **THEN** la respuesta renderiza hasta 3 tarjetas apiladas verticalmente, legibles, sin scroll horizontal

#### Scenario: Idioma activo

- **WHEN** el usuario cambia el idioma de la interfaz
- **THEN** las etiquetas del formulario y de las tarjetas se renderizan en el idioma activo según los recursos de traducción del proyecto

#### Scenario: Sin coincidencias

- **WHEN** la consulta no devuelve ninguna promoción compatible (ninguna EN_VENTA/PROXIMA cumple los filtros duros)
- **THEN** la interfaz muestra un mensaje breve explicando que no hay coincidencias y proponiendo relajar criterios, sin ningún resultado inventado
