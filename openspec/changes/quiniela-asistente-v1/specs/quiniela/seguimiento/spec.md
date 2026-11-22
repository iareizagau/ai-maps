## Purpose

Esta capacidad mide si el asistente aporta algo. Evalúa cada boleto confirmado contra los resultados reales, compara la calibración de cada fuente de probabilidad (cuotas, modelo, criterio del usuario) y permite un backtest histórico antes de confiar en el modelo propio.

## ADDED Requirements

### Requirement: El sistema SHALL evaluar el boleto confirmado cuando haya resultados

Cuando una jornada tenga los 15 resultados, el sistema SHALL calcular los aciertos del boleto confirmado en los 14 partidos. En los partidos con múltiple, cualquier signo incluido cuenta como acierto. El sistema SHALL registrar también el acierto del Pleno al 15 y el coste jugado.

#### Scenario: Evaluación con múltiples

- **WHEN** el boleto tiene un doble "1X" en un partido que terminó en empate
- **THEN** ese partido cuenta como acierto

#### Scenario: Jornada sin boleto confirmado

- **WHEN** una jornada tiene resultados pero no tiene boleto confirmado
- **THEN** no se evalúa ningún boleto y la calibración por fuente se calcula igualmente

### Requirement: El sistema SHALL medir la calibración por fuente

Para cada partido con resultado, el sistema SHALL calcular el Brier score de las probabilidades de cada fuente disponible (cuotas, modelo) y la tasa de acierto del signo más probable de cada fuente y del criterio del usuario. SHALL mostrar el acumulado por temporada y de las últimas 10 jornadas.

#### Scenario: Comparativa acumulada

- **WHEN** el usuario abre la página de seguimiento
- **THEN** ve, por fuente, el Brier medio, la tasa de acierto y el número de partidos evaluados, y el gasto total frente a los aciertos de cada jornada

#### Scenario: Criterio del usuario frente al modelo

- **WHEN** el usuario sobrescribió signos en jornadas evaluadas
- **THEN** el seguimiento muestra cuántas sobrescrituras acertaron y cuántas habría acertado el signo propuesto

### Requirement: El sistema SHALL permitir un backtest histórico del modelo frente a las cuotas

El sistema SHALL ofrecer un backtest sobre las temporadas guardadas de Primera y Segunda. Para cada partido con cuotas de cierre, SHALL pronosticar con el modelo (entrenado solo con partidos anteriores) y comparar el Brier score, la log-loss y la tasa de acierto del modelo frente a las cuotas de cierre. El resultado SHALL poder repetirse con los mismos datos y parámetros.

#### Scenario: Backtest de varias temporadas

- **WHEN** se lanza el backtest sobre tres temporadas
- **THEN** se obtiene, por división y en total, Brier, log-loss, tasa de acierto y número de partidos de cada fuente

#### Scenario: Reproducibilidad

- **WHEN** se lanza dos veces con los mismos datos y parámetros
- **THEN** ambos resultados son idénticos
