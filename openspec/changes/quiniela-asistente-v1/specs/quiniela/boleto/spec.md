## Purpose

Esta capacidad propone cada semana un único boleto de quiniela de hasta 5 €. Elige qué partidos llevan doble o triple para maximizar la probabilidad de cobrar premio, permite al usuario aplicar su propio criterio y explica la propuesta en lenguaje natural sin inventar datos.

## ADDED Requirements

### Requirement: El sistema SHALL ofrecer solo boletos que cumplen el presupuesto y las reglas de juego

El coste del boleto es el número de apuestas por el precio por apuesta. Con el precio vigente de 0,75 €, un mínimo de 2 apuestas y un tope de 5 €, las configuraciones válidas SHALL ser: 1 doble (2 apuestas, 1,50 €), 1 triple (3 apuestas, 2,25 €), 2 dobles (4 apuestas, 3,00 €) y 1 triple + 1 doble (6 apuestas, 4,50 €). El precio, el mínimo y el tope SHALL ser configurables, y la lista de configuraciones válidas SHALL derivarse de ellos.

#### Scenario: Configuraciones bajo el tope por defecto

- **WHEN** el tope es 5 € y el precio 0,75 €
- **THEN** el sistema ofrece exactamente las cuatro configuraciones listadas, con su coste

#### Scenario: Tope menor

- **WHEN** el usuario fija un tope de 3 €
- **THEN** solo se ofrecen 1 doble, 1 triple y 2 dobles

#### Scenario: Cambio de precio

- **WHEN** el precio configurado pasa a 1,00 €
- **THEN** solo se ofrecen las configuraciones con 5 apuestas o menos y sus costes se recalculan

### Requirement: El Pleno al 15 SHALL llevar un único signo por equipo

Cada signo adicional en el Pleno al 15 multiplica el número de apuestas de los 14 partidos, y solo tiene valor con 14 aciertos. Por eso el sistema SHALL proponer y admitir exactamente un signo (0, 1, 2 o M) por equipo en el Pleno.

#### Scenario: Intento de marcar dos signos en el Pleno

- **WHEN** el usuario intenta marcar dos signos para un equipo del Pleno al 15
- **THEN** el sistema lo rechaza e indica que duplicaría el coste del boleto

### Requirement: El sistema SHALL colocar dobles y triples de forma óptima

Para cada configuración válida, el sistema SHALL elegir en qué partidos (1–14) poner los dobles y triples, y con qué signos, para maximizar la probabilidad de lograr N o más aciertos en los 14 partidos, tratando los partidos como independientes. N es configurable y vale 11 por defecto, porque el premio de 10 aciertos queda sin pagar cuando a cada acertante le correspondería menos de 1,50 €. El cálculo SHALL ser exacto, no aproximado. Los demás partidos llevan su signo más probable.

#### Scenario: El doble va al partido más incierto

- **WHEN** la configuración es 1 doble y un partido tiene probabilidades (0,40, 0,32, 0,28) mientras los demás tienen un favorito de 0,70 o más
- **THEN** el doble se coloca en ese partido, cubriendo los dos signos más probables

#### Scenario: Comparativa de configuraciones

- **WHEN** se muestra la propuesta de una jornada
- **THEN** cada configuración válida aparece con su coste y sus probabilidades de 10+, 11+, 12+ y 14 aciertos, y se marca como recomendada la de mayor probabilidad de N+ dentro del tope

#### Scenario: Partido sin datos

- **WHEN** un partido está marcado "sin datos" y el usuario no ha fijado signo
- **THEN** el boleto no se puede confirmar hasta que el usuario fije ese signo

### Requirement: El usuario SHALL poder sobrescribir signos y ver el efecto

El usuario SHALL poder cambiar el signo (o los signos de un múltiple) de cualquier partido y el resultado del Pleno al 15. El sistema SHALL recalcular el coste y las probabilidades de 10+, 11+, 12+ y 14 del boleto resultante, y SHALL rechazar cambios que superen el tope.

#### Scenario: Cambio dentro del tope

- **WHEN** el usuario cambia el signo de un partido simple de "1" a "X"
- **THEN** el boleto muestra el nuevo signo, la probabilidad recalculada y la marca "criterio del usuario" en ese partido

#### Scenario: Cambio que excede el tope

- **WHEN** el usuario intenta añadir un segundo triple con el boleto en 1 triple + 1 doble
- **THEN** el sistema rechaza el cambio y muestra el coste que tendría

### Requirement: El usuario SHALL poder confirmar el boleto y copiarlo

El usuario SHALL poder confirmar un boleto por jornada. El boleto confirmado SHALL guardarse sin cambios posteriores, junto con las probabilidades del momento, y SHALL mostrarse en un formato fácil de trasladar al boleto físico o a la app oficial: 14 signos más el Pleno al 15.

#### Scenario: Confirmación

- **WHEN** el usuario confirma el boleto de una jornada antes de su fecha de cierre
- **THEN** el boleto queda guardado como definitivo con signos, coste y probabilidades

#### Scenario: Jornada cerrada

- **WHEN** ya pasó la fecha de cierre de la jornada
- **THEN** el sistema no permite confirmar ni modificar el boleto

### Requirement: El sistema SHALL explicar el boleto usando solo datos calculados

El sistema SHALL generar una explicación breve (3–5 líneas) de por qué se eligieron los múltiples y los signos. Recibe solo las probabilidades, las fuentes y los avisos ya guardados. NO puede citar cifras que no estén en esos datos. Si la generación falla, el boleto se muestra sin explicación.

#### Scenario: Explicación disponible

- **WHEN** la IA responde a tiempo
- **THEN** la explicación aparece bajo el boleto y menciona los partidos con múltiple

#### Scenario: IA no disponible

- **WHEN** la IA falla o supera el tiempo límite
- **THEN** el boleto se muestra completo sin el párrafo de explicación
