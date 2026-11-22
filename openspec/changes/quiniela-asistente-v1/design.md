## Context

- Monorepo Django 6 (`src/apps/*`), Docker, Postgres. Gemini ya está configurado con su ladder de fallback (`GEMINI_GENERATION_FALLBACK_MODELS` en `config/settings/base.py`), `feedparser` y `requests` ya son dependencias, y la UI es HTMX + Alpine + Cotton, mobile-first.
- Hay dos copias del helper de Gemini con ladder: `apps/mubil/ask/services.py:258` y `apps/amenabar/services_match.py:130`. No existe uno compartido en `core`.
- `numpy`, `scipy` y `pandas` no están en dependencias.
- La quiniela no tiene API abierta, ni para la jornada ni para los porcentajes del público. Las fuentes abiertas usables son los CSV de football-data.co.uk y los RSS de prensa.
- Uso personal: un usuario, un boleto por semana, tope de 5 €. Motivación en proposal.md; requisitos en `specs/quiniela/*`.

## Goals / Non-Goals

**Goals:**
- Flujo semanal de unos 5 minutos: alta de jornada → pronóstico → avisos → boleto → confirmar. El lunes, resultados → evaluación.
- Que cada probabilidad lleve su fuente y que cada semana se mida si el modelo y el usuario aportan algo frente a las cuotas.
- Cero dependencias nuevas y un consumo de Gemini despreciable (≤ 2 llamadas por jornada).

**Non-Goals:**
- Tiempo real, alineaciones confirmadas, scraping de Loterías, porcentajes del público, reducidas, multiusuario o pago (ver proposal.md, fuera de alcance).
- Consolidar los helpers de Gemini en `core`. Sería un refactor que toca otras apps; queda como cambio aparte.
- Celery Beat. En v1 todo se lanza con comandos o con botones HTMX.

## Decisions

### D1. App dentro del monorepo, sin campos GIS
Se reutiliza Docker, la autenticación, la ladder de Gemini y el pipeline de Tailwind. La app no usa `django.contrib.gis`.
**Alternativa:** repo aparte. Más limpio, pero duplica infraestructura para un uso personal. Si algún día hay versión de pago, la app se puede extraer porque no depende de otras apps.

### D2. Fuentes de datos (verificadas en la tarea 1, 2026-11-22)
| Dato | Fuente | Notas |
| --- | --- | --- |
| Histórico y cuotas de cierre | `https://football-data.co.uk/mmz4281/{yyYY}/SP1.csv` y `SP2.csv` (`www.` responde con un 302 a esta URL: seguir redirecciones) | Cuotas: **`AvgCH/AvgCD/AvgCA`** (media de cierre), presentes en el 100 % de filas de 24-25, 25-26 y 26-27. Pinnacle (`PSCH…`) **desaparece** a mitad de 25-26 (188/380 en SP1) y no existe en 26-27, así que no se usa. Respaldo: `B365CH…`, y después `AvgH…` (previa) |
| Cuotas de la semana | `https://football-data.co.uk/fixtures.csv` | Verificado: incluye **SP1 (10) y SP2 (11)** de la jornada con cuotas previas `AvgH/AvgD/AvgA` (`B365H…` de respaldo). Las columnas de cierre vienen vacías. `Last-Modified` = viernes 10:23 GMT, con partidos desde el viernes por la noche |
| Resultados de la jornada | El mismo CSV de temporada, o entrada manual | No se actualiza a diario (`Last-Modified` de SP1 26-27: lunes 09/11). Partidos fuera de SP1/SP2 → siempre a mano |
| Noticias | `QUINIELA_RSS_FEEDS` en settings | Ver más abajo |
| Jornada (15 partidos) | Formulario manual | Selects del catálogo `Equipo` y texto libre para equipos ajenos |

Formato de los CSV: `Date` `dd/mm/yyyy`; `Time` en hora del Reino Unido (deducido: el viernes 20:00 del CSV es el horario habitual de las 21:00 en España); `FTHG/FTAG/FTR` como resultado. Los nombres de equipo van abreviados en inglés (`Ath Bilbao`, `Ath Madrid`, `Sociedad B`, `La Coruna`, `Santander`, `Sp Gijon`, `Espanol`), por eso hacen falta los alias.

Extra no previsto: desde 26-27 los CSV traen **xG por partido (`HxG/AxG`)**. En v1 no se usa. Es candidato para mejorar el modelo en un cambio posterior.

**RSS verificados** (frescura medida el 22/11/2026):
| Feed | Estado |
| --- | --- |
| AS fútbol portada, primera y segunda (`https://feeds.as.com/mrss-s/pages/as/site/as.com/section/futbol/…`) | OK. Unas 50 entradas, todas de los últimos 1–2 días |
| Mundo Deportivo fútbol (`https://www.mundodeportivo.com/rss/futbol.xml`) | OK. 100 entradas de la última semana |
| Google News búsqueda por equipo (`https://news.google.com/rss/search?q="<equipo>"+(lesión OR baja OR convocatoria)&hl=es&gl=ES&ceid=ES:es`) | OK y es la mejor cobertura para Segunda. Una petición por equipo de la jornada (unas 30) |
| Marca primera y segunda (`e00-marca.uecdn.es/rss/…`) | **Descartado**: congelado desde el 07/11 |
| Sport, Relevo, Estadio Deportivo | **Descartados**: 406 o 404 |
| Europa Press deportes | **Descartado**: 10 entradas de todos los deportes |

Los feeds de AS solo guardan 1–2 días. Las noticias se ingieren con dedupe, así que conviene pulsar "Actualizar noticias" el jueves y el viernes. El histórico de noticias se acumula en BD.

Los nombres de equipo se resuelven con un modelo `EquipoAlias` (texto único → equipo). El formulario usa el catálogo, así que no hace falta coincidencia difusa.

### D3. Probabilidades a partir de cuotas: normalización proporcional
`p_i = (1/o_i) / Σ(1/o_j)`. Es simple y suficiente con cuotas de cierre de margen bajo.
**Alternativa:** el método de Shin corrige mejor el sesgo hacia favoritos y no favoritos. Se deja como parámetro para compararlo en el backtest si el proporcional calibra mal.

### D4. Modelo propio: Poisson de ataque y defensa con decaimiento temporal (Maher / Dixon-Coles), en Python puro
- `λ_local = exp(μ + h + a_local − d_visit)` y `λ_visit = exp(μ + a_visit − d_local)`. Se ajusta por máxima verosimilitud ponderada con pesos `exp(−ξ·días)`.
- Se ajusta **conjuntamente sobre SP1 y SP2** de las 2 últimas temporadas, para que los ascendidos y descendidos tengan histórico, con un efecto de división que absorbe la diferencia de nivel.
- Solver: Newton por coordenadas o IPF (unos 40 equipos y unos 1.600 partidos). Se escribe en Python puro porque cabe de sobra y evita meter `scipy` en la imagen.
- Corrección ρ de Dixon-Coles para marcadores bajos: es configurable y empieza en 0. Se activa si el backtest muestra que el modelo infravalora los empates, que en la quiniela pesan mucho.
- Un equipo tiene "histórico suficiente" con ≥ `QUINIELA_MIN_PARTIDOS` (por defecto 10) partidos ponderados en la ventana.
- Pleno al 15: con la matriz de goles hasta 10 por equipo se agrega a {0, 1, 2, M}.
**Alternativa:** Elo. Más simple, pero no da distribución de goles, y la necesitamos para el Pleno.

### D5. Optimizador exacto
- Cobertura por partido: simple → `max p`, doble → suma de los dos mayores, triple → 1.
- Para cada configuración válida (derivada de precio, mínimo y tope en settings) se enumeran todas las colocaciones posibles: como máximo 14 × 13 = 182 en T+D. Para cada una se calcula `P(aciertos ≥ k)` con la DP de Poisson-binomial, O(14·15).
- Objetivo: **P(≥ N)** con `N = QUINIELA_OBJETIVO_ACIERTOS`, por defecto **11**. No es 10 porque la norma 7ª.6 deja **sin cobrar la 5ª categoría (10 aciertos) si a cada acertante le corresponde menos de 1,50 €**. Eso pasa justo en las jornadas "fáciles", cuando ganan los favoritos y nuestro boleto llega a 10 con más facilidad. La 4ª categoría (11 aciertos) solo se queda vacía por debajo de 1 € (norma 7ª.5), que es raro. P(14) es prácticamente cero y no discrimina. Se muestran P(10+), P(11+), P(12+) y P(14).
- Pleno al 15: **un único signo por equipo**. La norma 17ª.2 multiplica todas las apuestas por cada signo extra del Pleno, y ese gasto solo rinde con 14 aciertos (probabilidad despreciable). El optimizador no lo considera.
- Las apuestas sencillas (2–8 columnas distintas, norma 19ª) son legales y caben en 5 € (hasta 6 columnas). Quedan fuera de v1: optimizar varias columnas independientes es otro problema y no ofrece una ventaja clara frente al múltiple directo. Se anota como posible cambio futuro.
- Con las sobrescrituras del usuario se hace lo mismo: se recalcula la DP sobre las coberturas resultantes.
- Importes con `Decimal`. Precio, mínimo y tope van en settings (`QUINIELA_PRECIO_APUESTA = Decimal("0.75")`, `QUINIELA_MIN_APUESTAS = 2`, `QUINIELA_TOPE_EUR = Decimal("5.00")`).

### D6. Gemini: dos llamadas por jornada como máximo, con esquema cerrado
- **Avisos**: una llamada con todos los titulares filtrados, agrupados por equipo con URL. Devuelve una lista JSON y se validan contra el esquema y contra las URL recogidas (spec avisos-noticias).
- **Explicación**: una llamada con un dict cerrado (signos, coberturas, probabilidades, fuentes, avisos). Timeout de unos 8 s; si falla, `None`.
- El helper sigue el patrón de `amenabar/services_match._call_gemini_json` (ladder; 503/429 avanzan y los errores de autenticación cortan). Se crea `apps/quiniela/services_gemini.py` como **tercera copia consciente**: importar un helper privado de otra app acopla más que duplicar 40 líneas. Consolidarlo en `core` queda como cambio aparte.

### D7. Modelo de datos
- `Equipo(nombre)` y `EquipoAlias(texto único, equipo FK)`.
- `PartidoHistorico(division, temporada, fecha, local FK, visitante FK, goles_local, goles_visitante, cuota_1/x/2 nullable, cuota_tipo)`, `unique(fecha, local, visitante)`. La ingesta hace upsert dentro de una transacción por temporada.
- `Jornada(temporada, numero, fecha_cierre)`.
- `PartidoJornada(jornada FK, posicion 1..15, local/visitante FK nullable, local_texto/visitante_texto, fecha, cuota_1/x/2 y cuotas_capturadas_at nullable, goles_local/visitante nullable)`, `unique(jornada, posicion)`.
- `Pronostico(partido FK, fuente ∈ {cuotas, modelo, uniforme}, p1, px, p2, pleno_dist JSON nullable, calculado_at)`, `unique(partido, fuente)`. La fuente "elegida" se deriva por precedencia: no se guarda, para que no se desincronice.
- `Noticia(url única, titulo, publicada_at, feed)` y M2M con `Equipo`.
- `Aviso(partido FK, equipo FK, jugador, tipo, resumen, noticia FK)`.
- `Boleto(jornada OneToOne, usuario FK, lineas JSON [{posicion, signos, origen}], pleno, configuracion, num_apuestas, coste Decimal, p10/p12/p14, explicacion, confirmado_at, aciertos nullable, pleno_acertado nullable)`. Una vez confirmado es de solo lectura (se valida en el servicio y en el admin).
- La calibración no se guarda: se calcula al consultar a partir de `Pronostico` y los resultados, que son pocos datos.

### D8. Ejecución y UI
- Comandos: `quiniela_ingest_historico --temporadas 2324 2425 2526`, `quiniela_ingest_cuotas`, `quiniela_ingest_resultados`, `quiniela_ingest_noticias` y `quiniela_backtest`.
- La página de jornada tiene botones HTMX que llaman a los mismos servicios de forma síncrona, con indicador de carga. Para una persona y unos 10 s como máximo, Celery no compensa.
- Rutas: `/quiniela/` (jornada actual y boleto), `/quiniela/jornada/nueva/`, `/quiniela/jornada/<id>/`, `/quiniela/seguimiento/`. Todas tras `staff_member_required`.
- Mobile-first a 375 px: cada partido es una fila compacta con barra de probabilidades 1/X/2, fuente, signo y avisos plegables (Alpine). El boleto se ve como una cuadrícula de 14 signos + Pleno, lista para copiar.

### D9. Backtest walk-forward por fecha
Se reajusta el modelo una vez por fecha de jornada, no por partido: unas 300 reajustes en 3 temporadas, y como mucho minutos en Python puro. Se pronostican los partidos de esa fecha con datos estrictamente anteriores. Las métricas son Brier, log-loss y acierto, por división y en total, frente a las cuotas de cierre. Con datos y parámetros fijos, el resultado es determinista.

**Resultado del backtest real (2026-11-22).** Temporadas 24-25, 25-26 y 26-27 de SP1 y SP2; reajuste por semana ISO (97 ajustes, ~40-60 s en total). El modelo y las cuotas medias de cierre se miden sobre el mismo conjunto de partidos:

| Variante | Fuente | n | Brier | log-loss | Acierto |
| --- | --- | --- | --- | --- | --- |
| Base (ξ = 0,0019, ρ = 0, mín. 10) | Cuotas (proporcional) | 1.679 | 0,5849 | 0,9826 | 52,6 % |
| | Modelo | 1.679 | 0,6052 | 1,0131 | 49,9 % |
| ρ = -0,1 | Modelo | 1.679 | 0,6060 | 1,0148 | 49,5 % |
| Mínimo 20 partidos | Cuotas | 1.419 | 0,5816 | 0,9772 | 52,9 % |
| | Modelo | 1.419 | 0,5981 | 1,0016 | 50,7 % |
| Cuotas Shin | Cuotas | 1.679 | 0,5839 | 0,9810 | 52,6 % |

Por división (base): SP1 cuotas 0,5627 frente a modelo 0,5840; SP2 cuotas 0,6041 frente a modelo 0,6235.

Decisiones:
- El modelo queda **solo como respaldo**: calibra ~0,02 de Brier peor que las cuotas, como se esperaba.
- **ρ = 0**: la corrección de Dixon-Coles empeora.
- **Shin pasa a ser el método por defecto** (`QUINIELA_METODO_CUOTAS`): mejora en las dos divisiones.
- **Mínimo de partidos = 10**: con 20 el modelo mejora, pero deja 260 partidos más en "sin datos", y en la quiniela un pronóstico algo peor vale más que ninguno.

## Risks / Trade-offs

- [`fixtures.csv` tarde o incompleto alguna semana] → Verificado que cubre SP1 y SP2 y se publica el viernes por la mañana. Si una jornada de quiniela cierra antes, o trae partidos de viernes temprano o entre semana, esos partidos van al modelo.
- [Reglas de juego] → Verificadas en las *Normas de La Quiniela* de SELAE, vigentes "a partir de la temporada 2017-2018 y para las siguientes, en tanto no se publique una nueva resolución" (norma 58ª.4): 0,75 €/apuesta (5ª); mínimo 2 apuestas (19ª); el Anexo I (Método Directo) autoriza 1D = 2, 1T = 3, 2D = 4 y 1D+1T = 6 apuestas; 55 % a premios con categorías 14/13/12/11/10 aciertos más la especial del Pleno (6ª–8ª). **No se ha podido confirmar** en loteriasyapuestas.es si hay una resolución más reciente, porque la web responde 403 a clientes automáticos. Precio y tope siguen en settings.
- [Hora de cierre de la validación] → La norma 4ª solo exige registrar las apuestas "antes de la hora de comienzo de los partidos". La hora exacta de cierre de venta no se ha verificado, así que `fecha_cierre` la introduce el usuario en el alta.
- [El modelo calibra peor que las cuotas] → Es lo esperado. Solo se usa sin cuotas, y el backtest dice cuánto peor. Si es mucho peor, en partidos sin cuotas se muestra "sin datos" en lugar de modelo.
- [Gemini inventa bajas] → URL obligatoria entre las noticias recogidas, esquema cerrado y ningún efecto sobre las probabilidades.
- [Tercera copia del helper de Gemini] → Deuda aceptada y anotada. Se consolida en `core` en un cambio aparte.
- [Independencia entre partidos en la DP] → Aproximación estándar, con impacto despreciable en 14 partidos distintos.
- [Juego con valor esperado negativo] → El tope de 5 € es duro, y la página de seguimiento muestra el gasto acumulado frente a lo ganado, sin maquillar.

## Migration Plan

1. Migración inicial de la app y registro en `INSTALLED_APPS` y `config/urls.py`.
2. `quiniela_ingest_historico` de las 3 últimas temporadas de SP1 y SP2, y `quiniela_backtest`. Revisar las métricas antes del primer uso.
3. Uso semanal.

Rollback: quitar la app de `INSTALLED_APPS` y la ruta. Las tablas quedan aisladas y se pueden borrar con `migrate quiniela zero`.
