## Purpose

Esta capacidad asigna a cada partido de la jornada unas probabilidades 1/X/2 trazables a su fuente (cuotas, modelo estadístico propio o criterio manual) y propone el resultado del Pleno al 15. Así el boleto se construye sobre números y no sobre la opinión de un LLM.

## ADDED Requirements

### Requirement: El sistema SHALL calcular probabilidades 1X2 por partido con una precedencia fija de fuentes

Para cada partido, el sistema SHALL producir tres probabilidades que suman 1 y SHALL registrar qué fuente las generó. Orden de precedencia: (1) cuotas de la semana, (2) modelo estadístico propio sobre el histórico, (3) "sin datos", donde el usuario fija el signo. Un LLM NO puede producir ni alterar estas probabilidades.

#### Scenario: Partido con cuotas

- **WHEN** un partido tiene cuotas 1/X/2
- **THEN** sus probabilidades son las implícitas en las cuotas sin el margen de la casa, suman 1 y la fuente queda como "cuotas"

#### Scenario: Partido sin cuotas pero con histórico

- **WHEN** un partido no tiene cuotas y ambos equipos tienen histórico suficiente
- **THEN** sus probabilidades salen del modelo estadístico y la fuente queda como "modelo"

#### Scenario: Partido sin datos

- **WHEN** un partido no tiene cuotas y algún equipo carece de histórico suficiente
- **THEN** el partido queda marcado como "sin datos", con probabilidades uniformes solo de referencia, y la interfaz pide al usuario fijar el signo

#### Scenario: Ambas fuentes disponibles

- **WHEN** un partido tiene cuotas y modelo
- **THEN** se usan las cuotas y la probabilidad del modelo se guarda también para el seguimiento

### Requirement: El modelo estadístico SHALL entrenarse solo con partidos anteriores al que pronostica

El modelo SHALL estimar fuerza de ataque y defensa de cada equipo y la ventaja de jugar en casa a partir de resultados anteriores a la fecha del partido, dando más peso a los recientes. NO puede usar información del propio partido ni de partidos posteriores.

#### Scenario: Sin fuga de información en el backtest

- **WHEN** se pronostica un partido histórico
- **THEN** el ajuste solo usa partidos con fecha estrictamente anterior

### Requirement: El sistema SHALL proponer un resultado para el Pleno al 15

Para el partido 15, el sistema SHALL calcular la probabilidad de cada combinación de goles en las categorías de la quiniela (0, 1, 2, M) por equipo y SHALL proponer la más probable, mostrando también su probabilidad.

#### Scenario: Pleno al 15 con modelo

- **WHEN** el partido 15 tiene histórico suficiente
- **THEN** el sistema muestra la combinación más probable (por ejemplo, "1-1") y su probabilidad, y las 16 combinaciones suman 1

#### Scenario: Pleno al 15 sin datos

- **WHEN** el partido 15 no tiene histórico suficiente
- **THEN** el sistema pide al usuario elegir la combinación sin proponer ninguna

### Requirement: El pronóstico SHALL recalcularse cuando cambien sus entradas

Las probabilidades de la jornada SHALL recalcularse al llegar cuotas nuevas o cambiar el histórico, y SHALL conservar la hora del último cálculo.

#### Scenario: Llegan cuotas después del alta

- **WHEN** se capturan cuotas para un partido que se pronosticó con el modelo
- **THEN** el partido pasa a fuente "cuotas" y la hora de cálculo se actualiza
