## Purpose

Esta capacidad reúne los datos que necesita el asistente cada semana: los 15 partidos de la jornada, el histórico de resultados y cuotas, las cuotas de la semana y los resultados finales. Todo viene de fuentes abiertas y gratuitas o de una entrada manual mínima.

## ADDED Requirements

### Requirement: El sistema SHALL mantener un catálogo de equipos con alias

El sistema SHALL guardar cada equipo una sola vez, con su nombre visible y los alias con los que aparece en cada fuente de datos. Los datos de distintas fuentes SHALL asociarse al mismo equipo a través de esos alias.

#### Scenario: Equipo con nombres distintos en dos fuentes

- **WHEN** una fuente nombra al equipo "Ath Bilbao" y el usuario lo selecciona como "Athletic Club"
- **THEN** ambos nombres se resuelven al mismo equipo y su histórico se usa en el pronóstico

#### Scenario: Nombre desconocido en una ingesta

- **WHEN** una fila de una fuente trae un nombre que no coincide con ningún equipo ni alias
- **THEN** la ingesta crea el equipo con ese nombre como alias, lo registra en el log y continúa con el resto de filas

### Requirement: El usuario SHALL poder dar de alta la jornada con sus 15 partidos

El sistema SHALL ofrecer un formulario para crear una jornada con fecha de cierre y exactamente 15 partidos ordenados (posiciones 1–14 y el Pleno al 15). Cada partido tiene local y visitante, elegidos del catálogo o escritos como texto libre si el equipo no está en él.

#### Scenario: Alta completa

- **WHEN** el usuario envía la jornada con 15 partidos válidos
- **THEN** la jornada queda guardada con los partidos en su orden y el sistema lanza el cálculo del pronóstico

#### Scenario: Jornada incompleta o duplicada

- **WHEN** faltan partidos, se repite una posición o local y visitante son el mismo equipo
- **THEN** el formulario rechaza el envío y señala la fila errónea sin perder lo ya escrito

#### Scenario: Partido de equipos fuera del catálogo

- **WHEN** un partido usa un equipo escrito como texto libre (por ejemplo, una selección)
- **THEN** el partido se guarda marcado como "sin histórico" y no bloquea el alta

### Requirement: El sistema SHALL ingerir histórico de resultados y cuotas desde una fuente abierta

El sistema SHALL importar, por temporada y división (Primera y Segunda), los resultados finales con goles y las cuotas 1X2 de cierre disponibles. La ingesta SHALL ser idempotente: al reimportar una temporada se actualizan sus filas sin duplicarlas.

#### Scenario: Primera importación de una temporada

- **WHEN** se importa una temporada que no estaba en el almacén
- **THEN** se guardan todos sus partidos con fecha, equipos, goles y, si existen, cuotas de cierre

#### Scenario: Reimportación

- **WHEN** se importa otra vez una temporada ya guardada
- **THEN** el número de partidos guardados no cambia y los valores corregidos en la fuente quedan actualizados

#### Scenario: Fuente no disponible

- **WHEN** la descarga falla o devuelve un formato inesperado
- **THEN** la ingesta termina con error explícito en el log y no deja datos a medias de esa temporada

### Requirement: El sistema SHALL obtener las cuotas de la semana para los partidos de la jornada

El sistema SHALL buscar cuotas 1X2 previas al partido en la fuente abierta y asociarlas a cada partido de la jornada por equipos y fecha. Las cuotas SHALL guardarse con su momento de captura. Si no hay cuota para un partido, el partido queda sin ella y nada se bloquea.

#### Scenario: Cuotas disponibles

- **WHEN** la fuente publica cuotas para un partido de la jornada
- **THEN** el partido queda con cuotas 1/X/2 y la hora de captura

#### Scenario: Cuotas ausentes

- **WHEN** la fuente no publica cuotas para un partido
- **THEN** el partido queda sin cuotas y el pronóstico usa la siguiente fuente disponible

### Requirement: El sistema SHALL registrar los resultados finales de la jornada

El sistema SHALL poder completar los resultados de los 15 partidos, desde la fuente abierta o a mano, incluidos los goles de cada equipo del Pleno al 15.

#### Scenario: Resultados desde la fuente

- **WHEN** la fuente publica los resultados de los partidos de la jornada
- **THEN** cada partido queda con sus goles y su signo final 1/X/2

#### Scenario: Resultado manual

- **WHEN** un partido no aparece en la fuente (por ejemplo, fuera de Primera y Segunda)
- **THEN** el usuario puede introducir los goles a mano y el signo se calcula a partir de ellos
