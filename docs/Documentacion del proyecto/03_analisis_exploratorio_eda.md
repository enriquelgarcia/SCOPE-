# SCOPE — Análisis exploratorio de datos (EDA) v0.1

**Documento narrativo n.º 03**
**Proyecto:** SCOPE — Sports Computational Outcome Prediction Engine
**Fase que describe:** EDA v0.1 (fases E0–E11), sobre los artefactos congelados del Data Pipeline v0.1
**Estado formal de la fase:** SCOPE EDA v0.1 — COMPLETE (2026-11-01). Decisiones resultantes: D46, D47, D48 y D49 (Decision Log).
**Documentos previos:** `01_arquitectura_y_data_contract.md` (arquitectura y reglas) y `02_data_pipeline_v0.1.md` (implementación y artefactos congelados). El Documento 02 conserva deliberadamente el estado histórico del proyecto al cierre del pipeline v0.1; las decisiones posteriores del EDA están en el Decision Log y en este documento.
**Evidencia de referencia:** `reports/eda/eda_report_v0.1.md` (reporte acumulativo con todas las cifras), `reports/eda/tables/` y `reports/eda/figures/` (outputs por fase), `reports/eda/eda_run_manifest.json` (hashes y versiones), `../DECISION_LOG.md`, `../contract/SCOPE_Data_Contract_v0.1.md`, `../quality/data_quality_register_v0.1.md` y `../EDA/EDA.md` (hub de seguimiento).

> Este documento **sintetiza** el EDA; no lo sustituye ni añade reglas. Las cifras proceden del reporte acumulativo y de las tablas de cada fase. Cuando este texto y la documentación normativa (contrato, Decision Log) parezcan decir cosas distintas, prevalece la documentación normativa.

---

## Tabla de contenidos

1. [Objetivo del EDA](#1-objetivo-del-eda)
2. [Datos y scopes](#2-datos-y-scopes)
3. [Calidad y estructura](#3-calidad-y-estructura)
4. [Targets](#4-targets)
5. [Mercado](#5-mercado)
6. [Features](#6-features)
7. [Relaciones](#7-relaciones)
8. [Decisiones estructurales](#8-decisiones-estructurales)
9. [Burn-in](#9-burn-in)
10. [Last5](#10-last5)
11. [Calidad: Q01](#11-calidad-q01)
12. [Drift temporal](#12-drift-temporal)
13. [Limitaciones](#13-limitaciones)
14. [Decisiones cerradas y abiertas](#14-decisiones-cerradas-y-abiertas)
15. [Handoff a modelado](#15-handoff-a-modelado)
16. [Conclusión](#16-conclusión)
17. [Anexo: matriz de trazabilidad por fase](#17-anexo-matriz-de-trazabilidad-por-fase)

---

## 1. Objetivo del EDA

El EDA de SCOPE v0.1 tenía dos propósitos.

El primero era **comprender los datos** antes de entrenar ningún modelo: su calidad, la forma de los targets, el comportamiento de las features pre-partido, sus relaciones y su estabilidad en el tiempo.

El segundo era **resolver con evidencia** un conjunto de cuestiones metodológicas que el contrato dejó abiertas a propósito:
- **M1:** cómo tratar la redundancia entre las representaciones `h_*`, `a_*` y `diff_*`;
- **M3:** qué relación estructural hay entre las ventanas de temporada y last5;
- **P01:** qué umbral mínimo de historial usar (burn-in);
- **P02:** si la ventana last5 aporta algo propio;
- **Q01:** cómo tratar la anomalía de calidad `AST > AS`.

El EDA **no** buscaba elegir modelos ni features. Su papel era dejar la etapa de modelado con un punto de partida comprendido, con las cuestiones estructurales cerradas y con las preguntas que solo el modelado puede responder planteadas con claridad.

## 2. Datos y scopes

**Datos.** El EDA trabaja sobre los artefactos congelados del Data Pipeline v0.1 (D44):
- **Origen:** cinco temporadas de la Premier League (2021/22–2025/26) de Football-Data.co.uk, con **1,900 partidos** y **20 equipos por temporada**. En total aparecen **27 `team_id`** distintos, por el sistema de ascensos y descensos (D27).
- **Cadena de capas:** `RAW → INTERIM → CANONICAL → team_match_log → FEATURES`.
- **CANONICAL:** un partido por fila, 42 campos.
- **team_match_log:** dos filas por partido, una por equipo; es auxiliar.
- **FEATURES v0.1:** 30 columnas, con 21 features de historia previa:
  - temporada: PPG, GF/PG y GA/PG;
  - last5: las mismas tres más SOT/PG;
  - cada una en versión local (`h_`), visitante (`a_`) y diferencia (`diff_`);
  - más los controles `h_`/`a_n_prev_season`.

Todas las features usan solo partidos anteriores al partido que describen (`shift(1)`, reglas T1–T10) y se reinician cada temporada (D14).

**Elegibilidad.** Un partido es elegible para modelado si ambos equipos tienen al menos tres partidos previos en la temporada (D48). Hay **1,749 partidos elegibles**: 350 / 350 / 349 / 350 / 350 por temporada.

**Scopes.** Cada fase del EDA declaró qué datos podía usar. Todo lo que pudiera influir en una decisión debía respetar la separación temporal (D42):

| Scope | Temporadas | Uso |
|---|---|---|
| `ALL_DESCRIPTIVE` | las 5 | Solo descripción y documentación |
| `DEV_PREDICTORS` (DEVX) | 2021/22–2024/25 | Análisis sin targets (*predictor-only*) |
| `TRAIN_TARGET` | 2021/22–2023/24 | Único scope donde se relacionan features con resultados |
| `VAL_DESCRIPTIVE` | 2024/25 | Descripción separada; su target no se usa para decidir |
| `TEST_DESCRIPTIVE` | 2025/26 | Solo descripción; **nunca** genera decisiones |

**Infraestructura (E0–E1).**
- Un módulo común (`src/eda/eda_io.py`) verifica los hashes D44 antes de cargar datos e impone los scopes en la carga.
- Solo permite escribir dentro de `reports/eda/`.
- Cada fase registra sus outputs con SHA-256 en un manifiesto.
- 20 tests automáticos protegen esa infraestructura.

## 3. Calidad y estructura

**Estructura.** E1 confirmó que las dimensiones, el esquema y las cardinalidades coinciden con el contrato, y que `match_id` es único y está alineado entre capas.

**Missingness.**
- Todo es **estructural**: las 21 features de historia están vacías solo en los 50 partidos inaugurales (10 por temporada), cuando ningún equipo tiene historia previa.
- Fuera de esa regla no hay ningún nulo.
- Con el burn-in vigente, el dataset elegible no tiene nulos y **no requiere imputación**.

**Avisos de calidad (`dq_flags`).** Hay 13 filas marcadas, cada una con un solo aviso:
- 1 `AST_GT_AS` (Q01, sección 11);
- 12 `GOALS_GT_SOT`, que el registro de calidad considera plausibles (por ejemplo, autogoles) y solo informativos.

**Política.** RAW no se ha corregido ni modificado en ningún momento (D03). Las anomalías se documentan en el registro de calidad y se tratan, si procede, en capas posteriores. Siguen documentadas, sin corrección:
- Q01 (D49);
- los 12 `GOALS_GT_SOT`;
- Q02 (espacio final en un árbitro, resuelto con `strip()` en INTERIM);
- Q17–Q19 (cuotas anómalas de la fuente, que no son predictores).

**Calendario.** En 2023/24, Burnley y Luton tienen un desfase temprano compatible con un partido aplazado. Por eso esa temporada tiene 349 partidos elegibles en lugar de 350; no es un error del dataset.

## 4. Targets

El problema principal es la clasificación del resultado en **H / D / A** (victoria local, empate, victoria visitante).

**Distribución (E2).** En TRAIN: H 45.8 %, D 22.5 % y A 31.7 %. En las cinco temporadas el orden es el mismo (44.2 / 23.9 / 31.9 %).
- Las clases no son uniformes: el empate es la minoritaria, aproximadamente la mitad que la victoria local.
- Consecuencia práctica: un clasificador que nunca predijera empates podría tener una exactitud aparentemente aceptable. Por eso la exactitud sola no basta para evaluar.

**`goal_difference`.**
- Es una variable **entera y discreta** (D16): mediana 0, media +0.32 en TRAIN, DE 1.99, rango [−8, +9]. El 80 % de los partidos termina con |GD| ≤ 2.
- Su distribución marginal no es normal por construcción. Eso **no** invalida la regresión lineal de Matemáticas, cuyos supuestos se refieren a los residuos; esa validación queda para la fase de Matemáticas (P03, provisional).

**Goles.** La media por partido en TRAIN es 1.65 del local y 1.33 del visitante. La covarianza entre ambos es ligeramente negativa. Su dispersión es cercana a la de una Poisson, pero el EDA no ajustó ninguna distribución (D17).

**Ventaja local.** Descriptivamente, el local gana más y marca más en todos los bloques (ALL, TRAIN, VAL y TEST). El EDA no creó features de localía.

**Variación entre temporadas.** La media de goles totales va de 2.75 a 3.28 por partido, con el máximo en 2023/24, y %H varía entre 40.8 y 48.4. Estas variaciones se describen, no se usan para decidir.

## 5. Mercado

SCOPE sigue la **Estrategia C** (D12, D13, D39): el modelo usa solo features deportivas y el mercado es un **benchmark externo**. **MARKET no entra como predictor en v0.1.** E2m caracterizó ese benchmark sin compararlo todavía con los resultados.

- **Normalización (D39):** `p_i = (1/o_i) / Σ(1/o_j)` produce probabilidades que suman exactamente 1 en los 1,900 partidos.
- **Overround** (suma de probabilidades implícitas por encima de 1 en las cuotas agregadas):
  - medio de 4.52 % en las cuotas previas (pre) y 4.32 % en las de cierre (close);
  - estable en 2021/22–2023/24 (≈ 4.1 %) y más alto en 2024/25 y 2025/26;
  - un cambio en la composición de las casas de apuestas podría contribuir, pero el EDA no lo verificó.
- **Probabilidades implícitas:** la de empate está muy concentrada (DE ≈ 0.05) y nunca supera 0.323. Por eso el empate **nunca** es el favorito del mercado; el local lo es en el 62.7 % de los partidos y el visitante en el 37.2 %.
- **Movimiento pre → close:** es pequeño; la masa de probabilidad redistribuida es de ≈ 1.8 puntos porcentuales de mediana. El favorito cambia en el 3.8 % de los partidos.

**Implicación.** La futura comparación SCOPE frente a mercado deberá hacerse sobre exactamente los mismos partidos elegibles y prestar atención explícita a la clase D. No se evaluaron accuracy, log loss, Brier ni calibración.

## 6. Features

E3 describió las features una a una con datos de desarrollo y sin targets.

- **Escala y forma:**
  - PPG está acotado en [0, 3];
  - GF/PG y GA/PG rondan 1.4–1.5;
  - SOT/PG ronda 4.5, en otra escala, lo que importa para KNN y modelos lineales;
  - las distribuciones son unimodales, con asimetría positiva moderada;
  - E3 no detectó violaciones de dominio en las features bajo las reglas evaluadas (las incidencias de calidad de la fuente, como Q01, se tratan por separado en la sección 11). Los 311 valores extremos que marca el criterio de Tukey son legítimos y se concentran en equipos con poco historial.
- **Inestabilidad temprana:** con 3–5 partidos previos, la dispersión entre equipos de las features de temporada es 1.6–1.8 veces la de los equipos con 21 o más. Con pocos partidos las medias son ruidosas, y eso motivó el estudio del burn-in (sección 9).
- **Local y visitante:** las distribuciones marginales de `h_*` y `a_*` son casi idénticas. Ambas describen el rendimiento **global** previo del equipo que ocupa cada rol, no su rendimiento en casa o fuera. Que se parezcan no las hace intercambiables en un modelo.
- **Diferencias:** las siete `diff_*` están centradas en 0 y son aproximadamente simétricas. El signo hay que leerlo por métrica: en `diff_ga_*`, un valor positivo significa que el local **recibe** más goles.
- **Granularidad de last5:** como promedia como máximo cinco partidos, tiene 13–19 veces menos valores distintos que la ventana de temporada, y la mitad de las filas cae en sus cinco valores más frecuentes. Eso producirá empates en distancias (KNN) y en puntos de corte (árboles).
- **SOT:** solo existe en versión last5. Es la feature con más dispersión en términos absolutos y, en E10, la que más cambió hacia 2025/26.

No se eliminó, transformó ni escaló ninguna feature.

## 7. Relaciones

E4 separó las relaciones entre features (DEVX, sin targets) de las relaciones con el resultado (solo TRAIN).

**Entre features (DEVX):**
- `h_x` y `a_x` están casi incorrelacionadas. La correlación de ≈ ±0.7 de cada una con `diff_x` es en gran parte algebraica: con varianzas parecidas, vale ≈ ±1/√2.
- PPG se asocia fuertemente con GF/PG (+0.82) y GA/PG (−0.78) en la ventana de temporada. SOT se asocia con GF last5 (+0.71).
- Cada métrica está correlacionada con su versión en la otra ventana (0.73–0.78), en parte porque son idénticas mientras `n_prev ≤ 5` (sección 8).
- Pearson y Spearman casi coinciden: las relaciones son esencialmente lineales y monótonas.

**Con el resultado (TRAIN):**
- Las correlaciones con `goal_difference` son de magnitud baja a moderada (|r| 0.17–0.41), todas con el signo esperable.
- Para cada métrica, la versión `diff_` se asocia más que `h_` o `a_` por separado, y la de temporada más que la last5. La mayor es `diff_ppg_season` (+0.41).
- Por clase, las `diff_*` se desplazan como se espera entre H, D y A, pero las tres clases **se solapan ampliamente**. Los empates quedan en medio y cerca de cero, sin estar más concentrados. Si el empate tiene una estructura distinguible con varias features a la vez **sigue sin resolverse**: es una pregunta para el modelado.

Correlación no es selección: ninguna de estas cifras ordena la utilidad de las features dentro de un modelo.

## 8. Decisiones estructurales

### D46 — M1: representaciones h / a / diff

- **Hecho:** como `diff = h − a` exactamente, la matriz que reúne las 21 columnas `h + a + diff` (HADIFF) tiene **rango 14 de 21**, una dependencia por cada terna, con o sin intercepto y con o sin estandarización (E5).
- **Decisión:** HADIFF **no** se usará completa en modelos lineales no regularizados, porque sus coeficientes no tendrían solución única.
- **Alcance:** HA (`h + a`, 14 columnas) y DIFF (7 columnas) siguen siendo representaciones candidatas **distintas y no equivalentes**. DIFF conserva el contraste entre equipos pero pierde los niveles absolutos (D22). La decisión no afirma que HADIFF sea inválida para KNN o árboles.
- **Multicolinealidad no exacta:** dentro de HA y DIFF existe multicolinealidad no exacta (VIF máximo ≈ 11.5 en `ppg_season`). Se describió sin umbrales automáticos.

### D47 — M3: season frente a last5

- **Identidad:** mientras la ventana last5 contiene todo el historial disponible, ambas versiones son **exactamente iguales**. En features de un lado (`h_`, `a_`) eso ocurre con `n_prev ≤ 5`; en las `diff_` solo cuando **ambos** equipos están en esa zona, `max(h_n, a_n) ≤ 5` (E6).
- **Fuera de esa zona:** dejan de ser idénticas. Mantienen una correlación considerable (≈ 0.64–0.75) y un MAE entre ambas que crece con el historial, pero no hay dependencia lineal exacta.
- **Alcance:** D47 resuelve la **estructura**, no la utilidad predictiva de last5 (sección 10).

### D48 — Burn-in v0.1

Se mantiene `k = 3` (`min(h_n_prev, a_n_prev) ≥ 3`), por parsimonia y rendimientos decrecientes. **No es un óptimo matemático.** Ver sección 9.

### D49 — Q01

Se conservan los valores originales de la fuente y su flag de calidad, sin reparación determinista, y RAW permanece inmutable. Ver sección 11.

No se creó ninguna decisión posterior a D49.

## 9. Burn-in

E7 evaluó umbrales `k = 1…6` con dos tipos de evidencia que no se mezclan:
- **estabilidad sin targets (DEVX):** dispersión y extremos de las features según el historial;
- **estabilidad retrospectiva (solo TRAIN):** distancia entre la estimación disponible tras `n` partidos y la media final de la temporada del mismo equipo. Esta referencia usa información futura a propósito, solo como diagnóstico; nunca es una feature.

**Coste.** Es prácticamente lineal y conocido de antemano: cada paso desde 2→3 excluye exactamente 40 partidos de desarrollo (30 de TRAIN), es decir ≈ 2.6 puntos de retención. El paso 1→2 cuesta uno más por la irregularidad de calendario de 2023/24.

**Beneficio.** El error medio de PPG frente a la referencia baja así:

| n | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| MAE de PPG | 1.17 | 0.73 | 0.58 | 0.52 | 0.48 |

- 1→2 mejora en las cuatro métricas.
- 2→3 es el **último paso** con una mejora respaldada en la mayoría de métricas: el intervalo bootstrap excluye cero en PPG, GF y SOT, no en GA.
- 3→4 y 4→5 aportan mejoras pequeñas e inciertas al mismo coste.

**Decisión (D48):** `k = 3`. No se demostró que k = 4 o k = 5 sean peores. Las features siguen siendo ruidosas con cualquier umbral razonable. Durante el modelado podrá hacerse un análisis de sensibilidad con k = 4 / k = 5 usando TRAIN y validación, nunca TEST.

## 10. Last5

Last5 pasó por dos fases, y sus conclusiones no se contradicen:

1. **E6 / D47 (estructura).** Después del quinto partido, last5 es **estructuralmente distinta** de la ventana de temporada: deja de ser idéntica y no es redundante en sentido algebraico.
2. **E8 (utilidad plausible).** Ser distinta no implica aportar una señal útil:
   - **Responsividad:** last5 es ≈ 3.7–4.3 veces más responsiva; se mueve mucho más de un partido al siguiente, porque solo recuerda cinco partidos.
   - **Asociación:** en TRAIN, last5 se asocia con el desempeño del partido **menos** que la ventana de temporada en PPG y GF (Spearman 0.19 frente a 0.26 y 0.18 frente a 0.26; el intervalo de la diferencia queda por debajo de 0). En GA no es concluyente.
   - **Persistencia:** la desviación reciente (last5 menos temporada) **no muestra persistencia clara** en el partido siguiente, salvo un indicio débil en GA.
   - **Lectura:** el movimiento adicional de last5 se comporta mayoritariamente como variación transitoria en estos diagnósticos univariados.

Por tanto, last5 es **distinta pero no validada**. El EDA no puede confirmarla ni descartarla, porque la pregunta decisiva es si aporta valor **incremental** dentro de un modelo. **P02 sigue abierta** y se resolverá comparando, dentro de una representación coherente, features `season` frente a `season + last5`, con TRAIN y validación y nunca con TEST. last5 permanece en FEATURES v0.1.

## 11. Calidad: Q01

**La anomalía.** El partido Newcastle United – West Ham United del 15/08/2021 (`PL_2021-2022_raw.csv`, fila 9) contiene en la fuente `AS = 8` tiros del visitante y `AST = 9` tiros a puerta. Eso viola `AST ≤ AS`.

**Origen y extensión (E9).**
- Es una **inconsistencia de la fuente**: ya existe en RAW, y el pipeline la preserva sin alterarla y la marca con `AST_GT_AS`.
- Es el único caso: no hay ningún `HST > HS`.
- El valor entra en los tiros a puerta de West Ham y, como las features solo usan partidos anteriores, no contamina el propio partido.
- Afecta a `sot_pg_last5` (y su `diff`) en los **5 partidos siguientes** de West Ham, de los cuales **3 son elegibles**, todos en TRAIN. VALIDATION y TEST no se ven afectados.

**Lo que no se sabe.** Sin una fuente externa, no puede saberse si el error está en AS, en AST o en ambos.
- Si AS fuese correcto y AST debiera bajar a 8, el cambio en las filas elegibles sería como máximo ≈ 0.33 tiros a puerta por partido.
- Si AST fuese correcto y el error estuviera en AS, las features SOT no cambiarían.

Ninguno de los dos escenarios es la «corrección verdadera».

**Decisión (D49).** v0.1 conserva los valores originales y el flag, sin reparación. La anomalía está **localizada en extensión**, aunque su magnitud real se desconoce. Cualquier reparación futura irá en una capa derivada, versionada y con una decisión explícita, y nunca modificará RAW.

## 12. Drift temporal

E10 midió, sin targets y con las filas elegibles, cuánto cambian las distribuciones de las features entre temporadas. Usó dos medidas descriptivas, sin umbrales:
- **SMD:** diferencia de medias en unidades de desviación típica;
- **KS:** máxima distancia entre las distribuciones acumuladas.

**Lo que muestra:**
- **Pico de 2023/24.** Las features de nivel de goles y tiros a puerta suben claramente en 2023/24 (SMD +0.27 a +0.41 respecto a 2022/23) y en parte vuelven en 2024/25. El pico persiste entre los 17 equipos presentes en ambas temporadas, así que no se explica solo por los ascensos y descensos. La composición sí parece influir parcialmente en otras transiciones.
- **TRAIN → VALIDATION.** El desplazamiento de medias es muy pequeño (|SMD| ≤ 0.030), con algunos cambios de forma o dispersión; por ejemplo, GF de temporada está más concentrada en 2024/25. TRAIN es internamente heterogéneo: sus saltos entre temporadas son mayores que el salto hacia VALIDATION.
- **Lo estable.** PPG local y visitante cambia poco de centro. Las `diff_*` son muy estables, porque un cambio que afecta a toda la liga se cancela al restar. Local y visitante cambian de forma casi idéntica.
- **FINAL TEST (2025/26, descriptivo y no decisional).** Niveles más bajos y menos dispersos de goles y tiros a puerta (SOT last5 SMD ≈ −0.29). Esto documenta una diferencia de distribución que habrá que tener en cuenta al interpretar el desempeño final, **pero no modifica el protocolo**.
- **Pipeline.** No hay indicio técnico de que el drift provenga del pipeline: las columnas fuente de las features están completas en las cinco temporadas, y los cambios de esquema RAW (106 / 106 / 106 / 120 / 132 columnas) afectan solo a columnas de cuotas.

## 13. Limitaciones

- **Pocas temporadas:** con solo cinco no se puede separar una tendencia de la variación entre temporadas.
- **Observaciones dependientes:** los equipos se repiten y las ventanas se solapan. Los intervalos son descriptivos (bootstrap por equipo-temporada cuando se usó) y no hubo tests de significancia.
- **Composición cambiante:** tres equipos entran y tres salen cada temporada.
- **Last5 discreta:** pocos valores distintos, con empates en distancias y en cortes.
- **Ruido temprano:** las features siguen siendo ruidosas con pocos partidos, incluso con el burn-in.
- **Empates:** el target multiclase tiene una clase minoritaria (D) con un solapamiento univariado amplio.
- **Alcance de E8:** es univariado; no mide valor incremental.
- **Alcance de E10:** el drift es marginal (columna a columna), no multivariable.
- **Q01:** su valor verdadero se desconoce.
- **TEST no plenamente ciego:** algunas estadísticas descriptivas agregadas de 2025/26 ya se conocían (D42).
- **Sin causalidad:** todas las relaciones son asociaciones.
- **Sin evaluación predictiva todavía:** no hay importancia de features ni comparación predictiva; eso corresponde al modelado.

## 14. Decisiones cerradas y abiertas

| Tema | Estado | Evidencia | Decisión / siguiente paso |
|---|---|---|---|
| M1 — h/a/diff | **Cerrado (D46)** | E5: rango 14/21 | No usar HADIFF completo en lineales no regularizados; HA y DIFF candidatas |
| M3 — season vs last5 | **Cerrado (D47)** | E6: identidad solo en la zona inicial | Estructura resuelta; utilidad en P02 |
| Burn-in (P01) | **Cerrado (D48)** | E7: rendimientos decrecientes | k = 3; sensibilidad opcional k = 4/5 (TRAIN/VAL) |
| Q01 — AS/AST | **Cerrado (D49)** | E9: inconsistencia de fuente localizada | Valores fuente + flag; sin reparación |
| Ventana last5 | **Abierto (P02)** | E6 + E8 | Comparación incremental en modelado (TRAIN/VAL) |
| Subconjuntos d = 5 / d = 10 | **Abierto (P04)** | E5, E8, E9, E10 | Resolver en modelado (TRAIN/VAL) |
| `goal_difference` como respuesta OLS | **Abierto (P03)** | E2 | Validar con residuos en Matemáticas |
| Split temporal | **Abierto (P06)** | D35, D42 | Protocolo operativo temporal vigente y provisional: Train 2021/22–2023/24 / Val 2024/25 / Final test 2025/26; P06 sigue abierta |
| Zona horaria | **Abierto (P07)** | — | Definir al incorporar otras fuentes |
| C01–C06 | **Pendiente docente** | Decision Log §3 | Confirmar con los profesores (scraping, n mínimo, logística binaria o multinomial, medición de tiempos, rúbricas) |

## 15. Handoff a modelado

Requisitos que debe respetar la etapa de ML. Se distingue su origen: decisión aprobada, regla del contrato, requisito de rúbrica, requisito docente comunicado o decisión del equipo.

1. **Split (protocolo operativo temporal vigente y provisional; P06 sigue abierta; D35, D42):** TRAIN = 2021/22–2023/24, VALIDATION = 2024/25 y FINAL TEST = 2025/26. No es una decisión formal cerrada.
2. **TEST (D35, D42):** nunca se usa para seleccionar features, modelos, hiperparámetros, umbrales, escalado, calibración ni tratamiento de anomalías.
3. **Burn-in (D48):** `k = 3`. La sensibilidad k = 4 / k = 5 es opcional y solo con TRAIN/VAL.
4. **Representaciones (D46, D22):**
   - HADIFF no se usa completa en modelos lineales no regularizados;
   - HA y DIFF se tratan como representaciones distintas.
5. **Subconjuntos (D19):** cada modelo declara su subconjunto de features explícitamente.
6. **P02:** evaluar el valor incremental de last5 (season frente a season + last5), con TRAIN/VAL.
7. **P04:** resolver los subconjuntos d = 5 / d = 10 con TRAIN/VAL. D22 y D23 siguen vigentes para Complejidad.
8. **Escalado (contrato T8):** si se usa, se ajusta solo con train.
9. **Modelos (requisito docente comunicado; respaldo documental/rúbrica pendiente, C06):** al menos cuatro, incluida una baseline. Los iniciales considerados son baseline, regresión logística multinomial, KNN, árbol de decisión y Random Forest.
10. **Complejidad (D23, rúbrica):** KNN y regresión logística se implementan a mano por el estudiante, sin IA.
11. **Métricas de clasificación:** matriz de confusión, y precision, recall y F1 por clase, además de accuracy.
12. **Métricas probabilísticas (contrato §10 y §12):** log loss, Brier multiclase y calibración. La convención exacta se define en ML.
13. **Mercado (D12, D13, D39):** solo benchmark externo (pre principal, close secundario), sobre los mismos partidos elegibles.
14. **Q01 (D49):** no se corrige en v0.1; excluir las filas afectadas, como mucho, como sensibilidad opcional.
15. **Interpretación final (D42, E10):** el desempeño en TEST se interpretará teniendo en cuenta su diferencia de distribución, sin modificar el protocolo.

**El EDA no decidió:** el modelo final, el feature set final, HA frente a DIFF por desempeño, la permanencia definitiva de last5, el escalado definitivo, la regularización, los hiperparámetros, la calibración, los umbrales, la mejor ventana temporal, el mejor algoritmo ni el desempeño final.

## 16. Conclusión

El EDA v0.1 deja una imagen coherente de los datos:
- un dataset íntegro, con missingness solo estructural y una única inconsistencia de fuente, documentada y localizada;
- un target multiclase con empates minoritarios y difíciles de separar univariadamente;
- features regulares, ruidosas al inicio de temporada y con una ventana last5 muy discreta;
- relaciones con el resultado moderadas y coherentes;
- distribuciones observadas que difieren de nivel entre temporadas, compatibles con variación de la liga y de la composición de equipos (interpretación, no demostración causal) y sin indicio técnico de que el pipeline sea la causa.

Las cuatro cuestiones estructurales quedaron cerradas con evidencia (D46–D49), sin presentar ninguna como óptima ni definitiva más allá de lo demostrado. Las preguntas que solo un modelo puede responder (el valor incremental de last5, P02; los subconjuntos de features, P04; y la comparación de representaciones) quedan delimitadas para la etapa de modelado. No son las únicas cuestiones abiertas: P03, P06 y P07 siguen provisionales y C01–C06 pendientes de confirmación docente (sección 14). Las decisiones de modelado se tomarán con TRAIN y VALIDATION como único terreno de decisión, y 2025/26 queda reservado para la evaluación final.

## 17. Anexo: matriz de trazabilidad por fase

Versión tabular en `reports/eda/tables/e11_eda_phase_summary__ALL.csv`: 12 filas, E0 (infraestructura) y las 11 fases analíticas E1, E2, E2m, E3, E4, E5, E6, E7, E8, E9 y E10. E11 no tiene fila porque es la síntesis de las anteriores.

| Fase | Pregunta | Conclusión | Decisión | Implicación |
|---|---|---|---|---|
| E0 | Organización y scopes | Infraestructura reproducible, scopes estrictos | — | Datos congelados; escritura solo en `reports/eda/` |
| E1 | Estructura y calidad | Sin missingness inesperado; 1,749 elegibles | — | Sin imputación con k = 3 |
| E2 | Targets | D minoritaria; GD discreta | P03 abierta | Métricas sensibles a D |
| E2m | Mercado | Benchmark coherente | D12/D13/D39 | Solo benchmark |
| E3 | Features | Regulares; ruido temprano; last5 discreta | — | Escalado y empates en KNN/árboles |
| E4 | Relaciones | Moderadas; D con solapamiento | — | Correlación no es selección |
| E5 | M1 | HADIFF singular | D46 | HA / DIFF por separado |
| E6 | M3 | Identidad solo en la zona inicial | D47 | Utilidad en P02 |
| E7 | Burn-in | k = 3 por parsimonia | D48 | Sensibilidad k = 4/5 opcional |
| E8 | last5 | Distinta, no validada | P02 abierta | Comparación incremental |
| E9 | Q01 | Inconsistencia de fuente localizada | D49 | Fuente + flag |
| E10 | Drift | Cambios de nivel observados entre temporadas; TEST distinto (descriptivo) | — | Interpretar TEST con cautela |
| E11 | Síntesis | EDA v0.1 completo | — | Handoff a modelado |
