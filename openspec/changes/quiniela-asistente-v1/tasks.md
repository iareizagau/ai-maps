## 1. Verificación de fuentes y reglas (spike, sin código de app)

- [x] 1.1 Descargar `SP1.csv` y `SP2.csv` de una temporada reciente de football-data.co.uk. Anotar en design.md D2 las columnas reales de cuotas de cierre (Pinnacle y media) y el formato de fecha. *(SP1/SP2 de 24-25, 25-26 y 26-27. `AvgC*` está al 100 %; Pinnacle desaparece a mitad de 25-26. En 26-27 aparece xG `HxG/AxG`. Hay que seguir el 302 de `www.`.)*
- [x] 1.2 Descargar `fixtures.csv` un viernes y comprobar si incluye partidos `SP1` y `SP2` con cuotas. Anotar cobertura y día y hora de publicación. Si no cubre SP2, dejarlo escrito en Risks (el respaldo sigue siendo el modelo). *(Cubre SP1 (10) y SP2 (11) con `AvgH/D/A` previas. Publicado el viernes a las 10:23 GMT.)*
- [x] 1.3 Contrastar en la web de Loterías y Apuestas del Estado: precio por apuesta, mínimo de apuestas, límites de dobles y triples, categorías de premio (¿10 aciertos es categoría?) y cómo funciona el Pleno al 15 en un boleto múltiple. Si algo difiere, corregir la spec `boleto` y las constantes antes de seguir. *(La web da 403 a clientes automáticos; se verificó en las Normas SELAE 2017-18 vigentes y su Anexo I. Cambios: objetivo P(≥11) en lugar de P(≥10) por la norma 7ª.6, y Pleno con un solo signo por la norma 17ª.2. Pendiente: confirmar en la web, desde el navegador, que no hay resolución posterior.)*
- [x] 1.4 Elegir 4–6 RSS de prensa deportiva que respondan y tengan títulos y fechas utilizables. Anotar sus URL para `QUINIELA_RSS_FEEDS`. *(AS ×3, Mundo Deportivo y Google News por equipo. Marca, Sport, Relevo, Estadio Deportivo y Europa Press descartados.)*

## 2. Scaffold de la app

- [x] 2.1 Crear `src/apps/quiniela/` siguiendo el skill `django-app-scaffold`: apps, admin, models, services, views, urls, `tests/`, `management/commands/` y `migrations/`. Sin `api.py` Ninja, porque v1 no expone API.
- [x] 2.2 Registrar `apps.quiniela` en `INSTALLED_APPS` y montar `path("quiniela/", include("apps.quiniela.urls"))` en `config/urls.py`.
- [x] 2.3 Añadir a `config/settings/base.py`: `QUINIELA_PRECIO_APUESTA`, `QUINIELA_MIN_APUESTAS`, `QUINIELA_TOPE_EUR`, `QUINIELA_OBJETIVO_ACIERTOS` (11), `QUINIELA_GNEWS_ENABLED`, `QUINIELA_MIN_PARTIDOS`, `QUINIELA_DECAY_XI`, `QUINIELA_DC_RHO`, `QUINIELA_RSS_FEEDS` y `QUINIELA_FD_BASE_URL`, leídos con `env` y con defaults.

## 3. Modelos y migración

- [x] 3.1 `Equipo` y `EquipoAlias` (texto único), con un helper `resolver_equipo(texto, crear=True)`. *(Añadido `equipos_seed.py`: 54 equipos de SP1/SP2 22-23→26-27 con nombre canónico y alias de prensa, necesarios para emparejar noticias y para la consulta de Google News.)*
- [x] 3.2 `PartidoHistorico` con `unique(fecha, local, visitante)` e índices por `(division, temporada)` y `fecha`.
- [x] 3.3 `Jornada`, y `PartidoJornada` con `unique(jornada, posicion)`, validación 1..15 y local ≠ visitante.
- [x] 3.4 `Pronostico` con `unique(partido, fuente)` y la propiedad `PartidoJornada.pronostico_elegido` por precedencia cuotas > modelo > uniforme.
- [x] 3.5 `Noticia` (URL única, M2M con `Equipo`) y `Aviso`.
- [x] 3.6 `Boleto` (OneToOne con la jornada; `coste` como `Decimal`), con un guardado que impide modificarlo si ya está confirmado.
- [x] 3.7 `makemigrations quiniela` y `migrate`. Registro en el admin, con `Boleto` confirmado en solo lectura. *(12 tests de modelos en verde.)*

## 4. Ingesta de datos (`services_ingest.py` y comandos)

- [x] 4.1 `ingest_temporada(division, temporada)`: descarga el CSV, parsea columnas y fechas, resuelve alias y hace upsert transaccional por temporada. Si falla la descarga o el formato, error explícito y nada guardado.
- [x] 4.2 Comando `quiniela_ingest_historico --divisiones SP1 SP2 --temporadas ...`.
- [x] 4.3 `ingest_cuotas_jornada(jornada)`: lee `fixtures.csv`, asocia por equipos y fecha (±1 día) y guarda las cuotas con `cuotas_capturadas_at`. Los partidos sin cuota se quedan sin ella. Comando `quiniela_ingest_cuotas`.
- [x] 4.4 `ingest_resultados_jornada(jornada)`: rellena goles desde el CSV de temporada. Comando `quiniela_ingest_resultados`.
- [x] 4.5 `ingest_noticias(jornada)`: lee los RSS fijos (AS ×3, Mundo Deportivo) y, si `QUINIELA_GNEWS_ENABLED`, una búsqueda de Google News por equipo de la jornada. Usa `feedparser`, filtra los últimos 7 días por nombre o alias y deduplica por URL. Un feed caído se registra en el log y se sigue con el resto. Comando `quiniela_ingest_noticias`.
- [x] 4.6 Al ingerir, seguir redirecciones (`www.football-data.co.uk` → `football-data.co.uk`), leer el CSV con `utf-8-sig` y cuotas por orden `AvgC*` → `B365C*` → `Avg*`. Test con un CSV de muestra de 26-27 (columnas `HxG/AxG` presentes pero ignoradas). *(13 tests de ingesta en verde, con CSV y feeds inyectados; sin red.)*

## 5. Pronóstico (`services_modelo.py` y `services_pronostico.py`)

- [x] 5.1 `probs_desde_cuotas(o1, ox, o2)` con normalización proporcional, y Shin opcional por parámetro.
- [x] 5.2 `ajustar_modelo(partidos, fecha_corte, xi, rho)`: Poisson de ataque y defensa con ventaja local, efecto de división y pesos temporales, en Python puro. Solo usa partidos anteriores a `fecha_corte`.
- [x] 5.3 `matriz_goles(modelo, local, visitante)` → probabilidades 1X2 y distribución del Pleno {0,1,2,M}², que suma 1.
- [x] 5.4 `calcular_pronostico_jornada(jornada)`: guarda las filas `Pronostico` por fuente disponible y marca "sin datos" cuando no hay histórico suficiente. *(11 tests en verde. Con datos reales (1.954 partidos, corte 20/11/2026): ajuste en 0,49 s y 78 iteraciones, h = 0,27; las probabilidades del modelo van en la línea de las cuotas pero más moderadas. Caso a vigilar en el backtest: los equipos con pocos partidos (Celta B, n = 14).)*

## 6. Avisos con Gemini (`services_gemini.py` y `services_avisos.py`)

- [x] 6.1 `_call_gemini_json(prompt, max_output_tokens, timeout_s)` con la ladder de `GEMINI_GENERATION_FALLBACK_MODELS`, siguiendo el patrón de `amenabar/services_match.py`, con un comentario que apunte a la futura consolidación en `core`.
- [x] 6.2 `extraer_avisos(jornada)`: una llamada con los titulares agrupados por equipo. Validación de esquema cerrado, URL dentro de las noticias recogidas y equipo de la jornada. Tipo desconocido → "otro". Si falla, cero avisos y bandera "avisos no disponibles". *(Gemini cita titulares numerados en vez de URL: es equivalente a exigir una URL recogida y no deja inventar enlaces. Si falla, se conservan los avisos de la última extracción buena y el motivo queda en `Jornada.avisos_error` (migración 0002); spec actualizada. Comando `quiniela_extraer_avisos`. 9 tests con Gemini simulado.)*

## 7. Boleto (`services_boleto.py`)

- [x] 7.1 `configuraciones_validas(precio, minimo, tope)`: enumera las combinaciones de dobles y triples con `2^d·3^t` apuestas entre el mínimo y `floor(tope/precio)`.
- [x] 7.2 `prob_aciertos(coberturas)`: DP de Poisson-binomial que devuelve la distribución de 0..14 aciertos y los acumulados P(≥10), P(≥11), P(≥12) y P(14).
- [x] 7.3 `optimizar(jornada, config)`: enumeración exacta de colocaciones de múltiples sobre los partidos 1–14, maximizando P(≥`QUINIELA_OBJETIVO_ACIERTOS`). Pleno con un solo signo por equipo (rechazar múltiples en el Pleno). `proponer(jornada)` devuelve todas las configuraciones con coste y probabilidades, y marca la recomendada.
- [x] 7.4 `aplicar_sobrescritura(boleto, posicion, signos)`: recalcula coste y probabilidades, rechaza superar el tope y marca el origen "usuario". Pleno al 15 editable.
- [x] 7.5 `confirmar(boleto)`: exige que no haya partidos "sin datos" sin signo y que no haya pasado `fecha_cierre`. Guarda la foto de las probabilidades.
- [x] 7.6 `explicar(boleto)`: Gemini con dict cerrado de datos calculados y timeout. Si falla, `None`. *(18 tests del boleto en verde. Un partido sin datos cubierto con triple no exige signo manual para confirmar; con doble o simple, sí.)*

## 8. Seguimiento y backtest (`services_seguimiento.py`)

- [x] 8.1 `evaluar_boleto(jornada)`: aciertos en 1–14 (un múltiple acierta si incluye el signo), acierto del Pleno y coste.
- [x] 8.2 `calibracion(rango)`: Brier y tasa de acierto por fuente, acierto de las sobrescrituras frente al signo propuesto, y gasto acumulado. Por temporada y de las últimas 10 jornadas.
- [x] 8.3 `backtest(temporadas, divisiones, xi, rho)`: walk-forward por fecha frente a cuotas de cierre. Devuelve Brier, log-loss, acierto y n por división y en total; determinista. Comando `quiniela_backtest` que imprime una tabla. *(6 tests; reajuste por semana ISO, con corte en el primer día de la semana; modelo y cuotas medidos sobre el mismo conjunto de partidos.)*

## 9. Vistas, URLs y plantillas (mobile-first 375 px)

- [x] 9.1 `urls.py` con `index`, `jornada_nueva`, `jornada_detalle` y `seguimiento`, más los endpoints HTMX `actualizar_cuotas`, `actualizar_noticias`, `sobrescribir`, `confirmar` y `actualizar_resultados`. Todo con `staff_member_required`.
- [x] 9.2 `quiniela/jornada_form.html`: 15 filas con selects del catálogo y texto libre alternativo. Los errores por fila conservan lo escrito.
- [x] 9.3 `quiniela/jornada.html`: fila por partido con barra 1/X/2, etiqueta de fuente, signo, avisos plegables (Alpine) con enlace a la noticia y banner "avisos no disponibles" si toca.
- [x] 9.4 Partial del boleto: comparativa de configuraciones (coste, P10+, P12+, P14), cuadrícula de 14 signos + Pleno lista para copiar, explicación opcional y botón de confirmar deshabilitado si falta algún signo.
- [x] 9.5 `quiniela/seguimiento.html`: tabla de calibración por fuente, histórico de jornadas con aciertos y gasto acumulado frente a lo ganado.
- [x] 9.6 `npm run build:css` si aparecen clases o variantes nuevas de Tailwind. *(Compilado en 8,6 s. Además: resultado manual por partido tras el cierre, botón "Copiar signos" y selector de jornada.)*

## 10. Tests (`src/apps/quiniela/tests/`)

- [x] 10.1 Datos: alias que resuelven al mismo equipo; ingesta idempotente (reimportar no duplica); formato inválido sin escrituras parciales; partido de cuotas asociado por fecha ±1 día.
- [x] 10.2 Pronóstico: probabilidades de cuotas que suman 1; precedencia cuotas > modelo > uniforme; el modelo no usa partidos con fecha ≥ corte; la distribución del Pleno suma 1; el equipo con más goles a favor recibe más λ.
- [x] 10.3 Avisos: un aviso con URL ajena se descarta; tipo desconocido → "otro"; con Gemini caído (mock) la jornada se renderiza con el banner; los avisos no alteran `Pronostico`.
- [x] 10.4 Boleto: configuraciones con 5 €, 3 € y precio 1 €; el doble va al partido más incierto; la DP coincide con fuerza bruta en un caso pequeño; una sobrescritura que excede el tope se rechaza; no se confirma con partido "sin datos" ni con la jornada cerrada; el boleto confirmado es inmutable.
- [x] 10.5 Seguimiento: un doble "1X" con empate cuenta acierto; Brier calculado a mano en 3 partidos; backtest determinista en dos ejecuciones.
- [x] 10.6 Vistas: un no staff → redirección al login; las páginas principales responden 200; los endpoints HTMX devuelven partials.

## 11. Verificación en dev

- [x] 11.1 `docker compose restart web`. Ingerir 3 temporadas de SP1 y SP2 y lanzar `quiniela_backtest`. Pegar la tabla de resultados en design.md (D9) y decidir si ρ o Shin hacen falta. *(1.954 partidos ingeridos. Backtest: modelo 0,605 frente a cuotas 0,585 de Brier; ρ = 0; Shin por defecto.)*
- [ ] 11.2 Dar de alta la jornada real de esta semana, actualizar cuotas y noticias, revisar avisos y fuentes, y comparar las cuatro configuraciones. Confirmar un boleto.
- [ ] 11.3 Revisión visual a 375 px de la jornada, el boleto y el seguimiento.
- [ ] 11.4 Tras la jornada: actualizar resultados y comprobar la evaluación y la calibración.
- [x] 11.5 `docker compose exec web pytest apps/quiniela` en verde y `ruff check src/apps/quiniela` limpio. *(76 tests en verde; ruff limpio salvo E501 en las migraciones autogeneradas, como en el resto de apps.)*
