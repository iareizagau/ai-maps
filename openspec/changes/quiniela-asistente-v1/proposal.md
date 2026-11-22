## Why

Relleno una quiniela a la semana "a ojo". Quiero un asistente personal que, con datos abiertos e IA, me proponga **un boleto por jornada de hasta 5 €** y me diga por qué. La premisa que manda el diseño, tras cuestionar la idea: las **cuotas de cierre** son el mejor predictor público de 1X2. Por eso Gemini **no decide signos**: lee noticias y avisa de bajas. Las probabilidades salen de cuotas y de un modelo estadístico propio, y el asistente **mide** cada semana si acierta.

## What Changes

- Nueva app Django `apps.quiniela`, montada en `/quiniela/`, de uso personal (solo usuarios `is_staff`).
- **Datos abiertos**:
  - Histórico de resultados y cuotas de Primera y Segunda (CSV de football-data.co.uk, `SP1`/`SP2`).
  - Cuotas de la semana (CSV `fixtures` de la misma fuente).
  - Noticias por RSS de prensa deportiva.
  - Los 15 partidos de la jornada se introducen a mano en un formulario de 15 filas: no hay API abierta de Loterías.
- **Pronóstico por partido**: probabilidades 1/X/2.
  - Si hay cuotas: probabilidades implícitas sin margen.
  - Si no: modelo Poisson propio (ataque/defensa con decaimiento temporal).
  - El modelo también da el reparto de goles para el **Pleno al 15**.
  - Los partidos sin datos (Copa, selecciones…) quedan marcados como "sin datos" y el usuario fija el signo.
- **Avisos de noticias**: Gemini (ladder de fallback del proyecto, una llamada por jornada) extrae de los titulares bajas, sanciones y dudas con esquema cerrado y URL de la fuente. Los avisos se muestran por partido y **no modifican** las probabilidades.
- **Boleto óptimo ≤ 5 €**:
  - Precio: 0,75 € por apuesta, mínimo 2 apuestas.
  - Configuraciones válidas: 1 doble (1,50 €), 1 triple (2,25 €), 2 dobles (3,00 €), 1 triple + 1 doble (4,50 €).
  - El optimizador coloca dobles y triples donde más suben la probabilidad de ≥ 11 aciertos (cálculo exacto) y muestra las cuatro opciones con coste y probabilidades. Se usa 11 y no 10 porque el premio de 10 aciertos no se paga si a cada acertante le tocaría menos de 1,50 €.
  - El Pleno al 15 lleva un solo signo por equipo: cada signo extra multiplica el coste.
  - El usuario puede sobrescribir signos ("mi criterio").
- **Seguimiento**: al meter resultados se calculan aciertos del boleto y calibración (Brier) por fuente: cuotas, modelo y criterio del usuario.
- **Backtest** sobre temporadas pasadas: compara cuotas frente a modelo antes de confiar en el modelo como respaldo.
- Explicación del boleto en 3–5 líneas, redactada por Gemini **solo** con los números calculados. Si Gemini falla, el boleto se muestra igual.

Fuera de alcance (cambios futuros):
- Versión de pago o multiusuario.
- Porcentajes apostados por el público ("valor frente al público").
- Scraper de la jornada oficial de Loterías.
- Quinielas reducidas, que ya superan los 5 €.
- Elige 8.
- Alineaciones confirmadas: salen 1 h antes del partido, después del cierre.

## Capabilities

### New Capabilities
- `quiniela/datos-jornada`: alta de la jornada (15 partidos) e ingesta de histórico, cuotas y resultados desde fuentes abiertas.
- `quiniela/pronostico`: probabilidades 1X2 por partido (cuotas → modelo → manual) y pronóstico del Pleno al 15.
- `quiniela/avisos-noticias`: extracción con IA de bajas y dudas desde RSS, con fuente obligatoria y sin efecto sobre las probabilidades.
- `quiniela/boleto`: propuesta de un boleto semanal con presupuesto ≤ 5 €, sobrescritura manual y explicación.
- `quiniela/seguimiento`: evaluación semanal de aciertos y calibración por fuente, y backtest histórico.

### Modified Capabilities
<!-- Ninguna. -->

## Impact

- **Código**: `src/apps/quiniela/` (models, services_*, views, urls, admin, management commands, tests), `src/templates/quiniela/`, registro en `INSTALLED_APPS` y `config/urls.py`.
- **BD**: tablas nuevas de la app (una migración inicial). Sin cambios en otras apps ni en la imagen de BD.
- **APIs externas**: football-data.co.uk (CSV públicos, sin clave), RSS públicos (`feedparser` ya está en dependencias) y Gemini (`GEMINI_API_KEY` y `GEMINI_GENERATION_FALLBACK_MODELS` existentes). Una o dos llamadas por semana: impacto despreciable en la cuota gratuita.
- **Dependencias nuevas**: ninguna. El modelo Poisson y el optimizador se escriben en Python puro.
- **Riesgos**: que las cuotas semanales de la fuente abierta falten o lleguen tarde (respaldo: modelo); nombres de equipo distintos entre fuentes (selección desde un catálogo con alias); que la normativa de precio o categorías de premio cambie (constantes en settings, comprobadas en la tarea 1).
- **Rollback**: quitar la app de `INSTALLED_APPS` y la ruta; no toca nada compartido.
