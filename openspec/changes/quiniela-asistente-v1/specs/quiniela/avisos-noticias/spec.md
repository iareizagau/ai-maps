## Purpose

Esta capacidad resume, para cada partido de la jornada, las bajas, sanciones y dudas publicadas en prensa deportiva abierta (RSS), con su fuente. Así el usuario puede decidir si cambia un signo, sin que la IA toque las probabilidades.

## ADDED Requirements

### Requirement: El sistema SHALL recoger noticias recientes de los equipos de la jornada

El sistema SHALL leer los RSS configurados, quedarse con las entradas de los últimos 7 días que mencionen a algún equipo de la jornada (por nombre o alias) y guardarlas sin duplicar, usando su URL como clave.

#### Scenario: Noticias relevantes

- **WHEN** un RSS publica una entrada que menciona a un equipo de la jornada
- **THEN** la entrada queda asociada a ese equipo con título, URL y fecha

#### Scenario: Entrada repetida

- **WHEN** la misma URL aparece en dos lecturas o en dos RSS
- **THEN** se guarda una sola vez

#### Scenario: RSS caído

- **WHEN** un RSS no responde o devuelve un formato inválido
- **THEN** se registra en el log y se siguen leyendo los demás

### Requirement: El sistema SHALL extraer avisos estructurados con IA y fuente obligatoria

A partir de las noticias recogidas, el sistema SHALL obtener avisos con esquema cerrado: equipo, jugador opcional, tipo (lesión, sanción, duda, rotación u otro), resumen de una línea y URL de la noticia de origen. Un aviso cuya URL no esté entre las noticias recogidas, o cuyo equipo no juegue la jornada, SHALL descartarse.

#### Scenario: Aviso válido

- **WHEN** la IA devuelve un aviso con equipo de la jornada, tipo permitido y URL de una noticia recogida
- **THEN** el aviso aparece en el partido correspondiente con enlace a la noticia

#### Scenario: Aviso inventado

- **WHEN** la IA devuelve un aviso cuya URL no está entre las noticias recogidas
- **THEN** el aviso se descarta y se registra en el log

#### Scenario: Tipo fuera del esquema

- **WHEN** la IA devuelve un tipo de aviso no permitido
- **THEN** el aviso se guarda con tipo "otro"

#### Scenario: IA no disponible

- **WHEN** la IA falla o agota la cuota en todos los modelos
- **THEN** la jornada muestra una indicación de "avisos no disponibles" junto con los avisos de la última extracción correcta, si los hay, y el pronóstico y el boleto no se ven afectados

### Requirement: Los avisos NO SHALL modificar las probabilidades

Los avisos SHALL ser solo informativos. Ningún aviso puede cambiar las probabilidades ni el boleto propuesto. Solo el usuario, sobrescribiendo un signo, puede trasladar un aviso al boleto.

#### Scenario: Aviso de baja importante

- **WHEN** un partido recibe un aviso de lesión del máximo goleador
- **THEN** las probabilidades y el boleto propuesto de ese partido no cambian, y el aviso se muestra junto a ellos
