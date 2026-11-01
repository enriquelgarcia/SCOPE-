# SCOPE — EDA Report v0.1

> Fase EDA de SCOPE v0.1. Pipeline de datos `COMPLETED / FROZEN` (D44).
> Outputs y hashes: `reports/eda/eda_run_manifest.json`. Código: `src/eda/`.

## E1 — Estructura, calidad y elegibilidad

**Scope:** `ALL_DESCRIPTIVE` (2021/22–2025/26). E1 es descriptivo: no analiza el target (sin distribuciones H/D/A ni de goles), no calcula correlaciones y no toma decisiones metodológicas. Sin aleatoriedad.

**Tablas** (`reports/eda/tables/`):

| Tabla | Contenido |
|---|---|
| `e01_schema_missingness__ALL.csv` | Una fila por columna de CANONICAL (42) y FEATURES (30): tipo lógico del contrato, dtype físico cargado, rol conceptual, no nulos, nulos, % nulos, valores únicos |
| `e01_features_missingness_by_history__ALL.csv` | Nulos de las 21 features históricas por temporada y por historial del lado correspondiente (`n_prev = 0` / `≥ 1`) |
| `e01_history_eligibility__ALL.csv` | Partidos, elegibles y no elegibles por temporada y nivel de historial (0–5, 6+) para `h_`, `a_` y el mínimo de ambos |
| `e01_quality_summary__ALL.csv` | 127 comprobaciones e indicadores (integridad, dimensiones, alineación, cardinalidades, constantes, `dq_flags`, missingness, historial, elegibilidad) con `PASS`/`FAIL`/`INFO` |
| `e01_dq_flagged_rows__ALL.csv` | Las 13 filas con `dq_flags` y los valores que activan cada flag |

Las tablas 4 y 5 adicionales separan dos granularidades distintas: el resumen agregado (tabla 3) no puede contener a la vez la matriz columna × temporada × historial ni el listado de filas afectadas sin perder legibilidad.

Resultado global: **67 PASS, 60 INFO, 0 FAIL.**

### Integridad de entrada

Los cuatro SHA-256 congelados en D44 coinciden antes del análisis (`eda_io.verify_frozen_inputs()`; cada cargador vuelve a verificar su archivo):

| Artefacto | SHA-256 |
|---|---|
| INTERIM | `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad` |
| CANONICAL | `06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1` |
| team_match_log | `0032af2965604d556b337a5d8c1f4ce6b5ac95ca931d82b99651a4f00c03ab02` |
| FEATURES | `a18c47888a38a80585ae97930f81a4ad6fc4497315af63ef05f284352ca9b356` |

### Estructura

| Artefacto | Dimensiones | Esperado |
|---|---|---|
| CANONICAL | 1,900 × 42 | ✅ |
| FEATURES | 1,900 × 30 | ✅ |
| team_match_log | 3,800 × 10 (= 2 × 1,900) | ✅ |

- Carga **tipada según el contrato** (§4.9, §5.4), no según la inferencia de pandas: todo se lee como texto y se convierte por tipo lógico (fechas con formato estricto `YYYY-MM-DD` / `YYYY-MM-DDTHH:MM:SS`, booleanos `true`/`false`, `feature_version` como string).
- Diferencias tipo físico ↔ conceptual relevantes: `kickoff_time` (lógico `time`) y `result`/`ht_result` (lógico `categorical`) se cargan como `string`; `source_row` y `match_seq_season` son `int64` pero su rol es trazabilidad / orden auxiliar, **no** frontera temporal (T5); `n_prev_season` es `int64` con rol de control, no de predictor.
- `match_id` está alineado fila a fila entre CANONICAL y FEATURES y es único.
- Cardinalidades CANONICAL: 5 temporadas; 380 partidos y 20 equipos por temporada; **39 árbitros** distintos (22/23/28/26/23 por temporada; sin análisis de efecto).
- Composición de equipos: en las cinco temporadas aparecen **27 `team_id` distintos** en total (D27). Cada transición de temporada incorpora tres equipos que no estaban en la temporada anterior (y, al haber 20 por temporada, salen otros tres), como consecuencia del sistema de ascensos y descensos. "Incorporado" significa ausente en la temporada inmediatamente anterior, no nunca visto: Burnley se incorpora en 2023/24 y de nuevo en 2025/26. Detalle por transición en `e01_quality_summary__ALL.csv` (`teams_new_vs_previous_season`).
- `kickoff_datetime` tiene 1,139 valores distintos para 1,900 partidos: los kickoffs simultáneos son habituales (compatibles con D36, que exige orden estricto solo dentro del historial de cada equipo).
- Constantes: `competition_code = EPL`, `source_name = football-data.co.uk`, `source_div = E0`, `feature_version = "0.1"` (un único valor cada una). No son predictores.
- Observación descriptiva: las features `last5` tienen muy pocos valores distintos (p. ej. `h_ppg_last5`: 28; `diff_ppg_last5`: 86) frente a las de temporada (`h_ppg_season`: 601; `diff_ppg_season`: 1,161), porque son promedios de como máximo 5 partidos. Su implicación (empates en distancias, discretización) se evaluará en fases posteriores; E1 no decide nada.

### Missingness

**Missingness esperado por construcción** (contrato §5.3, §9): si un equipo no tiene partidos previos en la temporada (`n_prev_season = 0`), sus tasas y ventanas no existen y quedan vacías, sin imputación.

**Missingness inesperado:** cualquier nulo fuera de esa regla. **No se encontró ninguno.**

Hechos verificados:

- CANONICAL: ninguna columna tiene nulos salvo `dq_flags` (1,887 vacíos = filas sin aviso, representación normativa D33).
- FEATURES: exactamente 21 columnas con nulos (7 `h_*`, 7 `a_*`, 7 `diff_*`), **50 nulos cada una** (10 por temporada). Claves, `n_prev_season`, targets, `is_modeling_eligible` y `feature_version` no tienen nulos.
- `h_*` es nulo **si y solo si** `h_n_prev_season = 0`; `a_*` si y solo si `a_n_prev_season = 0`; `diff_*` si y solo si `min(h, a) = 0`. Con historial ≥ 1 hay 0 nulos en 38,850 celdas.
- Las 50 filas con `h_n_prev_season = 0` son **las mismas** 50 filas con `a_n_prev_season = 0`: los 10 partidos inaugurales de cada temporada, en los que ambos equipos debutan. Por eso los nulos están concentrados en 50 partidos, no en 100.

Estos nulos no son un problema de calidad: son la representación correcta de "no hay información previa".

### Historial disponible

Partidos por `min(h_n_prev_season, a_n_prev_season)`:

| Nivel | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 | Total |
|---|---|---|---|---|---|---|
| 0 | 10 | 10 | 10 | 10 | 10 | 50 |
| 1 | 10 | 10 | **11** | 10 | 10 | 51 |
| 2 | 10 | 10 | 10 | 10 | 10 | 50 |
| 3 | 10 | 10 | 10 | 10 | 10 | 50 |
| 4 | 10 | 10 | 10 | 10 | 10 | 50 |
| 5 | 10 | 10 | 10 | 10 | 10 | 50 |
| 6+ | 320 | 320 | **319** | 320 | 320 | 1,599 |

- Por lado, la distribución es casi idéntica. Solo 2023/24 se desvía de 10 por nivel (`h`: 10/10/11/8/12/8 en los niveles 0–5; `a`: 10/10/9/12/8/12), por el desfase de calendario descrito en Elegibilidad.
- `n_prev_season` va de 0 a 37 en ambos lados (V12).
- Desfase de calendario local/visitante (`|h_n_prev − a_n_prev|`): máximo 4 (2021/22), 3 (2022/23), 2 (2023/24) y 1 (2024/25, 2025/26). Partidos con desfase ≥ 2: 51 / 20 / 4 / 0 / 0. Los aplazamientos se concentran en las dos primeras temporadas. Es descriptivo y confirma que las tasas por partido son necesarias (política MVP).

### Elegibilidad

- `is_modeling_eligible == (min(h_n_prev_season, a_n_prev_season) ≥ 3)` en las 1,900 filas.
- Elegibles: **350 / 350 / 349 / 350 / 350 = 1,749**. No elegibles: **151** (30 / 30 / 31 / 30 / 30).
- Los no elegibles están **exclusivamente** en los niveles 0 (50), 1 (51) y 2 (50) del mínimo. No hay ninguna fila no elegible con mínimo ≥ 3, y ninguna fila elegible tiene features vacías (V13).
- 150 filas elegibles tienen al menos un lado con `n_prev ≤ 5` (148 con ambos), la zona donde `last5 = season` por construcción (M3). Es un dato para E6, no una conclusión.

**Por qué 2023/24 tiene 349.** Burnley y Luton Town no juegan en la segunda ventana de jornada: entre su primer partido (11/08 y 12/08) y el segundo (27/08 y 25/08) no tienen ninguno. Su enfrentamiento directo se jugó el 03/10/2023, lo que es consistente con un partido aplazado. FEATURES no tiene columna de jornada (Q08), así que el aplazamiento se infiere y no puede demostrarse con estos datos. Consecuencia: ambos equipos llegan a principios de septiembre con 2 partidos en lugar de 3.

- Chelsea–Luton (25/08) queda en el nivel 1, lo que explica la fila extra en ese nivel.
- Luton–West Ham (01/09) y Burnley–Tottenham (02/09) quedan en el nivel 2.
- El Burnley–Tottenham es la **única** fila no elegible de todo el dataset que se juega después de que ya existan partidos elegibles en su temporada.

### Calidad

| Flag | Total | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 |
|---|---|---|---|---|---|---|
| sin flags | 1,887 | | | | | |
| `HST_GT_HS` | 0 | 0 | 0 | 0 | 0 | 0 |
| `AST_GT_AS` | 1 | 1 | 0 | 0 | 0 | 0 |
| `GOALS_GT_SOT` | 12 | 3 | 2 | 3 | 2 | 2 |

- No hay combinaciones: ninguna fila tiene más de un flag.
- El recálculo independiente de cada condición sobre los valores coincide con los flags: 1, 0 y 12.
- `AST_GT_AS`: Newcastle–West Ham, 15/08/2021 (`AS = 8`, `AST = 9`). Es Q01 y se analiza en E9.
- Las 12 filas `GOALS_GT_SOT` coinciden con el registro de calidad §2.2 (listado en `e01_dq_flagged_rows__ALL.csv`).
- No se corrigió ni excluyó ningún dato.

### Hallazgos E1

**Hechos observados**

1. Las cuatro entradas están íntegras (D44). Las dimensiones, el esquema y las cardinalidades coinciden con el contrato.
2. Todo el missingness de FEATURES es estructural: 50 partidos inaugurales × 21 features, ligado exactamente a `n_prev_season = 0`. No hay missingness inesperado.
3. La elegibilidad reproduce exactamente la regla provisional: 1,749 filas elegibles. Las 151 excluidas son los partidos con mínimo de historial 0–2.
4. Las 349 elegibles de 2023/24 se deben a un desfase de calendario temprano de Burnley y Luton.
5. Hay 13 filas con un único flag cada una y sin anomalías nuevas.
6. Las features `last5` son mucho más discretas que las de temporada.
7. La irregularidad de calendario es mayor en 2021/22 y 2022/23.

**Interpretación (provisional, sin decisiones)**

- Con FEATURES v0.1, cualquier umbral de burn-in `k` excluye aproximadamente 10 partidos por temporada y por nivel; el coste en filas de cada umbral es casi lineal y conocido de antemano. Esto describe el coste, no el beneficio, que es lo que debe evaluar E7.
- Bajo la regla actual el dataset elegible no tiene nulos, así que el modelado no necesita imputación con este umbral.

### Decisiones

- **E1 no cierra ninguna decisión metodológica.**
- **P01** (burn-in) sigue abierta: E1 no evalúa si el umbral 3 es correcto u óptimo.
- **P02** (ventana last5) sigue abierta.
- **M1** (representación h / a / diff) sigue abierta.
- **M3** (redundancia season / last5) sigue abierta.
- E1 no selecciona ni elimina features.
- E1 no realiza modelado.
- No se modificó ningún dato: RAW, INTERIM, CANONICAL, team_match_log y FEATURES siguen intactos.

## E2 — Targets

**Scopes.**
- `ALL_DESCRIPTIVE` (5 temporadas): solo descripción.
- `TRAIN_TARGET` (2021/22–2023/24): el único scope target-aware utilizable en el futuro para decisiones. En E2 también se usa solo de forma descriptiva.
- VAL (2024/25) y TEST (2025/26) aparecen como filas separadas y **no** se usan para justificar nada (D42).

**Datos y método.** Columnas de CANONICAL: `season`, `match_id`, `home_goals`, `away_goals`, `result`, `goal_difference`, y `total_goals = home_goals + away_goals` calculado aquí. No se usan los goles al descanso, otras estadísticas POST ni MARKET. Sin aleatoriedad.

**Convenciones de las tablas.**
- `level = season`: una fila por temporada.
- `level = scope_total` con `season = ALL`: agregado de **todas las temporadas del scope del archivo**. En un archivo `__TRAIN` es el agregado 2021/22–2023/24, no el de las 5 temporadas.
- Wilson al 95 %. Varianza y desviación estándar muestrales (ddof = 1). Asimetría y curtosis en exceso con los estimadores ajustados de pandas.

**Outputs.**

| Archivo | Contenido |
|---|---|
| `tables/e02_result_distribution__ALL.csv`, `__TRAIN.csv` | Conteos, proporciones e IC de Wilson de H/D/A por temporada y agregado |
| `tables/e02_goal_difference_summary__ALL.csv`, `__TRAIN.csv` | Estadísticos de `goal_difference` |
| `tables/e02_goal_difference_frequency__ALL.csv`, `__TRAIN.csv` | Frecuencia de cada valor entero de `goal_difference` |
| `tables/e02_goals_summary__ALL.csv`, `__TRAIN.csv` | Goles local, visitante y total: posición, dispersión, cuantiles y varianza/media |
| `tables/e02_season_summary__ALL.csv` | Resumen por temporada (§E2.5) y comprobación signo ↔ resultado |
| `tables/e02_home_advantage__ALL.csv` | Ventaja local descriptiva separada en ALL / TRAIN / VAL / TEST |
| `figures/e02_result_distribution_by_season__ALL.png` | Proporciones H/D/A por temporada |
| `figures/e02_goal_difference_distribution__TRAIN.png` | Barras por valor entero de `goal_difference`, solo TRAIN |

Además de las 6 tablas mínimas hay 4 más:
- las frecuencias de `goal_difference` (por temporada y valor) tienen otra forma que su resumen;
- el resumen por temporada y la tabla de localía responden a §E2.5 y §E2.4 y necesitan columnas propias;
- la tabla de localía es `__ALL` porque compara los cuatro grupos en una sola tabla descriptiva.

### Result H / D / A

`result` se trata como variable **nominal** de tres categorías, sin orden ni codificación numérica.

| Grupo | n | H | D | A |
|---|---|---|---|---|
| ALL | 1,900 | 839 · **44.2 %** [41.9, 46.4] | 454 · **23.9 %** [22.0, 25.9] | 607 · **31.9 %** [29.9, 34.1] |
| TRAIN | 1,140 | 522 · **45.8 %** [42.9, 48.7] | 257 · **22.5 %** [20.2, 25.1] | 361 · **31.7 %** [29.0, 34.4] |

Entre corchetes: IC de Wilson al 95 %. Los intervalos suponen partidos independientes, lo que es una aproximación porque los equipos se repiten, así que deben leerse como orientativos.

### Desbalance descriptivo

- **HECHO (TRAIN).** H 45.8 %, A 31.7 %, D 22.5 %. El IC de H está por encima de 1/3 y el de D por debajo. El de A [29.0, 34.4] contiene 1/3.
- **HECHO (ALL).** El mismo orden: H > A > D.
- **INTERPRETACIÓN.** La distribución de clases no es uniforme. La clase más frecuente es la victoria local y la menos frecuente el empate. El desbalance es moderado: la clase menor (D) supone aproximadamente la mitad de la mayor (H).
- **IMPLICACIÓN FUTURA.** La evaluación de los clasificadores deberá tener en cuenta que las clases tienen frecuencias distintas. En particular, un clasificador que nunca prediga D puede tener una exactitud aparentemente aceptable. Cómo tratarlo (métricas, pesos, umbrales) se decidirá en la fase de modelado y solo con TRAIN.

### Goal difference

| Estadístico | ALL | TRAIN |
|---|---|---|
| n | 1,900 | 1,140 |
| media | 0.268 | 0.315 |
| mediana | 0 | 0 |
| desviación estándar | 1.900 | 1.993 |
| varianza | 3.610 | 3.974 |
| mín / máx | −8 / +9 | −8 / +9 |
| Q1 / Q3 / IQR | −1 / 1 / 2 | −1 / 2 / 3 |
| asimetría | −0.004 | 0.022 |
| curtosis en exceso | 0.744 | 0.817 |

Frecuencias en TRAIN (proporción de partidos):

| −3 | −2 | −1 | 0 | +1 | +2 | +3 |
|---|---|---|---|---|---|---|
| 4.6 % | 9.1 % | 15.1 % | 22.5 % | 20.4 % | 13.2 % | 7.1 % |

**HECHOS (TRAIN).**
- El valor más frecuente es 0 (22.5 %).
- El 58.1 % de los partidos termina con |GD| ≤ 1 y el 80.4 % con |GD| ≤ 2.
- Solo 37 partidos (3.2 %) tienen |GD| ≥ 5. Los extremos son −8 (1 partido) y +9 (1 partido).
- La masa está desplazada hacia valores positivos: +1 (20.4 %) frente a −1 (15.1 %), +2 (13.2 %) frente a −2 (9.1 %).

**Q3 e IQR.** Q3 vale 2 en TRAIN y 1 en ALL, pero es un efecto de la discretización: el percentil 75 cae justo en el salto entre 1 y 2. No es una diferencia sustantiva de dispersión.

**INTERPRETACIÓN.**
- `goal_difference` es una variable **entera y discreta** (D16), concentrada en pocos valores y con un pico en 0.
- La asimetría casi nula convive con una media positiva y más masa en el lado positivo.
- La curtosis en exceso positiva (≈ 0.8) indica colas algo más pesadas que una normal con la misma varianza.
- No se asume normalidad. Esto describe la distribución **marginal** de la respuesta: OLS no exige que `goal_difference` sea normal (sus supuestos se refieren a los errores, condicionados a los predictores). Esta fase no hace contrastes ni regresión.

**Relación conceptual entre targets.** En todas las temporadas, `goal_difference > 0 ⇔ H`, `= 0 ⇔ D` y `< 0 ⇔ A`. Esto ya lo garantizaba el pipeline (V09); aquí solo se documenta y **no es un hallazgo nuevo**.
- `result` resume el signo de `goal_difference`. Por eso es el target natural de la **clasificación** probabilística H/D/A (ML).
- `goal_difference` conserva la magnitud del resultado. Por eso es la respuesta numérica de la **regresión lineal múltiple** de Matemáticas Aplicadas (P03 sigue provisional).
- Ambos describen el mismo partido, así que nunca pueden usarse uno como predictor del otro.

### Goles

| Variable | Grupo | media | mediana | varianza | DE | mín–máx | Q10 / Q25 / Q75 / Q90 | var / media |
|---|---|---|---|---|---|---|---|---|
| home_goals | ALL | 1.597 | 1 | 1.737 | 1.318 | 0–9 | 0 / 1 / 2 / 3 | 1.088 |
| home_goals | TRAIN | 1.649 | 1 | 1.891 | 1.375 | 0–9 | 0 / 1 / 2 / 3 | 1.147 |
| away_goals | ALL | 1.330 | 1 | 1.450 | 1.204 | 0–8 | 0 / 0 / 2 / 3 | 1.091 |
| away_goals | TRAIN | 1.334 | 1 | 1.548 | 1.244 | 0–8 | 0 / 0 / 2 / 3 | 1.161 |
| total_goals | ALL | 2.927 | 3 | 2.765 | 1.663 | 0–9 | 1 / 2 / 4 / 5 | 0.945 |
| total_goals | TRAIN | 2.983 | 3 | 2.905 | 1.704 | 0–9 | 1 / 2 / 4 / 5 | 0.974 |

**HECHOS.**
- En TRAIN, los goles local y visitante muestran **sobredispersión aparente**: var/media = 1.15 y 1.16.
- Los goles totales muestran una ligera **subdispersión aparente**: 0.97.
- Por temporada, el índice va de 0.90 a 1.23 en local y de 1.00 a 1.21 en visitante. En total cambia de signo: de 0.84 en 2023/24 a 1.12 en 2022/23.
- La covarianza implícita entre goles local y visitante es **negativa**: −0.267 en TRAIN (correlación −0.156) y −0.211 en ALL (−0.133). Se obtiene directamente de las tablas como (var_total − var_home − var_away) / 2.

**INTERPRETACIÓN.**
- Las desviaciones respecto de var = media son pequeñas.
- El total tiene menos varianza relativa que la suma de sus partes porque ambos conteos covarían negativamente en esta muestra.
- Esto **no** permite concluir que los goles sigan, ni que no sigan, una distribución Poisson. Tampoco se ajusta ningún modelo (D17).

### Ventaja local

| Grupo | Temporadas | % H [IC 95 %] | % A [IC 95 %] | H − A (pp) | Goles local | Goles visitante | GD medio |
|---|---|---|---|---|---|---|---|
| ALL | 5 | 44.2 [41.9, 46.4] | 31.9 [29.9, 34.1] | +12.2 | 1.597 | 1.330 | +0.268 |
| TRAIN | 2021/22–2023/24 | 45.8 [42.9, 48.7] | 31.7 [29.0, 34.4] | +14.1 | 1.649 | 1.334 | +0.315 |
| VAL | 2024/25 | 40.8 [36.0, 45.8] | 34.7 [30.1, 39.7] | +6.1 | 1.513 | 1.421 | +0.092 |
| TEST | 2025/26 | 42.6 [37.8, 47.7] | 30.0 [25.6, 34.8] | +12.6 | 1.526 | 1.224 | +0.303 |

- **HECHO.** En los cuatro grupos el local gana más partidos que el visitante y marca más goles de media.
- **INTERPRETACIÓN.** Existe una ventaja local descriptiva en estos datos.
- VAL y TEST se muestran solo como descripción separada. **No** se usan para decidir cómo modelar la localía, y E2 no crea features de home advantage.

### Variación por temporada

| Temporada | Partidos | H | D | A | %H | %D | %A | Goles local | Goles visit. | Goles total | GD medio | DE GD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021/22 (TRAIN) | 380 | 163 | 88 | 129 | 42.9 | 23.2 | 33.9 | 1.513 | 1.305 | 2.818 | 0.208 | 2.011 |
| 2022/23 (TRAIN) | 380 | 184 | 87 | 109 | 48.4 | 22.9 | 28.7 | 1.634 | 1.218 | 2.853 | 0.416 | 1.904 |
| 2023/24 (TRAIN) | 380 | 175 | 82 | 123 | 46.1 | 21.6 | 32.4 | 1.800 | 1.479 | 3.279 | 0.321 | 2.062 |
| 2024/25 (VAL) | 380 | 155 | 93 | 132 | 40.8 | 24.5 | 34.7 | 1.513 | 1.421 | 2.934 | 0.092 | 1.866 |
| 2025/26 (TEST) | 380 | 162 | 104 | 114 | 42.6 | 27.4 | 30.0 | 1.526 | 1.224 | 2.750 | 0.303 | 1.620 |

**HECHOS.**
- %H varía entre 40.8 y 48.4, %D entre 21.6 y 27.4 y %A entre 28.7 y 34.7.
- La media de goles totales varía entre 2.75 y 3.28 (máximo en 2023/24).
- La DE de GD varía entre 1.62 y 2.06.
- Dentro de TRAIN, los IC de Wilson de cada categoría se solapan entre temporadas.

Estas diferencias **no** se interpretan aquí como drift estructural. El análisis formal corresponde a E10, y para las decisiones solo podrá usar TRAIN o datos sin target, según la política de scopes.

### Hallazgos E2

**HECHOS.**
1. TRAIN: H 45.8 %, D 22.5 %, A 31.7 %. ALL: 44.2 %, 23.9 % y 31.9 %. Mismo orden H > A > D en ambos.
2. `goal_difference` es entera, con mediana 0, media +0.32 en TRAIN, DE 1.99, rango [−8, +9], el 80 % de los partidos con |GD| ≤ 2 y curtosis en exceso ≈ 0.8.
3. Los goles local y visitante tienen var/media ≈ 1.15 en TRAIN (sobredispersión aparente), el total ≈ 0.97, y la covarianza local–visitante es negativa (−0.27).
4. El local gana más y marca más en ALL, TRAIN, VAL y TEST.
5. Las proporciones y las medias de goles varían entre temporadas, con IC solapados dentro de TRAIN.

**INTERPRETACIÓN.**
- Las clases no son uniformes: el empate es la clase minoritaria.
- La distribución marginal de `goal_difference` es discreta y no normal por construcción. Es una descripción de la variable, no una evaluación de OLS.
- La dispersión de los conteos está cerca de la de una Poisson, pero no es idéntica.

### Implicaciones posteriores

Ninguna de estas implicaciones se decide en E2:
- La evaluación de clasificadores tendrá que tener en cuenta las frecuencias distintas de las clases, especialmente el empate. Se decidirá en el modelado, solo con TRAIN.
- `goal_difference` es una respuesta cuantitativa discreta: su naturaleza y sus colas deberán tenerse en cuenta al **interpretar** el modelo lineal. Esto no invalida automáticamente OLS ni exige que la variable respuesta sea normal. En la fase de Matemáticas (R) deberán evaluarse explícitamente, mediante los residuos, la especificación lineal y los supuestos relevantes: normalidad de los errores/residuos, homocedasticidad, patrones sistemáticos y observaciones influyentes. E2 no valida OLS; **P03 sigue abierta / provisional**.
- La localía existe descriptivamente. Si conviene representarla y cómo, se decidirá con TRAIN cuando corresponda.
- La variación entre temporadas se estudiará formalmente en E10.

### Decisiones

E2:
- **NO** selecciona modelo;
- **NO** selecciona métricas de evaluación definitivas;
- **NO** decide class weights;
- **NO** realiza resampling;
- **NO** modifica targets;
- **NO** utiliza VAL ni TEST para justificar decisiones.

P01, P02, P03, M1 y M3 siguen abiertas.

## E2m — Mercado

**Scope:** `ALL_DESCRIPTIVE` (5 temporadas). D42 permite caracterizar descriptivamente el mercado de 2025/26, pero ningún patrón de VAL o TEST justifica decisiones. No se generaron versiones `__TRAIN`: E2m no alimenta ninguna decisión, así que una copia restringida a TRAIN solo duplicaría información.

**Datos y método.**
- Columnas de CANONICAL: `match_id`, `season` y las seis cuotas `mkt_avg_*`. **No se usa `result`**, porque no hace falta ni para etiquetar filas.
- Las probabilidades se calculan en memoria con D39: `q_i = 1/o_i`, `p_i = q_i / Σq_j`. Solo se escriben resúmenes en `reports/eda/`; nada se añade a CANONICAL ni a FEATURES.
- Sin aleatoriedad.

**Outputs.**

| Archivo | Contenido |
|---|---|
| `tables/e02m_market_integrity__ALL.csv` | Cobertura, nulos, mín/máx, cuotas > 1 y comprobación Σp = 1 (tolerancia 1e-9) |
| `tables/e02m_overround_summary__ALL.csv` | Overround pre y close por temporada y total (también en %) |
| `tables/e02m_implied_probability_summary__ALL.csv` | Distribuciones de `q` crudas y `p` normalizadas, H/D/A × pre/close |
| `tables/e02m_market_favorite__ALL.csv` | Categoría favorita del mercado (sin acierto), empates exactos y cambios de favorito pre → close |
| `tables/e02m_pre_close_movement__ALL.csv` | Distribución de `Δp_H`, `Δp_D`, `Δp_A` y `market_move_L1` |
| `tables/e02m_market_by_season__ALL.csv` | Resumen por temporada |
| `figures/e02m_overround_by_season__ALL.png` | Mediana e IQR del overround pre y close por temporada |
| `figures/e02m_implied_probabilities__ALL.png` | Distribuciones de `p_pre_H`, `p_pre_D`, `p_pre_A` |

La figura opcional de movimiento no se generó: su distribución queda bien descrita por la tabla y una figura más no aportaría información interpretable.

### Papel del mercado en SCOPE

Estrategia C (contrato §10; D12, D13, D39): el modelo SCOPE usa **solo features deportivas** y el mercado es un **benchmark externo**.
- Las cuotas no forman parte de FEATURES, no son predictores y no se usan para seleccionar features.
- **Pre** (`AvgH/D/A`) es el benchmark principal y **close** (`AvgCH/CD/CA`) el secundario.
- No se supone que las cuotas de cierre tengan la misma información temporal que una predicción futura del modelo: la hora de captura no está documentada.

### Cuotas disponibles

Comprobación descriptiva del input (V08 ya lo validó en el pipeline):
- Las 6 columnas están completas: 1,900 filas, 380 por temporada, 0 nulos.
- Todas las cuotas son > 1.

| Columna | mín | máx |
|---|---|---|
| `mkt_avg_pre_home` / `_draw` / `_away` | 1.07 / 3.05 / 1.14 | 18.09 / 12.85 / 37.57 |
| `mkt_avg_close_home` / `_draw` / `_away` | 1.07 / 2.98 / 1.13 | 20.93 / 14.54 / 32.00 |

### Probabilidades implícitas

- Las probabilidades crudas `q = 1/o` suman más de 1 en todos los partidos.
- `Σq` va de 1.0344 a 1.0725 en pre y de 1.0269 a 1.0692 en close.
- Las medias crudas pre son H 0.461, D 0.247 y A 0.337. Están por encima de las normalizadas porque incluyen el overround.

### Overround

`overround = Σq − 1`. Es la suma de las probabilidades implícitas por encima del 100 % en las cuotas **agregadas** (medias de mercado). **No** es el margen ni el beneficio realizado de ninguna casa de apuestas.

| Ventana | media | mediana | DE | mín | máx | Q1 / Q3 / IQR |
|---|---|---|---|---|---|---|
| pre | 4.52 % | 4.25 % | 0.73 pp | 3.44 % | 7.25 % | 4.02 / 4.74 / 0.72 pp |
| close | 4.32 % | 4.04 % | 0.73 pp | 2.69 % | 6.92 % | 3.85 / 4.42 / 0.57 pp |

Overround medio por temporada (pre / close): 2021/22 4.07 / 3.87 · 2022/23 4.07 / 3.90 · 2023/24 4.14 / 3.97 · 2024/25 (VAL) 4.49 / 4.19 · 2025/26 (TEST) 5.81 / 5.67.

En todas las temporadas, el overround medio de close es menor que el de pre.

### Probabilidades normalizadas

`Σp = 1` en las 1,900 filas, tanto pre como close. La desviación máxima es 2.2e-16 y ninguna fila supera la tolerancia de 1e-9.

| p | media | mediana | DE | mín | Q05 / Q25 / Q75 / Q95 | máx |
|---|---|---|---|---|---|---|
| `p_pre_H` | 0.441 | 0.424 | 0.193 | 0.053 | 0.139 / 0.294 / 0.581 / 0.778 | 0.899 |
| `p_pre_D` | 0.237 | 0.248 | 0.047 | 0.075 | 0.139 / 0.211 / 0.271 / 0.294 | 0.314 |
| `p_pre_A` | 0.323 | 0.297 | 0.176 | 0.026 | 0.078 / 0.185 / 0.436 / 0.662 | 0.839 |
| `p_close_H` | 0.440 | 0.426 | 0.194 | 0.046 | 0.140 / 0.291 / 0.583 / 0.778 | 0.899 |
| `p_close_D` | 0.239 | 0.252 | 0.049 | 0.066 | 0.137 / 0.214 / 0.275 / 0.298 | 0.323 |
| `p_close_A` | 0.322 | 0.296 | 0.176 | 0.030 | 0.079 / 0.183 / 0.434 / 0.657 | 0.852 |

- **HECHO.** `p_H` y `p_A` se reparten en casi todo el rango [0, 0.9]. `p_D`, en cambio, está muy concentrada (DE ≈ 0.05; Q05–Q95 ≈ 0.14–0.29) y nunca supera 0.323.
- **INTERPRETACIÓN.** Las probabilidades implícitas de empate se concentran en un rango considerablemente más estrecho y presentan menor dispersión que las probabilidades de victoria local o visitante. E2m no evalúa si esa menor dispersión implica mayor o menor capacidad para discriminar partidos que terminarán en empate; eso requeriría relacionar las probabilidades con los resultados reales mediante métricas posteriores.
- Estas probabilidades **no** se comparan aquí con los resultados reales: eso sería calibración y corresponde a fases posteriores.

### Favorito del mercado

Favorito = categoría con mayor `p`. Los empates exactos en el máximo (cuotas idénticas) se reportan aparte y no se rompen.

| Ventana | H favorito | D favorito | A favorito | Empate exacto |
|---|---|---|---|---|
| pre | 1,192 (62.7 %) | 0 | 706 (37.2 %) | 2 (0.1 %) |
| close | 1,190 (62.6 %) | 0 | 709 (37.3 %) | 1 (0.05 %) |

- El empate **nunca** es el favorito del mercado, lo que es coherente con `p_D ≤ 0.323` (siempre por debajo de 1/3).
- Los empates exactos se dan entre H y A.
- El favorito cambia entre pre y close en **73 partidos (3.8 %)**, contando también los cambios hacia o desde un empate exacto.
- No se calcula cuántos favoritos acertaron.

### Pre vs close

`Δp_i = p_close_i − p_pre_i`; `market_move_L1 = |Δp_H| + |Δp_D| + |Δp_A|`.

| Variable | media | mediana | DE | Q05 / Q95 | máx \|·\| |
|---|---|---|---|---|---|
| `Δp_H` | −0.0012 | −0.0010 | 0.0252 | −0.042 / +0.041 | 0.164 |
| `Δp_D` | +0.0023 | +0.0024 | 0.0101 | −0.015 / +0.019 | 0.082 |
| `Δp_A` | −0.0011 | −0.0004 | 0.0230 | −0.041 / +0.035 | 0.112 |
| `market_move_L1` | 0.0446 | 0.0361 | 0.0336 | 0.0075 / 0.1055 | 0.329 |

- **HECHO.** El movimiento típico pre → close es pequeño: media de L1 = 0.045 y mediana = 0.036. El 95 % de los partidos tiene L1 < 0.11.
- **Lectura de L1.** Como pre y close suman 1, lo que gana un resultado lo pierden otros, y L1 cuenta esa masa dos veces. La masa de probabilidad efectivamente redistribuida es **L1 / 2**: ≈ 2.2 pp de media (0.045 / 2) y ≈ 1.8 pp de mediana (0.036 / 2).
- **HECHO.** En promedio, close asigna algo más de probabilidad al empate que pre (+0.0023).
- **INTERPRETACIÓN.** Pre y close describen consensos muy parecidos, con movimientos ocasionales grandes.
- El movimiento **no** se interpreta como información predictiva superior, y E2m **no** declara a close como benchmark "mejor" ni "más justo". Ninguna cuota será predictor en v0.1.

### Variación por temporada

| Temporada | Overround pre / close (%) | p_pre H / D / A (media) | L1 medio |
|---|---|---|---|
| 2021/22 (TRAIN) | 4.07 / 3.87 | 0.433 / 0.242 / 0.325 | 0.043 |
| 2022/23 (TRAIN) | 4.07 / 3.90 | 0.438 / 0.241 / 0.321 | 0.043 |
| 2023/24 (TRAIN) | 4.14 / 3.97 | 0.448 / 0.224 / 0.328 | 0.044 |
| 2024/25 (VAL) | 4.49 / 4.19 | 0.448 / 0.230 / 0.322 | 0.047 |
| 2025/26 (TEST) | 5.81 / 5.67 | 0.437 / 0.245 / 0.318 | 0.046 |

- **HECHO.** El overround medio es estable en 2021/22–2023/24 (≈ 4.1 % pre) y más alto en 2024/25 y, sobre todo, en 2025/26. Las probabilidades normalizadas medias y el movimiento medio varían poco.
- **HIPÓTESIS (no verificada en E2m).** El Quality Register §3 documenta que el conjunto de casas de apuestas presentes en los archivos fuente cambia en 2024/25 y 2025/26. Un cambio en la composición del agregado `Avg` podría contribuir al cambio de overround, pero E2m no lo comprueba.
- Las diferencias de 2025/26 no motivan ningún cambio de modelado. El drift formal corresponde a E10.

### Hallazgos E2m

**HECHOS.**
1. El bloque de mercado está completo (6 cuotas × 1,900 partidos, todas > 1) y la normalización D39 cumple Σp = 1 (desviación máxima 2.2e-16).
2. Overround medio: 4.52 % pre y 4.32 % close. Close es menor que pre en todas las temporadas. Es estable en 2021/22–2023/24 (≈ 4.1 %) y más alto en 2024/25 (4.5 %) y 2025/26 (5.8 %).
3. Probabilidades pre medias: H 0.441, D 0.237, A 0.323. `p_D` está muy concentrada y nunca supera 0.323.
4. Favorito pre: H 62.7 %, A 37.2 %, D 0 %, 2 empates exactos. El favorito cambia de pre a close en el 3.8 % de los partidos.
5. Movimiento pre → close pequeño: mediana de L1 0.036, Q95 0.106, máximo 0.329.

**INTERPRETACIÓN.**
- Las probabilidades implícitas de empate se concentran en un rango considerablemente más estrecho y presentan menor dispersión que las probabilidades de victoria local o visitante. E2m no evalúa si esa menor dispersión implica mayor o menor capacidad para discriminar partidos que terminarán en empate; eso requeriría relacionar las probabilidades con los resultados reales mediante métricas posteriores.
- Pre y close son consensos muy cercanos.
- El nivel de overround depende de la temporada. La normalización proporcional de D39 elimina el overround agregado de cada terna, haciendo que `p_H + p_D + p_A = 1`. Esto no demuestra que el margen contenido en las cuotas originales estuviera distribuido homogéneamente entre los tres resultados. D39 sigue siendo el procedimiento oficial de v0.1.

### Implicaciones posteriores

Ninguna de estas implicaciones se decide en E2m:
- La futura comparación SCOPE vs mercado tendrá que hacerse sobre **exactamente el mismo conjunto de partidos elegibles** (contrato §10) y con las mismas convenciones de métrica, que se definirán en ML.
- Como el mercado nunca hace favorito al empate, la comparación de desempeño en la clase D merecerá atención explícita en esa fase. No se evalúa aquí.
- El cambio de overround entre temporadas afecta al nivel de `q`, no a `Σp`. Cualquier análisis futuro que dependa de `q` crudas deberá tenerlo en cuenta.

### Decisiones

- El mercado **sigue siendo benchmark externo**.
- Las cuotas **no son predictors** y no se usaron para seleccionar features.
- **Pre** sigue siendo el benchmark principal y **close** el secundario.
- **No** se ha evaluado accuracy.
- **No** se ha evaluado log loss.
- **No** se ha evaluado Brier.
- **No** se ha estudiado calibración.
- **No** se ha realizado comparación SCOPE vs mercado.
- P01, P02, P03, M1 y M3 siguen abiertas.

## E3 — Features univariadas

### Scope

**`DEV_PREDICTORS` (`__DEVX`), 2021/22–2024/25**, en modo *predictor-only*:
- El cargador no entrega `result`, `goal_difference`, POST ni MARKET, y `e03_univariate.py` vuelve a comprobarlo antes de analizar.
- Del CANONICAL solo se añaden `home_team_id` y `away_team_id`, que es información pre-partido, para dar trazabilidad a los extremos.
- 2025/26 no participa. Sin aleatoriedad.

**Población principal:** filas con `is_modeling_eligible = true`, es decir 1,399 partidos (350 / 350 / 349 / 350), sin missingness.

**Análisis secundarios, etiquetados aparte:** estratificación por historial en los tramos 3–5, 6–10, 11–20 y 21–37.
- `h_*` se estratifica por `h_n_prev_season`, `a_*` por `a_n_prev_season` y `diff_*` por el mínimo de ambos.
- Cada lado tiene 120 / 200 / 399 / 680 filas por tramo.

**Outputs.**

| Archivo | Contenido |
|---|---|
| `tables/e03_univariate_summary__DEVX.csv` | Una fila por feature (2 de control + 21 de tasa): n, media, mediana, DE, varianza, mín, máx, Q1, Q3, IQR, P5, P95, asimetría, curtosis en exceso, valores únicos y conteos de Tukey |
| `tables/e03_univariate_by_season__DEVX.csv` | Feature × temporada: n, media, mediana, DE, Q1, Q3, mín, máx |
| `tables/e03_univariate_by_history__DEVX.csv` | Feature × tramo de historial: posición, dispersión, cuantiles y extremos según las vallas globales |
| `tables/e03_extreme_values__DEVX.csv` | Cada observación fuera de las vallas de Tukey, con partido, equipos, `n_prev` y comprobación del dominio |
| `tables/e03_granularity__DEVX.csv` | Valores únicos, saltos entre valores y concentración, season vs last5 |
| `tables/e03_home_away_comparison__DEVX.csv` | `h_x` vs `a_x` por estadístico |
| `figures/e03_diff_feature_distributions__DEVX.png` | Distribuciones de las 7 `diff_*` |
| `figures/e03_season_vs_last5_univariate__DEVX.png` | Granularidad season vs last5 (ppg, gf_pg, ga_pg) |
| `figures/e03_feature_dispersion_by_history__DEVX.png` | Dispersión relativa por tramo de historial (selección representativa) |

La tabla de local vs visitante (§E3.4) se añadió porque su estructura, métrica × estadístico × lado, no cabe en el resumen por feature.

### Resumen de features

Control: `h_n_prev_season` y `a_n_prev_season` van de 3 a 37, con mediana 20, y su distribución es casi uniforme (curtosis en exceso −1.2). Se interpretan como **madurez del historial**, no como predictores decididos.

| Feature (lado h) | media | mediana | DE | mín–máx | P5 / P95 | asim. | curt. exc. | únicos |
|---|---|---|---|---|---|---|---|---|
| `h_ppg_season` | 1.374 | 1.333 | 0.568 | 0–3 | 0.50 / 2.38 | 0.21 | −0.38 | 535 |
| `h_gf_pg_season` | 1.461 | 1.400 | 0.549 | 0–3.63 | 0.71 / 2.45 | 0.53 | −0.03 | 533 |
| `h_ga_pg_season` | 1.463 | 1.429 | 0.466 | 0–4.00 | 0.75 / 2.25 | 0.41 | 0.99 | 491 |
| `h_ppg_last5` | 1.367 | 1.400 | 0.717 | 0–3 | 0.20 / 2.60 | 0.23 | −0.59 | 28 |
| `h_gf_pg_last5` | 1.471 | 1.400 | 0.705 | 0–4.80 | 0.40 / 2.80 | 0.73 | 0.65 | 39 |
| `h_ga_pg_last5` | 1.489 | 1.400 | 0.654 | 0–4.00 | 0.40 / 2.60 | 0.47 | 0.13 | 35 |
| `h_sot_pg_last5` | 4.512 | 4.400 | 1.389 | 1.2–10.4 | 2.49 / 7.00 | 0.57 | 0.38 | 68 |

Los valores del lado `a` son casi idénticos (ver Local vs visitante). Las 21 filas están en `e03_univariate_summary__DEVX.csv`.

### Distribuciones

**HECHOS.**
- Las tasas de equipo son unimodales y con asimetría positiva moderada: entre 0.12 y 0.73.
- `ppg` está acotada por construcción en [0, 3] y tiene colas ligeras (curtosis en exceso negativa).
- `ga_pg_season` es la feature de temporada con colas más pesadas (curtosis en exceso ≈ 1.0 en ambos lados).
- Las tasas de goles last5 (`gf_pg_last5`, y menos `ga_pg_last5`) tienen la asimetría positiva más marcada: unas pocas rachas muy goleadoras.

**INTERPRETACIÓN.** Ninguna distribución es degenerada ni multimodal. No se usaron tests de normalidad: con n = 1,399 detectarían desviaciones pequeñas sin relevancia práctica. Lo que se describe es la forma.

### Valores extremos

**Regla.** Tukey, valores fuera de [Q1 − 1.5·IQR, Q3 + 1.5·IQR] calculado sobre la población principal, con dos definiciones separadas:
- **Valor extremo** = observación poco frecuente.
- **Error** = violación del dominio del contrato §5.4 (`ppg` ∈ [0, 3] y el resto de tasas ≥ 0).

**HECHOS.**
- **311 pares feature × partido** quedan fuera de las vallas, **todos dentro del dominio: 0 errores**.
- Las features con más extremos son `a_ga_pg_season` (45; 3.2 %) y `h_ga_pg_season` (38; 2.7 %), en ambas colas, y `h_gf_pg_last5` (32). Las tasas `ppg_last5` y los controles no tienen ninguno.
- **Proporción de extremos por tramo de historial:** 3.75 % en 3–5, 1.52 % en 6–10, 0.57 % en 11–20 y 0.74 % en 21–37. En 21–37 dominan las features last5, por rachas cortas.
- Todos los valores `ppg_season = 0` (16 casos) y `ppg_season = 3` (11 casos) aparecen con `n_prev` entre 3 y 6. Son legítimos: unos pocos partidos producen tasas extremas.
- **Máximos absolutos:**
  - `h_sot_pg_last5` = 10.4 y `a_sot_pg_last5` = 10.8 (ambos con `n_prev` 16–19);
  - `h_gf_pg_last5` = 4.8 (con `n_prev = 27`) y `h_ga_pg_season` = 4.0 (con `n_prev = 4`).

**NO DECISIÓN.** No se eliminó, winsorizó, truncó ni transformó ningún valor.

### Dependencia con historial disponible

Este bloque es descriptivo y **no** aborda P01, que se reserva para E7.

| Feature | DE 3–5 | DE 6–10 | DE 11–20 | DE 21–37 |
|---|---|---|---|---|
| `h_ppg_season` | 0.848 | 0.651 | 0.528 | 0.500 |
| `h_gf_pg_season` | 0.762 | 0.643 | 0.537 | 0.480 |
| `h_ga_pg_season` | 0.730 | 0.555 | 0.423 | 0.398 |
| `diff_ppg_season` | 1.124 | 0.894 | 0.759 | 0.720 |
| `h_ppg_last5` | 0.848 | 0.665 | 0.682 | 0.728 |
| `h_gf_pg_last5` | 0.762 | 0.688 | 0.677 | 0.717 |
| `h_sot_pg_last5` | 1.501 | 1.320 | 1.361 | 1.408 |

**HECHOS.**
- La dispersión de las features **season** baja de forma monótona con el historial. Con 3–5 partidos es entre 1.6 y 1.8 veces la del tramo 21–37 (`h_ppg_season` 1.70; `diff_ppg_season` 1.56).
- La de las features **last5** baja de 3–5 a 6–10 y después se mantiene casi constante (0.91–1.0 respecto a 21–37).
- En el tramo 3–5, cada feature last5 tiene **exactamente** la misma DE que su versión season (0.848, 0.762, 0.730). Es consecuencia de la construcción, `last5 = season` mientras `n_prev ≤ 5` (M3), y no un hallazgo.

**INTERPRETACIÓN.**
- Con poco historial, las tasas de temporada son más variables entre equipos, lo que es coherente con promediar pocos partidos.
- La ventana last5, al tener tamaño fijo a partir de 5 partidos, mantiene una dispersión aproximadamente estable.

**NO DECISIÓN.** No se elige ningún burn-in.

### Local vs visitante

Recordatorio: `h_*` y `a_*` son el rendimiento **global** previo del equipo que ocupa el rol local o visitante en ese partido, no su rendimiento en casa o fuera.

**HECHOS.**
- En `ppg`, `gf_pg` y `ga_pg`, las medias de `h` y `a` difieren como mucho en 0.034 (≤ 0.006 en las de temporada), las medianas como mucho en 0.024 y las DE como mucho en 0.009.
- `sot_pg_last5` es la mayor diferencia: 4.51 frente a 4.61 (−0.10), con mediana igual (4.4).
- La forma (asimetría y curtosis) es similar en ambos lados.

**INTERPRETACIÓN.** Las distribuciones marginales de las features `h_` y `a_` son muy similares en DEVX: presentan medias, medianas y dispersiones muy próximas. Esto es coherente con que ambas describan el rendimiento global previo de equipos que ocupan distintos roles en cada partido; no implica que las columnas sean intercambiables en un modelo.

**NO DECISIÓN.** Estas diferencias pequeñas **no** se interpretan como ventaja local, y no se hicieron tests formales.

### Features diff

| Feature | media | mediana | DE | mín–máx | P5 / P95 | asim. | curt. exc. | únicos |
|---|---|---|---|---|---|---|---|---|
| `diff_ppg_season` | −0.006 | 0 | 0.799 | −2.33 / 2.38 | −1.27 / 1.32 | 0.05 | −0.12 | 996 |
| `diff_gf_pg_season` | −0.001 | 0 | 0.773 | −3.00 / 2.75 | −1.25 / 1.33 | 0.03 | 0.10 | 987 |
| `diff_ga_pg_season` | 0.003 | 0 | 0.637 | −2.17 / 3.00 | −1.00 / 1.00 | 0.07 | 0.60 | 957 |
| `diff_ppg_last5` | −0.034 | 0 | 1.008 | −2.60 / 2.80 | −1.67 / 1.60 | 0.10 | −0.35 | 80 |
| `diff_gf_pg_last5` | −0.018 | 0 | 0.970 | −3.20 / 3.40 | −1.60 / 1.60 | 0.02 | 0.53 | 97 |
| `diff_ga_pg_last5` | 0.021 | 0 | 0.892 | −2.80 / 3.00 | −1.40 / 1.40 | −0.05 | 0.23 | 89 |
| `diff_sot_pg_last5` | −0.101 | 0 | 1.948 | −7.80 / 6.20 | −3.40 / 3.00 | −0.10 | 0.38 | 174 |

**HECHOS.** Las siete `diff_*` están centradas en 0 (mediana 0, media |·| ≤ 0.10) y son aproximadamente simétricas (|asimetría| ≤ 0.10). Las de last5 tienen más dispersión que sus homólogas de temporada.

**Lectura del signo.** `diff_x > 0` significa que el valor del local es **mayor**, pero "mayor" no siempre es "mejor":
- en `diff_ga_*`, un valor positivo significa que el local **recibe más goles** por partido que el visitante;
- en `diff_ppg_*`, `diff_gf_*` y `diff_sot_*`, un valor positivo indica más puntos, goles o tiros a puerta del local.

Ningún valor positivo se describe automáticamente como "ventaja local".

### Granularidad last5

| Métrica | únicos season (h / a / diff) | únicos last5 (h / a / diff) | % filas en los 5 valores más frecuentes, season → last5 (h) |
|---|---|---|---|
| `ppg` | 535 / 523 / 996 | 28 / 27 / 80 | 11.7 % → 48.9 % |
| `gf_pg` | 533 / 552 / 987 | 39 / 39 / 97 | 13.9 % → 53.0 % |
| `ga_pg` | 491 / 477 / 957 | 35 / 37 / 89 | 13.5 % → 53.8 % |

- **HECHO.** Las features last5 tienen entre 13 y 19 veces menos valores distintos que sus versiones season. Sus valores están en una rejilla de fracciones `k/m` con `m ∈ {3, 4, 5}` (el salto mínimo entre valores es 0.05), y la mitad de las filas cae en sus 5 valores más frecuentes.
- `sot_pg_last5` no tiene versión season y queda fuera de la comparación: tiene 68 / 67 / 174 valores únicos.
- En la figura, los valores `h_` y `a_` se agrupan, por eso los conteos son algo mayores (p. ej. 42 en `gf_pg_last5`).
- **INTERPRETACIÓN.** La ventana fija produce variables mucho más discretas.
- **IMPLICACIÓN FUTURA.** Habrá muchos valores repetidos, y por tanto empates en distancias (KNN) y en cortes (árboles). Además, la posible redundancia season–last5 se evaluará en E6 (M3).
- **NO DECISIÓN.** No se elimina ninguna de las dos familias.

### Variación por temporada

Solo DEVX y solo descripción; el drift formal corresponde a E10.

**HECHOS.**
- Las medias de `ppg` son estables (1.35–1.41).
- Las medias de `gf_pg`, `ga_pg` y `sot_pg_last5` son más altas en 2023/24, en ambos lados a la vez (p. ej. `h_gf_pg_season` 1.575 frente a 1.37–1.47; `h_sot_pg_last5` 4.86 frente a 4.33–4.51).
- Las medias de las `diff_*` son ≈ 0 en todas las temporadas.
- Las DE varían poco. La mayor diferencia es `gf_pg_season` en 2024/25 (DE 0.456 frente a 0.54–0.62).

**INTERPRETACIÓN.** Ninguna distribución parece anómala ni inestable. Los cambios de nivel de 2023/24 afectan a la vez a local y visitante, así que se compensan en las `diff_*`.

### Hallazgos E3

**HECHOS.**
1. Las 21 features de tasa no tienen ningún error de dominio. Hay 311 observaciones descriptivamente extremas, concentradas con poco historial (3.75 % en 3–5 frente a < 1 % con ≥ 11).
2. La dispersión de las features season baja monótonamente con el historial (1.6–1.8 veces mayor en 3–5 que en 21–37). La de last5 se estabiliza desde 6–10.
3. Las distribuciones marginales de `h_*` y `a_*` son muy similares (lo que no las hace intercambiables como columnas de un modelo).
4. Las siete `diff_*` están centradas en 0 y son aproximadamente simétricas.
5. Las features last5 son muy discretas: 27–39 valores únicos frente a 477–552 en season.
6. Las medias de goles y tiros a puerta son más altas en 2023/24, con las `diff_*` estables.

**INTERPRETACIÓN.** Las features son estadísticamente regulares. Las propiedades que más condicionarán fases posteriores son la mayor variabilidad con poco historial y la discreción de last5.

### Implicaciones posteriores

Ninguna se decide en E3:
- E7 (P01) deberá considerar que la variabilidad de las features season depende fuertemente del historial.
- E6 (M3) deberá evaluar la redundancia season–last5, teniendo en cuenta que son idénticas en el tramo 3–5 por construcción.
- E5 (M1) deberá documentar la dependencia `diff = h − a`. E3 confirma que las tres representaciones tienen escalas distintas (las DE de `diff` son ≈ 1.4 veces las de `h`/`a`).
- El modelado deberá considerar la discreción de last5: muchos valores repetidos, empates en distancias y menos puntos de corte posibles.
- Las diferencias de escala entre features (p. ej. SOT ≈ 4.5 frente a ppg ≈ 1.4) serán especialmente relevantes para métodos basados en distancia como KNN y pueden ser importantes para modelos lineales o regularizados. Los modelos basados en árboles son, en general, mucho menos sensibles al escalado, porque sus divisiones se realizan mediante umbrales sobre cada variable. E3 no decide ningún método de escalado; cualquier escalado futuro se ajustará exclusivamente con train (T8).
- Las diferencias entre temporadas se estudiarán formalmente en E10.

### Decisiones

- **Ninguna** feature eliminada.
- **Ninguna** transformación aplicada.
- **Ninguna** winsorización.
- **Ningún** escalado.
- **P01** abierta.
- **P02** abierta.
- **M1** abierta.
- **M3** abierta.
- E3 no usó `result` ni `goal_difference` y no calculó correlaciones entre features.

## E4 — Relaciones entre variables

### Scope y separación DEVX / TRAIN

| Bloque | Scope | Temporadas | Población | Targets |
|---|---|---|---|---|
| **E4A** predictor ↔ predictor | `DEV_PREDICTORS` (`__DEVX`) | 2021/22–2024/25 | 1,399 filas elegibles (verificado) | **no** (el cargador los excluye) |
| **E4B** predictor ↔ target | `TRAIN_TARGET` (`__TRAIN`) | 2021/22–2023/24 | 1,049 filas elegibles (verificado) | `result`, `goal_difference` |

- VAL (2024/25) y TEST (2025/26) **no** participan en ningún análisis con target. No se imputa nada.
- **Spearman** se calcula como Pearson sobre rangos medios, que es su definición. Coincide con la matriz de pandas con una diferencia de 2.4e-15 y evita depender de scipy.
- **Fuera de E4:** no hay VIF, condition number, rango ni regresiones auxiliares (E5/M1), ni correlaciones season–last5 condicionadas al historial (E6/M3).
- **Sin tests inferenciales.** Los partidos no son independientes (equipos repetidos, estructura equipo-temporada, dependencia temporal), así que se priorizan los tamaños de efecto descriptivos.

**Outputs.**

| Archivo | Contenido |
|---|---|
| `tables/e04_pearson_predictors__DEVX.csv` | Matriz 21 × 21 de Pearson (columna `feature` + una columna por feature, en el orden de bloques de la figura) |
| `tables/e04_spearman_predictors__DEVX.csv` | Matriz 21 × 21 de Spearman (mismo formato) |
| `tables/e04_pairwise_relationships__DEVX.csv` | 54 pares por familia (`h_a_diff_definicional`, `season_vs_last5`, `conceptual`) con Pearson, Spearman y su diferencia |
| `tables/e04_goal_difference_relationships__TRAIN.csv` | Pearson y Spearman de cada feature con `goal_difference`, n = 1,049; `order_by_abs_pearson` solo ordena para leer |
| `tables/e04_features_by_result__TRAIN.csv` | Feature × clase H/D/A: n, media, mediana, DE, Q1, Q3 y media del valor absoluto |
| `tables/e04_result_separation__TRAIN.csv` | Diferencia de medias estandarizada (DE combinada) entre pares de clases, como medida descriptiva |
| `figures/e04_feature_correlation_heatmap__DEVX.png` | Heatmap de Pearson agrupado: season \| last5 × h / a / diff |
| `figures/e04_diff_features_by_result__TRAIN.png` | Boxplots de las 7 `diff_*` por H/D/A |

**Figuras omitidas.**
- El heatmap de Spearman no se generó. El criterio, fijado en el código antes de ver los resultados, era generarlo solo si alguna celda difería de Pearson en ≥ 0.05. La diferencia máxima es 0.031 y la media 0.011, así que Spearman queda solo en tablas.
- La figura opcional de relación con GD tampoco se generó: la tabla ordenada resume las 21 relaciones sin necesidad de scatterplots.
- La tabla de separación es adicional a las mínimas: es la medida de separación entre grupos que §E4B permite, documentada aparte.

### Predictor ↔ predictor

**Estructura algebraica (no estadística).** `diff_x = h_x − a_x` por definición: `h_x`, `a_x` y `diff_x` **no son tres variables independientes**.

**HECHOS (DEVX).**
- `h_x` y `a_x` de la misma métrica están prácticamente incorrelacionadas: |r| entre 0.012 y 0.081.
- `corr(h_x, diff_x)` va de +0.67 a +0.70 y `corr(a_x, diff_x)` de −0.68 a −0.70.

**INTERPRETACIÓN.** Si `h` y `a` están casi incorrelacionadas y tienen varianzas parecidas (E3), la correlación de cada una con su diferencia es, algebraicamente, ≈ ±1/√2 ≈ ±0.71. Esos ±0.7 son por tanto **en gran parte consecuencia de la construcción** y no una relación empírica independiente.

La dependencia lineal exacta y sus consecuencias para los modelos son el objeto de E5. **M1 sigue abierta.**

### Pearson vs Spearman

- **HECHO.** En los 210 pares, |Pearson − Spearman| ≤ 0.031 (media 0.011).
- **INTERPRETACIÓN.** Las asociaciones entre features son esencialmente lineales y monótonas. Los extremos de E3 y la discreción de last5 no cambian la imagen.

### Relaciones por familia

Pearson (Spearman entre paréntesis cuando difiere en más de 0.02) para el lado `h`. `a` y `diff` son casi iguales; ver la tabla de pares.

| Relación | season | last5 |
|---|---|---|
| PPG ↔ GF/PG | +0.82 | +0.74 |
| PPG ↔ GA/PG | −0.78 | −0.70 |
| GF/PG ↔ GA/PG | −0.50 (−0.47) | −0.30 |
| SOT ↔ GF/PG (solo last5) | — | +0.71 |
| SOT ↔ PPG (solo last5) | — | +0.60 |

**HECHOS.**
- PPG está fuertemente asociado de forma positiva con los goles a favor y negativa con los goles en contra, en ambas ventanas, en ambos lados y también en las `diff_*` (+0.82 / −0.78 en season).
- GF/PG y GA/PG tienen una asociación negativa moderada: −0.50 en season y −0.30 en last5.
- Los tiros a puerta (last5) se asocian con los goles a favor (+0.71) y, en menor medida, con PPG (+0.60).
- La asociación es menor en last5 que en season en todos los pares conceptuales.

**INTERPRETACIÓN.** Las métricas de rendimiento de un mismo equipo comparten mucha información. La relación PPG ↔ goles es en parte mecánica, porque los puntos se derivan de los goles, pero E4 solo la cuantifica y no asume causalidad. Una correlación alta no demuestra duplicación ni implica eliminar nada.

### Season vs last5

| Par | h | a | diff |
|---|---|---|---|
| `ppg_season` ↔ `ppg_last5` | 0.78 | 0.78 | 0.77 |
| `gf_pg_season` ↔ `gf_pg_last5` | 0.77 | 0.77 | 0.75 |
| `ga_pg_season` ↔ `ga_pg_last5` | 0.74 | 0.73 | 0.73 |

- **HECHO.** Cada métrica está correlacionada con su versión de la otra ventana (0.73–0.78).
- **LIMITACIÓN.** Estas correlaciones son **globales** y están parcialmente infladas: en las filas con `n_prev ≤ 5` ambas ventanas son idénticas por construcción. Eso afecta a 118 filas elegibles en el lado `h` (8.4 %), 120 en el `a` (8.6 %) y 120 en `diff` (mínimo de ambos).
- **NO DECISIÓN.** No se concluye que sean redundantes ni que deba conservarse o eliminarse ninguna familia. El análisis condicionado al historial, las diferencias, el MAE y la redundancia corresponden a E6. **M3 sigue abierta.**

### Relación con goal_difference

Solo TRAIN elegible (n = 1,049). El orden por |r| es **solo** para facilitar la lectura; no indica importancia, poder predictivo ni selección. Una correlación univariada no equivale al rendimiento de una variable dentro de un modelo multivariable.

| # | Feature | Pearson | Spearman |
|---|---|---|---|
| 1 | `diff_ppg_season` | +0.412 | +0.405 |
| 2 | `diff_gf_pg_season` | +0.394 | +0.382 |
| 3 | `diff_ga_pg_season` | −0.361 | −0.355 |
| 4 | `diff_sot_pg_last5` | +0.330 | +0.327 |
| 5 | `h_ppg_season` | +0.324 | +0.324 |
| 6 | `diff_ppg_last5` | +0.321 | +0.319 |
| 7 | `diff_gf_pg_last5` | +0.314 | +0.282 |
| … | … | … | … |
| 21 | `a_ga_pg_last5` | +0.171 | +0.176 |

**HECHOS.**
- Todas las correlaciones son de magnitud baja a moderada (|r| 0.17–0.41).
- Los signos son los conceptualmente esperables:
  - las métricas de rendimiento ofensivo y de puntos del local (`h_ppg`, `h_gf`, `h_sot`) y sus `diff_*` se asocian positivamente con GD;
  - `diff_ga_*` y `h_ga_*` se asocian negativamente con GD. `diff_ga > 0` significa que el local recibe más goles;
  - las métricas del visitante tienen el signo inverso (`a_ppg` −, `a_ga` +).
- Para cada métrica:
  - la versión `diff_` tiene mayor |r| que `h_` y que `a_` por separado;
  - `h_` tiene un |r| mayor o igual que `a_` (empate en `ga_pg_season`, 0.245);
  - la versión season tiene mayor |r| que la last5 (p. ej. `diff_ppg` 0.412 frente a 0.321).

No se corrigió ningún signo ni se redefinió ninguna feature.

### Distribuciones por result

Solo TRAIN elegible: H n = 482, D n = 235, A n = 332. `result` se trata como nominal, sin codificación numérica.

| Feature | media H | media D | media A | mediana H / D / A | d(H, A) | d(H, D) | d(D, A) |
|---|---|---|---|---|---|---|---|
| `diff_ppg_season` | +0.290 | −0.054 | −0.401 | +0.27 / −0.03 / −0.46 | 0.94 | 0.46 | 0.48 |
| `diff_gf_pg_season` | +0.274 | −0.035 | −0.383 | +0.23 / 0.00 / −0.38 | 0.88 | 0.40 | 0.46 |
| `diff_ga_pg_season` | −0.200 | +0.049 | +0.271 | −0.18 / +0.09 / +0.34 | −0.79 | −0.41 | −0.36 |
| `diff_ppg_last5` | +0.275 | −0.128 | −0.406 | +0.20 / 0.00 / −0.50 | 0.70 | 0.42 | 0.29 |
| `diff_gf_pg_last5` | +0.260 | −0.095 | −0.365 | +0.20 / −0.20 / −0.20 | 0.66 | 0.37 | 0.28 |
| `diff_ga_pg_last5` | −0.208 | +0.100 | +0.314 | −0.20 / 0.00 / +0.20 | −0.61 | −0.35 | −0.25 |
| `diff_sot_pg_last5` | +0.556 | −0.403 | −0.826 | +0.60 / −0.20 / −0.80 | 0.72 | 0.50 | 0.23 |

`d` = diferencia de medias estandarizada con DE combinada, como medida descriptiva. Ver `e04_result_separation__TRAIN.csv`.

**HECHOS, respecto a las preguntas descriptivas:**
- **Victorias locales:** sí, tienen `diff_ppg` (y `diff_gf`, `diff_sot`) desplazado hacia valores positivos, y `diff_ga` hacia negativos.
- **Victorias visitantes:** sí, tienen el desplazamiento opuesto.
- **Empates:** en varias `diff_*`, su centro queda **entre** H y A, cerca de 0, pero **no están más concentrados** alrededor de 0. Por ejemplo, en `diff_ppg_season` su DE es similar (D 0.749, H 0.755, A 0.715) y su media de |diff| apenas es menor (0.605 frente a 0.638 y 0.682).
- La separación H–A es la mayor (d ≈ 0.6–0.9). Las separaciones de D respecto de H o de A son menores (d ≈ 0.2–0.5).
- Las distribuciones de las tres clases **se solapan ampliamente**: los rangos intercuartílicos se superponen en las siete `diff_*`.
- Por la discreción de last5, algunas medianas coinciden entre clases (p. ej. `diff_gf_pg_last5`, D y A en −0.20) aunque sus medias difieran.

**INTERPRETACIÓN (TRAIN).** Las distribuciones de las `diff_*` muestran desplazamientos coherentes con la semántica de cada métrica entre H, D y A, aunque con un solapamiento considerable. Para métricas donde un valor mayor representa mejor rendimiento del local, como PPG o GF/PG, H tiende hacia valores más positivos y A hacia valores más negativos. En `diff_ga_*` la dirección se invierte, porque valores positivos significan que el local recibe más goles. En varias `diff_*`, la distribución de los empates se sitúa descriptivamente entre las de H y A y cerca de cero, pero presenta un fuerte solapamiento con ambas. E4 no determina si los empates poseen o no una estructura multivariable diferenciable. **No se afirma que ninguna feature "prediga" H/D/A.**

### Hallazgos E4

**HECHOS.**
1. **DEVX:** `h_x` y `a_x` están casi incorrelacionadas (|r| ≤ 0.08). Su correlación de ≈ ±0.7 con `diff_x` es mayoritariamente algebraica (≈ ±1/√2).
2. **DEVX:** PPG se asocia con GF/PG (+0.82 season, +0.74 last5) y con GA/PG (−0.78 / −0.70). GF/PG ↔ GA/PG −0.50 / −0.30. SOT ↔ GF last5 +0.71.
3. **DEVX:** las versiones season y last5 están correlacionadas (0.73–0.78), con inflación parcial por las filas con `n_prev ≤ 5` (≈ 8.5 %).
4. **DEVX:** Pearson y Spearman son casi idénticos (|Δ| ≤ 0.031).
5. **TRAIN:** las asociaciones con `goal_difference` son de magnitud baja a moderada (|r| 0.17–0.41), con los signos esperables. Por métrica, `diff_` > `h_` ≥ `a_` en |r|, y season > last5.
6. **TRAIN:** las `diff_*` muestran desplazamientos entre H, D y A coherentes con la semántica de cada métrica (H más positivo en PPG, GF y SOT; dirección invertida en `diff_ga_*`), con un solapamiento considerable. En varias `diff_*` los empates se sitúan entre H y A y cerca de cero, sin estar más concentrados.

### Implicaciones posteriores

Ninguna se decide en E4:
- E5 (M1) deberá estudiar formalmente la dependencia lineal exacta h / a / diff y sus implicaciones para cada familia de modelos.
- E6 (M3) deberá separar la correlación season–last5 del efecto de identidad con `n_prev ≤ 5`.
- La fuerte asociación entre PPG, GF y GA dentro de un mismo equipo deberá tenerse en cuenta al interpretar coeficientes de modelos lineales. No se cuantifica aquí con VIF.
- La fuerte superposición observada en los análisis univariados sugiere una separación limitada de la clase D mediante features individuales. La dificultad real de clasificar empates deberá evaluarse posteriormente mediante modelos multivariables y métricas de evaluación. E4 no determina si los empates poseen o no una estructura multivariable diferenciable.
- Las correlaciones univariadas con GD no ordenan la utilidad de las features en un modelo multivariable.

### Decisiones

- **Ninguna** feature eliminada.
- **Ninguna** feature seleccionada.
- **Ninguna** transformación aplicada.
- **M1** abierta.
- **M3** abierta.
- **P01** abierta.
- **P02** abierta.
- Los targets solo se usaron en TRAIN (2021/22–2023/24). VAL y TEST no participaron en ningún análisis con target.
- No se calcularon VIF, condition number, rango ni regresiones auxiliares.

## E5 — M1: dependencia lineal h/a/diff

**Scope:** `DEV_PREDICTORS` (`__DEVX`), 2021/22–2024/25, con 1,399 filas elegibles (verificado).
- Es completamente *predictor-only*: no usa `result`, `goal_difference`, POST ni MARKET. No compara desempeño predictivo ni entrena modelos.
- Se implementa solo con NumPy: SVD (`numpy.linalg.svd`) para rango y valores singulares, y `numpy.linalg.lstsq` para el R² auxiliar.
- Sin aleatoriedad.

**Criterio de rango, documentado y no ajustado:** es el de `numpy.linalg.matrix_rank`, `tol = σ_max · max(n_filas, n_columnas) · ε_float64` (ε = 2.2e-16). El rango es el número de valores singulares mayores que `tol`. El código comprueba además que coincide con `matrix_rank`.

**Estandarización:** `z = (x − media_DEVX) / DE_DEVX` (ddof = 1), solo como diagnóstico de geometría. No define el escalado futuro y no se guarda en FEATURES.

**Outputs.**

| Archivo | Contenido |
|---|---|
| `tables/e05_algebraic_identity__DEVX.csv` | Por terna: error máximo de `diff − (h − a)`, filas con igualdad exacta y verificación |
| `tables/e05_rank_by_triplet__DEVX.csv` | Por terna × {raw, estandarizada}: rango, nullity, σ₁ σ₂ σ₃, tolerancia, condition number y marca de singularidad |
| `tables/e05_rank_by_representation__DEVX.csv` | HA, DIFF y HADIFF × {raw, estandarizada} × {X, [1, X]}: rango, nullity, σ extremos y condition number |
| `tables/e05_vif__DEVX.csv` | Por representación y feature: SSR/SST, residuo máximo de reconstrucción, R² auxiliar, VIF, marca finito/infinito y dependencia exacta |
| `figures/e05_singular_values_by_representation__DEVX.png` | Valores singulares (estandarizados, escala log) de HA, DIFF y HADIFF con la tolerancia de rango |
| `figures/e05_vif_by_representation__DEVX.png` | VIF descriptivo de HA y DIFF. HADIFF no se dibuja: su VIF es ∞ |

### Identidad algebraica

- **Por construcción** (contrato §5.2): `diff_x = h_x − a_x`, es decir `1·h_x − 1·a_x − 1·diff_x = 0`. Es una combinación lineal no trivial de las tres columnas que da el vector cero, y eso **es** dependencia lineal exacta.
- **Verificación empírica (DEVX elegible):** las siete ternas cumplen la identidad.
  - El error máximo |`diff − (h − a)`| va de 4.4e-16 a 8.9e-16 según la terna.
  - La igualdad es bit a bit exacta en entre 767 y 1,071 de las 1,399 filas. En el resto, la diferencia es de unos pocos ulp de float64: redondeo de coma flotante al recalcular `h − a`, no una discrepancia de datos.
  - Tolerancia usada: 1e-12. Es coherente con V16, que ya validó la identidad en el pipeline.

### Rango por terna

| Terna | columnas | rango | nullity | σ₁ / σ₂ (raw) | σ₃ (raw) | tolerancia |
|---|---|---|---|---|---|---|
| ppg_season | 3 | 2 | 1 | 76.0 / 36.6 | 2.6e-14 | 2.4e-11 |
| gf_pg_season | 3 | 2 | 1 | 80.0 / 35.4 | 6.5e-15 | 2.5e-11 |
| ga_pg_season | 3 | 2 | 1 | 79.4 / 29.2 | 6.3e-15 | 2.5e-11 |
| ppg_last5 | 3 | 2 | 1 | 78.0 / 46.2 | 5.0e-14 | 2.4e-11 |
| gf_pg_last5 | 3 | 2 | 1 | 82.8 / 44.4 | 4.4e-14 | 2.6e-11 |
| ga_pg_last5 | 3 | 2 | 1 | 82.3 / 40.9 | 2.2e-14 | 2.6e-11 |
| sot_pg_last5 | 3 | 2 | 1 | 247.2 / 89.2 | 7.0e-14 | 7.7e-11 |

- **HECHO.** Las siete ternas tienen rango 2 y nullity 1, tanto en raw como estandarizadas. El tercer valor singular es entre 400 y 4,000 veces menor que la tolerancia (σ₃/tol ≤ 0.0026).
- **Condition number.** El valor numérico σ₁/σ₃ sale entre 1.2e15 y 1.3e16, pero **no se interpreta** como "multicolinealidad alta": la matriz es **singular**. σ₃ es cero salvo por precisión de coma flotante, y el condition number conceptual es ∞.

### Representaciones HA / DIFF / HADIFF

| Representación | columnas | rango X | nullity X | rango [1, X] | nullity [1, X] |
|---|---|---|---|---|---|
| **HA** (14 `h_*`/`a_*`) | 14 | 14 | 0 | 15 | 0 |
| **DIFF** (7 `diff_*`) | 7 | 7 | 0 | 8 | 0 |
| **HADIFF** (14 + 7) | 21 | **14** | **7** | **15** | **7** |

Los resultados son idénticos en raw y estandarizadas.

**HECHOS.**
- HA y DIFF tienen rango completo.
- HADIFF tiene rango 14 de 21: **nullity 7, exactamente una dependencia por terna**. Sus 7 menores valores singulares (raw: el mínimo es 4.3e-15) quedan por debajo de la tolerancia (9.6e-11). Su menor valor singular no nulo (4.64) es del mismo orden que el menor de HA (4.24).

**Intercepto.**
- Añadir una columna de unos aumenta el rango en 1 en las tres representaciones, porque ninguna columna es constante, y **la nullity de HADIFF sigue siendo 7**.
- La dependencia viene de `diff = h − a` (una combinación de columnas sin término constante), **no** del intercepto, y persiste con él.

**Estandarizar no la elimina.** Como `media(diff) = media(h) − media(a)`, se cumple `z_diff = (DE_h · z_h − DE_a · z_a) / DE_diff`. Sigue siendo una combinación lineal exacta de `z_h` y `z_a`.

**Información conservada:**
- **HADIFF** no contiene más información que HA: sus 7 columnas extra son combinaciones lineales exactas de las de HA. Su rango, 14, es el de HA.
- **DIFF** conserva el **contraste** entre equipos, pero pierde los **niveles absolutos**. Por ejemplo, `h_ppg = 2.5, a_ppg = 2.0` y `h_ppg = 1.0, a_ppg = 0.5` dan el mismo `diff_ppg = 0.5`.
- Por eso HA y DIFF son representaciones **relacionadas pero no equivalentes** (D22). HA (rango 14) contiene a DIFF; DIFF (rango 7) no permite recuperar HA.

### Valores singulares y condition number

| Representación | raw: σ_max / σ_min | raw: cond | estandarizada: cond | [1, X] raw: cond |
|---|---|---|---|---|
| HA | 310.1 / 4.24 | 73.2 | 11.3 | 114.1 |
| DIFF | 90.3 / 6.02 | 15.0 | 10.9 | 15.0 |
| HADIFF | 310.2 / 4.3e-15 | **singular** (numérico 7.2e16) | **singular** (numérico 1.6e16) | **singular** |

- El condition number depende de la escala. Por ejemplo, el raw de HA (73) refleja en parte que `sot_pg_last5` (≈ 4.5) está en otra escala que `ppg` (≈ 1.4). Estandarizado, HA y DIFF tienen condition numbers moderados y parecidos (≈ 11).
- En HA, añadir el intercepto sin centrar las columnas eleva el condition number raw (114). Con columnas estandarizadas, que son ortogonales a la columna de unos, no cambia.
- Para HADIFF, el valor numérico enorme **no** es "multicolinealidad alta": es el reflejo en coma flotante de una matriz **singular**, con 7 valores singulares que son cero salvo por redondeo.

### VIF

`VIF_j = 1 / (1 − R²_j)`, donde `R²_j` se obtiene regresando la columna j sobre las demás de su representación, con intercepto y mínimos cuadrados.

**HADIFF.** Las **21** columnas tienen SSR/SST ≤ 3.3e-28 y residuo máximo de reconstrucción ≤ 2.7e-14. Se reconstruyen **exactamente** a partir de las demás (`diff = h − a`, `h = diff + a`, `a = h − diff`), así que R² = 1 y **VIF = ∞** conceptualmente. Se marcan como `vif_finite = false` y `exact_linear_dependence = true`; el VIF no se calcula como un número enorme.

**HA y DIFF** (finitos; descriptivos, sin umbrales):

| Métrica | HA (h / a) | DIFF |
|---|---|---|
| ppg_season | 11.5 / 11.5 | 11.3 |
| ppg_last5 | 8.4 / 8.1 | 8.1 |
| gf_pg_season | 6.4 / 6.1 | 6.0 |
| gf_pg_last5 | 5.6 / 5.4 | 5.3 |
| ga_pg_season | 5.4 / 5.3 | 5.2 |
| ga_pg_last5 | 4.5 / 4.4 | 4.2 |
| sot_pg_last5 | 2.2 / 2.2 | 2.1 |

**HECHOS.**
- En HA y DIFF hay multicolinealidad **no exacta**. Es máxima en `ppg_season` (VIF ≈ 11.5) y mínima en `sot_pg_last5` (≈ 2.2).
- Los VIF de cada métrica son casi iguales en HA y en DIFF.

**INTERPRETACIÓN.** Esta multicolinealidad es coherente con dos asociaciones de E4. La primera, PPG ↔ GF/GA del mismo equipo. La segunda, season ↔ last5 de la misma métrica, que puede estar en parte inflada por las filas con `n_prev ≤ 5`, aunque eso **no se verifica aquí** (M3, E6).

**NO DECISIÓN.** No se aplica ningún umbral automático (VIF > 5 o > 10) ni se elimina ninguna variable. La asociación PPG/GF/GA **no** es una dependencia exacta y no se confunde con M1.

### Correlación vs dependencia exacta

- En E4, la correlación por pares entre `h_x` y `diff_x` era ≈ +0.7, y la mayor |r| de todo el conjunto, 0.82, era la de PPG ↔ GF. **Ningún par de HADIFF tiene correlación ±1.**
- Aun así, HADIFF tiene nullity 7.
- La razón formal de la singularidad **no** es ninguna correlación de ≈ 0.7. Es la identidad `diff = h − a`, una relación lineal exacta entre **tres** columnas que ninguna correlación por pares puede revelar por sí sola.
- Por eso el diagnóstico de M1 se basa en rango, valores singulares y R² auxiliar, no en la matriz de correlaciones.

### Implicaciones por familia de modelos

**Modelos lineales (OLS, regresión logística):**
- Con HADIFF, la matriz de diseño `[1, X]` tiene nullity 7.
- En un modelo **no regularizado**, los coeficientes individuales **no tienen solución única**: cualquier vector del espacio nulo (7 direcciones, una por terna) puede sumarse a los coeficientes sin cambiar las predicciones lineales.
- Solo con alguna restricción o regularización se obtendría una solución única, y esa solución dependería de la restricción elegida.
- Por tanto, HADIFF no debe usarse ingenuamente como matriz completa en estos modelos.

**KNN:**
- No invierte ninguna matriz de diseño, así que la dependencia exacta no lo vuelve singular.
- Pero incluir `h`, `a` y `h − a` hace que la misma información cuente varias veces en la distancia, lo que altera la ponderación implícita de cada métrica.
- E5 no concluye qué representación rinde mejor.

**Árboles y Random Forest:**
- La dependencia tampoco los vuelve singulares, y pueden manejar variables redundantes.
- Aun así, la redundancia ofrece varias variables para divisiones muy relacionadas, reparte las medidas de importancia entre ellas y aumenta la dimensionalidad sin añadir información.
- No se afirma que sea necesariamente perjudicial para el rendimiento.

### Propuesta de cierre M1

**M1 STRUCTURAL CLOSURE — APPROVED** (2026-11-01). Registrada como **D46** en `docs/DECISION_LOG.md` (patch documental 5).

> No se utilizará simultáneamente el conjunto completo `h/a/diff` (HADIFF, 21 columnas) como representación de entrada en modelos lineales no regularizados, porque `diff = h − a` introduce dependencia lineal exacta: rango 14 de 21 y nullity 7, con o sin intercepto y con o sin estandarización. HA (d = 14) y DIFF (d = 7) permanecen como representaciones candidatas **distintas y no equivalentes** para experimentación posterior: DIFF pierde los niveles absolutos (D22).

Evidencia:
- la identidad se verifica en las 7 ternas;
- cada terna tiene rango 2 de 3;
- HADIFF tiene nullity 7, que no cambia con el intercepto ni con la estandarización;
- el R² auxiliar es 1 en las 21 columnas.

### Decisiones

**Cerrado (D46, aprobado):**
- HADIFF contiene **redundancia algebraica exacta** (nullity 7).
- HADIFF **no** se usará ingenuamente como matriz completa en OLS o regresión logística no regularizada.

**Sigue abierto para el modelado:**
- HA frente a DIFF;
- el rendimiento predictivo de cada representación;
- los subconjuntos concretos (P04, provisional);
- la dimensionalidad óptima;
- el escalado (cualquier escalado futuro se ajustará solo con train, T8);
- la regularización.

**Además:**
- el Decision Log solo se actualizó con D46, tras la revisión de E5; los resultados de E5 no cambiaron;
- no se usaron targets;
- no se comparó desempeño predictivo;
- no se seleccionó, eliminó ni transformó ninguna feature;
- P01, P02 y M3 siguen abiertas.

## E6 — M3: season vs last5

**Scope:** `DEV_PREDICTORS` (`__DEVX`), 2021/22–2024/25. Es *predictor-only*: no usa targets, POST ni MARKET. No decide P02, que queda reservada para E8.

**Poblaciones (siempre etiquetadas):**
- **A_DEVX_history:** todas las filas DEVX donde la tasa existe. Por lado, `n_prev ≥ 1` (1,480 filas). En diff, ambos lados ≥ 1.
- **B_DEVX_eligible:** las 1,399 filas elegibles (verificado).

**Pares analizados:** `ppg`, `gf_pg` y `ga_pg`, cada uno en h, a y diff (9 pares). `sot_pg_last5` queda **fuera** porque no existe `sot_pg_season` en FEATURES v0.1; no se inventa.

**Convención:** `delta = last5 − season`, calculada solo en memoria y nunca guardada en FEATURES. Tolerancia de igualdad: 1e-12. Spearman se calcula por rangos medios, como en E4. Sin aleatoriedad.

**Outputs.**

| Archivo | Contenido |
|---|---|
| `tables/e06_identity_season_last5__DEVX.csv` | Verificación de la identidad por par y condición: filas evaluadas, idénticas, % y error máximo |
| `tables/e06_diff_mixed_zone_cases__DEVX.csv` | Partidos con un lado ≤ 5 y el otro ≥ 6 (§6) |
| `tables/e06_season_last5_overall__DEVX.csv` | Por población × par × zona (todo / identidad / fuera de identidad): Pearson, Spearman, MAE, RMSE, % exacto y distribución de `delta` |
| `tables/e06_season_last5_by_history__DEVX.csv` | Por población × par × tramo de historial: n, Pearson, Spearman, MAE, RMSE, % exacto, media y DE de `delta` |
| `tables/e06_collinearity_season_last5__DEVX.csv` | Rango, condition number estandarizado y VIF de HA_season+last5 (12 columnas) y DIFF_season+last5 (6) en tres subconjuntos |
| `figures/e06_season_last5_correlation_by_history__DEVX.png` | Pearson season ↔ last5 por tramo (h, a, diff) |
| `figures/e06_season_last5_mae_by_history__DEVX.png` | MAE season ↔ last5 por tramo (h, a, diff) |

- La tabla de zona mixta es adicional a las mínimas: documenta lo que pide §6.
- La figura de dispersión opcional no se generó. Habría necesitado muestreo, y las tablas por tramo ya muestran la divergencia.

### Definición estructural

- Para un equipo con `n_prev` partidos previos en la temporada, `season` promedia **todos** ellos y `last5` promedia los `min(5, n_prev)` más recientes.
- **Por construcción**, mientras `n_prev ≤ 5` la ventana last5 contiene todo el historial y `last5 = season`. A partir de `n_prev = 6`, last5 es un subconjunto estricto del historial y ambas pueden diferir.
- **Para diff:** `diff_last5 − diff_season = delta_h − delta_a`. La identidad está **garantizada** solo si **ambos** lados están en su zona de identidad, es decir `max(h_n, a_n) ≤ 5`. Si solo un lado está en ella (`min ≤ 5 < max`), la igualdad no está garantizada: solo ocurriría si `delta_a = 0` por coincidencia. Por tanto, `min(h_n, a_n) ≤ 5` **no** implica `diff_season = diff_last5`.

### Identidad temprana

Población A. La identidad es una **verificación empírica de que el dataset implementa la definición**, no un hallazgo estadístico.

| Par | Condición | Filas | Idénticas | % | Error máx. |
|---|---|---|---|---|---|
| h (ppg, gf, ga) | `h_n_prev` 1–5 | 199 | 199 | **100 %** | 0 |
| a (ppg, gf, ga) | `a_n_prev` 1–5 | 201 | 201 | **100 %** | 0 |
| diff (ppg, gf, ga) | `max(h_n, a_n) ≤ 5` | 199 | 199 | **100 %** | 0 |
| diff | **zona mixta**: un lado ≤ 5 y el otro ≥ 6 | 2 | 0 | 0 % | 0.13–0.47 |
| h / a, control | `n_prev ≥ 6` | 1,279–1,281 | 17–34 | 1.3–2.7 % | 1.66–2.28 |
| diff, control | `min(h_n, a_n) ≥ 6` | 1,279 | 7–19 | 0.5–1.5 % | 2.08–2.95 |

- **Zona mixta.** Solo **2** partidos de DEVX la ocupan, ambos elegibles: Everton–Luton y Newcastle–Burnley, del 30/09/2023, con `h_n = 6` y `a_n = 5`. Es el efecto del aplazamiento de Burnley y Luton descrito en E1. En ninguno de los dos coinciden las `diff_*` season y last5, lo que confirma la condición derivada arriba.
- **Coincidencias fuera de identidad.** El 0.5–2.7 % de filas fuera de la zona de identidad coincide por casualidad, algo esperable con valores discretos. No es identidad estructural.

### Divergencia después de cinco partidos

Correlación global frente a fuera de identidad (Pearson / Spearman):

| Par | A: global | B: global (elegibles) | fuera de identidad (h/a: `n_prev ≥ 6`; diff: `min ≥ 6`) |
|---|---|---|---|
| h_ppg | 0.817 / 0.795 | 0.782 / 0.768 | **0.748 / 0.737** |
| h_gf_pg | 0.800 / 0.789 | 0.771 / 0.767 | **0.742 / 0.740** |
| h_ga_pg | 0.785 / 0.745 | 0.738 / 0.718 | **0.701 / 0.684** |
| a_ppg | 0.812 / 0.788 | 0.779 / 0.763 | **0.743 / 0.729** |
| a_gf_pg | 0.799 / 0.774 | 0.765 / 0.751 | **0.732 / 0.720** |
| a_ga_pg | 0.764 / 0.723 | 0.727 / 0.696 | **0.687 / 0.662** |
| diff_ppg | 0.798 / 0.773 | 0.769 / 0.755 | **0.737 / 0.724** |
| diff_gf_pg | 0.785 / 0.753 | 0.749 / 0.731 | **0.716 / 0.699** |
| diff_ga_pg | 0.766 / 0.738 | 0.725 / 0.716 | **0.691 / 0.685** |

- **HECHO.** Fuera de la zona de identidad, la correlación baja de 0.73–0.78 (el valor global de E4 en elegibles) a **0.69–0.75**.
- **Por qué la correlación global no basta.** Mezcla un tramo de correlación 1 por construcción (8.4–8.6 % de las filas elegibles, 13–14 % de la población A) con un tramo donde ambas ya difieren.

### Correlación por historial

Población A, Pearson. La población B da valores idénticos desde 6–10, y en 3–5 vale 1.

| Par | 1–5 | 6–10 | 11–20 | 21–37 |
|---|---|---|---|---|
| h_ppg / h_gf / h_ga | 1 / 1 / 1 | 0.894 / 0.906 / 0.859 | 0.724 / 0.746 / 0.664 | 0.723 / 0.690 / 0.676 |
| a_ppg / a_gf / a_ga | 1 / 1 / 1 | 0.890 / 0.909 / 0.834 | 0.747 / 0.722 / 0.663 | 0.695 / 0.678 / 0.660 |
| diff_ppg / diff_gf / diff_ga | 1 / 1 / 1 | 0.884 / 0.893 / 0.835 | 0.727 / 0.723 / 0.644 | 0.705 / 0.658 / 0.675 |

**HECHO.** El patrón tiene tres etapas:
1. Las dos versiones **son idénticas** en el tramo 1–5.
2. **Divergen** de forma rápida en 6–10 (r ≈ 0.83–0.91, porque last5 todavía cubre entre la mitad y casi todo el historial).
3. Se **estabilizan** en r ≈ 0.64–0.75 desde 11 partidos, sin bajar más en 21–37.

**INTERPRETACIÓN.** Que la correlación se mantenga alrededor de 0.7 incluso con 21–37 partidos, cuando last5 ya es una fracción pequeña del historial, es compatible con un componente persistente (el nivel del equipo) que comparten ambas ventanas, junto a variación de corto plazo propia de last5. E6 **no** contrasta esta explicación. Tampoco establece si esa variación de corto plazo es señal o ruido: eso corresponde a P02 y E8.

### Diferencia season-last5

Fuera de la zona de identidad, población A:

| Par | media Δ | DE Δ | MAE | RMSE | P5 / P95 | máx \|Δ\| |
|---|---|---|---|---|---|---|
| h_ppg / a_ppg | −0.008 / +0.022 | 0.467 / 0.471 | 0.369 / 0.374 | 0.467 / 0.472 | −0.77 / +0.76 · −0.74 / +0.82 | 1.85 / 1.79 |
| h_gf_pg / a_gf_pg | +0.012 / +0.031 | 0.469 / 0.473 | 0.360 / 0.363 | 0.469 / 0.474 | −0.73 / +0.81 · −0.72 / +0.84 | 2.28 / 2.10 |
| h_ga_pg / a_ga_pg | +0.029 / +0.009 | 0.462 / 0.476 | 0.359 / 0.372 | 0.462 / 0.476 | −0.71 / +0.80 · −0.77 / +0.80 | 1.66 / 1.69 |
| diff_ppg / gf / ga | −0.030 / −0.019 / +0.019 | 0.674 / 0.674 / 0.643 | 0.536 / 0.523 / 0.502 | 0.675 / 0.674 / 0.643 | ≈ −1.1 / +1.1 | 2.37 / 2.95 / 2.08 |

**MAE por tramo de historial (población A):**

| Par | 1–5 | 6–10 | 11–20 | 21–37 |
|---|---|---|---|---|
| h / a | 0 | 0.23–0.26 | 0.35–0.37 | 0.40–0.42 |
| diff | 0–0.003 (zona mixta) | 0.33–0.36 | 0.49–0.53 | 0.55–0.59 |

**HECHOS.**
- `delta` está centrada en ≈ 0: |media| ≤ 0.031. No hay sesgo sistemático entre ventanas.
- Su dispersión es grande respecto a la escala de las features. La DE de Δ es ≈ 0.47 en h/a y la de la propia feature season es ≈ 0.47–0.57 (E3).
- La divergencia **crece de forma monótona** con el historial en todas las métricas.

**Diferencias por métrica (§13):**
- **Correlación:** fuera de la identidad, **GA/PG** es la métrica **menos** correlacionada en h, a y diff (0.687–0.701). PPG y GF/PG son las más correlacionadas (0.716–0.748).
- **MAE:** en unidades absolutas es casi igual entre métricas (h/a 0.36–0.37). En relación con su dispersión, GA diverge algo más, porque la DE de `ga_pg_season` es la menor de las tres (E3).
- **Evolución con la temporada:** en h/a, las tres métricas divergen de forma parecida (MAE ≈ 0.40–0.42 en 21–37). En diff, PPG y GF divergen algo más que GA (0.593 frente a 0.548).
- "Más diferente" **no** se interpreta como "más útil".

### Colinealidad conjunta

Diagnóstico predictor-only sobre la población B, con VIF por R² auxiliar con intercepto y condition number de las columnas estandarizadas.

| Subconjunto | n | HA_season+last5 (12 col.): rango / cond | DIFF_season+last5 (6 col.): rango / cond |
|---|---|---|---|
| elegible completo (`n_prev ≥ 3`) | 1,399 | 12 / 10.70 | 6 / 10.27 |
| `min(h_n, a_n) ≥ 6` (fuera de identidad) | 1,279 | 12 / 10.07 | 6 / 9.81 |
| `min(h_n, a_n) ≥ 11` | 1,078 | 12 / 9.91 | 6 / 9.85 |

| Feature (h / a) | elegible completo | `min ≥ 6` | `min ≥ 11` |
|---|---|---|---|
| `ppg_season` | 11.45 / 11.52 | 11.46 / 11.59 | 12.20 / 12.16 |
| `ppg_last5` | 8.36 / 8.07 | 7.39 / 7.12 | 6.87 / 6.52 |
| `gf_pg_season` | 6.30 / 6.05 | 6.18 / 6.00 | 6.26 / 5.86 |
| `gf_pg_last5` | 5.07 / 4.71 | 4.58 / 4.23 | 4.20 / 3.81 |
| `ga_pg_season` | 5.35 / 5.31 | 5.17 / 5.09 | 5.19 / 5.22 |
| `ga_pg_last5` | 4.49 / 4.36 | 4.02 / 3.90 | 3.74 / 3.63 |

En DIFF_season+last5 el patrón es el mismo: `diff_ppg_season` 11.28 / 11.20 / 12.26 y `diff_ppg_last5` 8.12 / 7.27 / 6.84.

**HECHOS.**
- Todas las representaciones combinadas tienen **rango completo**: no hay dependencia exacta entre season y last5 fuera de la identidad, a diferencia de M1.
- Al excluir el tramo de identidad, los VIF de las **last5** bajan moderadamente (≈ 9–12 % con `min ≥ 6` y ≈ 15–19 % con `min ≥ 11`). Los de las **season** apenas cambian: `ppg_season` sube ligeramente, de 11.5 a 12.2.
- El condition number baja muy poco (10.7 → 9.9).

**INTERPRETACIÓN.**
- La identidad temprana **contribuye**, pero de forma **limitada**, a la colinealidad de las last5.
- La colinealidad conjunta **persiste** fuera de la identidad. Es coherente con dos fuentes:
  - la asociación PPG ↔ GF/GA dentro de cada ventana (E4: +0.82 / −0.78), que es la principal fuente del VIF ≈ 11–12 de `ppg_season`;
  - la correlación season ↔ last5 de ≈ 0.7 que se mantiene.
- Estos valores son coherentes con los VIF de HA en E5, que incluían también SOT.

En resumen: Existe colinealidad no exacta y persistente entre las familias season y last5; los VIF alcanzan aproximadamente 12 y el condition number estandarizado ronda 10. E6 no utiliza umbrales automáticos para clasificarla ni eliminar variables.

**NO DECISIÓN.** No se aplica ningún umbral ni se elimina nada.

### Local vs visitante

**HECHO.** h y a presentan un comportamiento muy similar en este análisis:
- misma identidad (100 % en `n_prev` 1–5);
- correlación fuera de identidad con diferencias ≤ 0.014 entre lados para la misma métrica;
- MAE con diferencias ≤ 0.013;
- mismo perfil por tramo;
- VIF casi iguales.

h y a representan roles distintos dentro de cada partido; la similitud de sus resultados no las hace intercambiables.

### Diff

`delta_diff = delta_h − delta_a`, así que la divergencia season ↔ last5 de una `diff_*` puede venir del local, del visitante o de ambos.

**HECHOS.**
- La identidad solo está garantizada con `max(h_n, a_n) ≤ 5`. Hay 2 casos en zona mixta y ninguno es idéntico.
- Fuera de la identidad, las `diff_*` tienen MAE ≈ 0.50–0.54, mayor que el de h/a, porque combinan dos deltas.
- Su correlación (0.69–0.74) es similar a la de h/a.

E6 **no** atribuye la divergencia de una diff a ninguno de los dos lados.

### Interpretación

Se distinguen cuatro conceptos:
- **Idénticas.** Lo son en una región precisa: por lado con `n_prev ≤ 5`, y en diff con `max(h_n, a_n) ≤ 5`. Está demostrado y verificado.
- **Correlacionadas.** Lo siguen estando fuera de esa región (r ≈ 0.69–0.75 global; ≈ 0.64–0.75 por tramo). Está cuantificado.
- **Estadísticamente redundantes.** Que aporten información muy solapada **en un modelo concreto** no puede establecerse sin el modelo y su objetivo. E6 no lo afirma.
- **Equivalentes.** Que una pueda sustituir a la otra sin pérdida relevante para el objetivo es una pregunta predictiva. E6 **no** la responde.

### Propuesta de cierre estructural de M3

**M3 STRUCTURAL CLOSURE — APPROVED** (2026-11-01). Registrada como **D47** en `docs/DECISION_LOG.md` (patch documental 6).

> Las versiones season y last5 de PPG, GF/PG y GA/PG son **idénticas** mientras la ventana last5 contiene todo el historial disponible: `n_prev ≤ 5` en h/a, y en diff solo si ambos lados cumplen `max(h_n, a_n) ≤ 5`. A partir de ahí dejan de ser idénticas y divergen de forma creciente con el historial (MAE h/a ≈ 0.23 → 0.41), aunque conservan una correlación moderada-alta y estable (≈ 0.64–0.75 desde 11 partidos). No existe dependencia lineal exacta entre ambas familias fuera de la zona de identidad (rango completo). Existe colinealidad no exacta y persistente entre las familias season y last5; los VIF alcanzan aproximadamente 12 y el condition number estandarizado ronda 10. E6 no utiliza umbrales automáticos para clasificarla ni eliminar variables. Las correlaciones globales season–last5 están parcialmente infladas por la zona de identidad y no deben usarse solas como evidencia de redundancia.

**Evidencia:**
- identidad al 100 % en su dominio, en las 9 combinaciones;
- 2 casos en zona mixta sin identidad;
- correlación y MAE por tramo;
- rango completo y VIF de las representaciones combinadas en tres subconjuntos.

### Decisiones

**Cerrado (D47, aprobado):**
- El dominio exacto de identidad season = last5.
- La condición correcta: `n_prev ≤ 5` en h/a y `max(h_n, a_n) ≤ 5` en diff (`min ≤ 5` no basta).
- Fuera de esa zona, season y last5 dejan de ser idénticas: están relacionadas, pero no son idénticas ni se declaran equivalentes.
- Fuera de la zona no existe dependencia lineal exacta comparable a M1 (rango completo).
- La correlación global season–last5 no es evidencia suficiente de redundancia.

**Sigue abierto (P02, E8 y modelado):**
- la utilidad predictiva de last5;
- la ventana óptima;
- si conservar season, last5 o ambas;
- las ventanas alternativas (last3, last10…);
- qué representación usar en los modelos finales.

**Además:**
- **P02** no se cerró;
- **P01** sigue abierta (E7);
- **P04** sigue provisional;
- el Decision Log solo se actualizó con D47, tras la revisión de E6; los resultados de E6 no cambiaron;
- no se usaron targets;
- no se seleccionó, eliminó ni transformó ninguna feature.

## E7 — P01: burn-in

### Pregunta metodológica

**Pregunta:** ¿qué umbral mínimo de historial previo `k` equilibra razonablemente la estabilidad de las features y la conservación de observaciones?

**Regla evaluada:** un partido es elegible si `min(h_n_prev_season, a_n_prev_season) ≥ k`, para `k = 1…5` (y `k = 6` como referencia). La regla provisional actual, `k = 3`, se trata igual que las demás. No hay modelado, ni función objetivo, ni pesos.

**Criterios fijados antes de mirar la conclusión (§13 del encargo):**
- **(A)** estabilidad predictor-only;
- **(B)** estabilidad frente a una referencia retrospectiva;
- **(C)** coste en filas;
- **(D)** rendimientos decrecientes.

Un umbral mayor solo se justifica por una mejora material que compense las filas perdidas.

**Dos bloques que no se mezclan:**
- **E7A — evidencia DEVX, predictor-only.** `DEV_PREDICTORS`, 2021/22–2024/25, sin targets. Cubre el coste por `k` y la dispersión y los extremos de las features según el `n_prev` de su lado.
- **E7B — evidencia TRAIN retrospectiva.** `TRAIN_TARGET`, 2021/22–2023/24, 60 team-seasons.
  - Compara la estimación disponible tras `n` partidos (el valor congelado de FEATURES) con una **referencia retrospectiva de temporada completa**: la media de los 38 partidos del equipo, calculada desde `team_match_log`.
  - Usa **información futura a propósito**, solo como diagnóstico. **No es una feature**, no se guarda en FEATURES y **no** usa VAL ni TEST.
  - La referencia es un nivel retrospectivo más estable, **no un "valor verdadero"**.
  - Control de integridad: las estimaciones tempranas recalculadas desde `team_match_log` coinciden con FEATURES (error ≤ 1e-12).

**Unidades:**
- elegibilidad de **partidos**: `min(h_n, a_n)`;
- estabilidad de una feature de **equipo**: el `n_prev` de su lado.

Se usa siempre `n_prev`, nunca la jornada nominal: el historial se reinicia cada temporada (D14) y hay aplazamientos.

**Relación con D47:** con `n_prev ≤ 5`, las features last5 de PPG/GF/GA son idénticas a las season, así que **no** se presentan como evidencia independiente; sus tablas repiten los mismos valores. `sot_pg_last5` sí es un caso separado, porque no tiene versión season; con `n ≤ 5` promedia todos los partidos previos.

**Outputs.**

| Archivo | Bloque | Contenido |
|---|---|---|
| `tables/e07_burnin_retention__DEVX.csv` | E7A | Por `k` = 1…6 y por temporada, con totales DEVX y TRAIN: elegibles, excluidos, % retenido/perdido y coste marginal |
| `tables/e07_feature_stability_by_n_prev__DEVX.csv` | E7A | Por feature (h/a; season y last5) × nivel (1, 2, 3, 4, 5, 6–10, 11–20, 21–37): n, media, DE, IQR, P5/P95, % de extremos según las vallas de Tukey de E3 y marca D47 |
| `tables/e07_dispersion_increments__DEVX.csv` | E7A | Cambio % de DE, IQR y extremos en cada paso 1→2…4→5 |
| `tables/e07_early_vs_final_stability__TRAIN.csv` | E7B | Por métrica × `n_prev` (1–5 y 10 como madurez): sesgo, MAE, RMSE, cuantiles de \|error\| y solapamiento con la referencia |
| `tables/e07_incremental_tradeoff__TRAIN.csv` | E7B | Por métrica × paso: MAE antes y después, mejora (absoluta y %), IC 95 % bootstrap y partidos TRAIN perdidos en el paso |
| `figures/e07_stability_by_n_prev__DEVX.png` | E7A | DE relativa al tramo 21–37, lado h, season y SOT |
| `figures/e07_early_vs_final_mae__TRAIN.png` | E7B | MAE frente a la referencia por `n_prev`, con IC 95 % bootstrap |

- La tabla de incrementos DEVX va aparte para no mezclar evidencia DEVX en un archivo `__TRAIN`.
- La figura de coste no se generó: la tabla basta, porque el coste es prácticamente lineal (ver Coste por threshold).

**Bootstrap:** no paramétrico, la unidad es el team-season completo (60 en TRAIN), con B = 2,000 y **semilla 42**. Los IC al 95 % son percentiles y son descriptivos: dependen del conjunto de team-seasons observado. No hay tests de significancia.

### Coste por threshold

| k | DEVX elegibles (de 1,520) | % retenido | perdidos vs k−1 | por temporada | TRAIN elegibles (de 1,140) | TRAIN perdidos vs k−1 |
|---|---|---|---|---|---|---|
| 1 | 1,480 | 97.4 % | 40 | 370 | 1,110 | 30 |
| 2 | 1,439 | 94.7 % | 41 | 360 (359 en 2023/24) | 1,079 | 31 |
| **3** | **1,399** | **92.0 %** | 40 | 350 (349) | **1,049** | 30 |
| 4 | 1,359 | 89.4 % | 40 | 340 (339) | 1,019 | 30 |
| 5 | 1,319 | 86.8 % | 40 | 330 (329) | 989 | 30 |
| 6 | 1,279 | 84.1 % | 40 | 320 (319) | 959 | 30 |

**HECHO.** El coste es prácticamente lineal. El paso 1→2 excluye 41 partidos en DEVX y 31 en TRAIN debido a una irregularidad de calendario ya documentada en 2023/24 (E1): es la única temporada con 11 partidos en `min_n_prev = 1`, por el desfase temprano de Burnley y Luton. No es un error del dataset. Desde 2→3 en adelante, cada incremento excluye exactamente 40 partidos en DEVX y 30 en TRAIN, es decir, 10 partidos por temporada en cada una de las cuatro temporadas. Por ejemplo, subir de 3 a 4 cuesta 40 partidos DEVX (30 en TRAIN), ≈ 2.6 puntos de retención.

### Estabilidad según historial

**E7A, evidencia DEVX predictor-only.** Cada nivel exacto tiene ≈ 38–42 filas por lado.

DE de las features season relativa al tramo 21–37 (media de las 6: h/a × ppg, gf, ga):

| nivel | 1 | 2 | 3 | 4 | 5 | 6–10 | 11–20 | 21–37 |
|---|---|---|---|---|---|---|---|---|
| índice DE medio | 2.74 | 2.20 | 1.82 | 1.72 | 1.58 | 1.36 | 1.08 | 1.00 |
| % medio de extremos (Tukey E3) | 30.0 | 17.1 | 10.4 | 7.9 | 5.7 | 2.6 | 0.4 | 0.3 |

**HECHOS.**
- **DE en agregado:** baja un 20 % de 1→2, un 17 % de 2→3, un 5 % de 3→4 y un 8 % de 4→5.
- **Extremos:** su proporción baja 12.9, 6.7, 2.5 y 2.2 puntos en los mismos pasos.
- **Paso a paso por feature es ruidoso:** con unas 40 filas por nivel, la DE de algunas features **sube** en algún paso (p. ej. `h_ga_pg_season` 3→4: +14 %; `a_gf_pg_season` 4→5: +14 %), y el IQR salta por la discreción de los valores.
- **SOT:** `sot_pg_last5` baja de forma más regular (h: −8 %, −24 %, −8 %, −4 %) y se acerca a su nivel maduro antes (índice ≈ 1.0 en n = 5).
- **La estabilización no termina en n = 5:** las features season siguen teniendo en n = 5 una DE 1.58 veces la madura y ≈ 5.7 % de extremos.

### Referencia final de temporada

**E7B, evidencia TRAIN retrospectiva.** `error = estimación tras n partidos − referencia de 38 partidos`.

| Métrica (feature) | n = 1 | n = 2 | n = 3 | n = 4 | n = 5 | n = 10 (madurez) |
|---|---|---|---|---|---|---|
| PPG (`ppg_season`): MAE | 1.171 | 0.729 | 0.583 | 0.518 | 0.482 | 0.267 |
| GF/PG (`gf_pg_season`): MAE | 0.898 | 0.723 | 0.541 | 0.468 | 0.474 | 0.299 |
| GA/PG (`ga_pg_season`): MAE | 0.936 | 0.621 | 0.538 | 0.513 | 0.425 | 0.281 |
| SOT/PG (`sot_pg_last5`): MAE | 2.093 | 1.264 | 1.075 | 0.962 | 0.896 | — |
| PPG: RMSE / P90 \|error\| | 1.30 / 1.86 | 0.86 / 1.30 | 0.71 / 1.10 | 0.61 / 0.98 | 0.56 / 0.90 | 0.35 / 0.56 |

**HECHOS.**
- **Sesgo:** es prácticamente nulo (|media| ≤ 0.07 en PPG/GF/GA). La estimación temprana no sobreestima ni subestima sistemáticamente; es ruidosa.
- **Ruido que queda:** sigue siendo grande. Con 3 partidos, el MAE de PPG es 0.58 puntos por partido y el 10 % de los equipos se desvía más de 1.1. Con 10 partidos baja a 0.27.
- **SOT con n > 5:** `sot_pg_last5` ya no es una media acumulada, así que no se compara con la referencia.

### Mejora incremental

E7B, TRAIN. Mejora = MAE(n) − MAE(n+1), con IC 95 % bootstrap por team-season.

| Paso (k → k+1) | PPG | GF/PG | GA/PG | SOT/PG | coste TRAIN / DEVX |
|---|---|---|---|---|---|
| 1 → 2 | **−38 %** [0.29, 0.60] | **−19 %** [0.02, 0.36] | **−34 %** [0.15, 0.49] | **−40 %** [0.45, 1.24] | 31 / 41 |
| 2 → 3 | **−20 %** [0.04, 0.25] | **−25 %** [0.09, 0.27] | −13 % [−0.02, 0.18] | **−15 %** [0.02, 0.37] | 30 / 40 |
| 3 → 4 | −11 % [−0.01, 0.15] | −13 % [−0.01, 0.16] | −4.5 % [−0.07, 0.12] | −10 % [−0.03, 0.25] | 30 / 40 |
| 4 → 5 | −6.9 % [−0.02, 0.10] | +1.2 % [−0.05, 0.04] | **−17 %** [0.03, 0.15] | −6.8 % [−0.05, 0.18] | 30 / 40 |

Los corchetes son el IC 95 % de la mejora absoluta de MAE. En negrita, los pasos cuyo IC excluye 0.

**HECHOS.**
- **Rendimientos decrecientes:** existe un patrón de mejora grande al principio y cada vez menor. 1→2 mejora en las 4 métricas. 2→3 mejora con IC por encima de 0 en 3 de 4 (PPG, GF, SOT; GA tiene una mejora puntual del 13 %).
- **3→4:** las mejoras puntuales son del 4–13 % y **ningún IC excluye 0**.
- **4→5:** son del −1 % al 17 % y solo GA excluye 0. Es la única métrica que mejora más en 4→5 que en 3→4, lo que es coherente con el ruido a nivel de paso.
- **Coste:** 1→2 cuesta 31 partidos TRAIN (41 DEVX). Desde 2→3, cada paso cuesta exactamente 30 TRAIN (40 DEVX).

### Trade-off estabilidad vs observaciones

Respuestas explícitas (§15):
1. **¿Qué mejora hay de 2 → 3?** MAE −20 % (PPG), −25 % (GF), −13 % (GA) y −15 % (SOT); IC por encima de 0 en 3 de 4. La DE agregada DEVX baja un 17 % y los extremos 6.7 puntos. Cuesta 30 partidos TRAIN / 40 DEVX.
2. **¿Qué mejora adicional hay de 3 → 4?** MAE −11 %, −13 %, −4.5 % y −10 %, ningún IC por encima de 0. La DE agregada baja un 5 % y los extremos 2.5 puntos. Cuesta lo mismo.
3. **¿Qué mejora adicional hay de 4 → 5?** MAE −7 %, +1 %, −17 % y −7 % (solo GA por encima de 0). La DE agregada baja un 8 % y los extremos 2.2 puntos. Cuesta lo mismo.
4. **¿Cuánto cuesta cada incremento?** 1→2: 41 DEVX y 31 TRAIN (excepción de calendario de 2023/24). 2→3, 3→4 y 4→5: exactamente 40 DEVX y 30 TRAIN cada uno (10 por temporada, ≈ 2.6 puntos de retención).
5. **¿Hay evidencia clara de que k = 3 sea demasiado temprano?** **No.** A partir de 3 las mejoras se vuelven pequeñas e inciertas a coste constante. Ahora bien, con k = 3 las features siguen siendo ruidosas (MAE PPG 0.58; DE season 1.8 veces la madura), y lo serían también con k = 4 o 5 (MAE PPG 0.52 / 0.48).
6. **¿Hay evidencia clara de que k = 4 o k = 5 justifiquen el coste?** **No clara.** Las mejoras puntuales son positivas en casi todas las métricas, pero modestas, y sus IC incluyen 0 salvo GA en 4→5. Ninguna métrica muestra un salto material tras k = 3 comparable a los de 1→2 o 2→3.

**k = 2 frente a k = 3:** bajar a k = 2 recuperaría 30 partidos TRAIN (40 DEVX), pero renunciaría al paso 2→3. 2→3 es el último incremento con una mejora material respaldada en la mayoría de las métricas: el IC bootstrap excluye cero en PPG, GF/PG y SOT/PG, aunque no en GA/PG. La evidencia no apoya bajar.

### Limitaciones

- **Tamaño muestral pequeño por nivel:** ≈ 40 filas por lado en DEVX y 60 team-seasons en TRAIN. Los cambios paso a paso son ruidosos y los IC bootstrap son amplios. Diferencias de unos pocos puntos porcentuales entre pasos no son distinguibles.
- **Observaciones no independientes:** los niveles n = 1…5 de un mismo team-season están relacionados y los equipos se repiten. El bootstrap por team-season respeta la primera dependencia, pero sus IC siguen siendo descriptivos.
- **La referencia final de temporada incluye los propios partidos usados en la estimación temprana.** El solapamiento crece de 1/38 ≈ 2.6 % (n = 1) a 5/38 ≈ 13.2 % (n = 5), lo que reduce algo el error mecánicamente a medida que crece n. El efecto es pequeño en 1–5, pero no nulo. La referencia tampoco es un "valor verdadero", y la estabilidad retrospectiva no equivale a rendimiento predictivo.
- **La estabilidad no es rendimiento predictivo.** E7 no evalúa si un umbral mayor mejora un modelo, y no debe hacerlo.
- **Alcance de la evidencia:** solo cubre las features de v0.1 y su reinicio por temporada (D14). Un cambio en las features, en la memoria entre temporadas o en las ventanas podría alterar el trade-off.

### Propuesta P01

**P01 — CLOSED / PROMOTED TO D48** (2026-11-01). Registrada como **D48** en `docs/DECISION_LOG.md` (patch documental 7). Formaliza la regla ya implementada en `is_modeling_eligible`; no cambia ningún dato.

> **Mantener el burn-in en k = 3** (`min(h_n_prev_season, a_n_prev_season) ≥ 3`; 1,399 partidos DEVX elegibles, 92.0 %; 1,049 en TRAIN).
>
> **Por qué:**
> - 2→3 es el último incremento con una mejora material respaldada en la mayoría de las métricas: el IC bootstrap excluye cero en PPG, GF/PG y SOT/PG, aunque no en GA/PG. En ese paso, el MAE frente a la referencia retrospectiva baja un 13–25 % según la métrica y la DE predictor-only baja un 17 %. (1→2 mejora en las cuatro.)
> - 3→4 y 4→5 muestran mejoras menores e inciertas: MAE −4.5 % a −13 % en 3→4, sin ningún IC que excluya 0; en 4→5, solo GA/PG lo excluye.
> - Desde 2→3 en adelante el coste marginal es el mismo: exactamente 40 partidos DEVX y 30 TRAIN por paso (≈ 2.6 % de los datos).
> - k = 3 retiene 1,399 partidos DEVX (92.0 %) y 1,049 TRAIN.
>
> **Límite de la propuesta:** la evidencia **no** demuestra que k = 4 o k = 5 sean peores. Muestra que su beneficio adicional es pequeño e incierto frente a un coste fijo. Elegir k = 3 entre {3, 4, 5} es un juicio de parsimonia (no perder filas sin una mejora demostrada), no un óptimo matemático.

**Nota metodológica (recogida en D48, no reabre P01):** durante el modelado podrán realizarse análisis de sensibilidad con k = 4 y k = 5, usando solo TRAIN y validación, nunca TEST. Además, las features con poco historial seguirán siendo ruidosas con cualquier umbral razonable.

### Decisiones

**Decidido (D48):**
- burn-in oficial de v0.1: `k = 3`;
- regla: `min(h_n_prev_season, a_n_prev_season) ≥ 3`, la que ya implementa `is_modeling_eligible`.

**No demostrado:**
- que k = 3 sea matemáticamente óptimo;
- que k = 4 o k = 5 tengan peor rendimiento predictivo.

**Futuro:**
- sensibilidad con k = 4 / k = 5 durante el modelado, usando TRAIN y validación y nunca TEST para seleccionar. La regla base sigue siendo k = 3 salvo nueva decisión formal.


**Evidencia DEVX (predictor-only):**
- el coste es prácticamente lineal: 41 DEVX en 1→2 (excepción de calendario de 2023/24) y exactamente 40 DEVX en cada paso desde 2→3;
- la dispersión y los extremos bajan sobre todo hasta n = 3 y después de forma más lenta y ruidosa.

**Evidencia TRAIN (retrospectiva, información futura solo como diagnóstico):**
- mejora material respaldada en la mayoría de métricas hasta 2→3 (IC > 0 en PPG, GF/PG y SOT/PG; no en GA/PG);
- mejoras menores y estadísticamente inciertas en 3→4 y 4→5.

**Estado:**
- **P01** quedó cerrada y promovida a **D48** (k = 3), tras la revisión de E7;
- **P02** sigue abierta (E8);
- **P04** sigue provisional;
- M1 (D46) y M3 (D47) no cambian;
- el Decision Log solo se actualizó con D48 y el cierre de P01; no se ha hecho modelado ni se reconstruyó ningún dataset;
- no se seleccionaron features ni se decidieron escalado, ventana, modelo ni hiperparámetros;
- la referencia retrospectiva no se guardó en FEATURES ni se usó como feature;
- VAL y TEST no participaron en E7B.

## E8 — P02: ventana last5

### Pregunta metodológica

**Pregunta:** ¿representa `last5` una señal reciente suficientemente distinta y metodológicamente razonable como para conservarla como familia candidata en v0.1? E8 **no** intenta demostrar que 5 sea la ventana óptima. FEATURES v0.1 no contiene otras ventanas, y no se construyó ninguna (ni last3, ni last10, ni EWMA) ni una FEATURES v0.2.

**Criterios (fijados antes de mirar la conclusión, §18 del encargo):**
- **(A)** distinción estructural;
- **(B)** responsividad;
- **(C)** plausibilidad temporal en TRAIN;
- **(D)** redundancia;
- **(E)** limitaciones.

**Dos bloques que no se mezclan:**
- **E8A — DEVX (predictor-only).**
  - `DEV_PREDICTORS`, 2021/22–2024/25, sin targets.
  - Formato team-match: una fila por equipo antes de cada partido, construida desde las columnas `h_`/`a_` de FEATURES y conservando el lado.
- **E8B — TRAIN (diagnóstico target-aware).**
  - `TRAIN_TARGET`, 2021/22–2023/24, en formato team-match.
  - Las features **pre-partido** (season, last5 y `delta`) se relacionan con el resultado **realizado en ese mismo partido**, tomado de `team_match_log` (`points`, `goals_for`, `goals_against` y, como auxiliar, `shots_on_target_for`).
  - Ese resultado es POST, así que se usa **solo como outcome diagnóstico**, nunca como predictor.
  - VAL y TEST no participan.

**Zona:** `n_prev ≥ 6`. Por D47, con `n_prev ≤ 5` last5 = season y ese tramo no aporta evidencia independiente. En TRAIN quedan 1,920 filas team-match (60 team-seasons × 32 partidos).

**Convenciones:**
- `delta = last5 − season` para PPG y GF, donde positivo significa que el rendimiento reciente está por encima de la media de temporada.
- Para GA se **invierte**: `delta_ga_improvement = ga_season − ga_last5`, donde positivo significa que el equipo ha recibido **menos** goles recientemente. Si hubiera persistencia, su asociación con `goals_against` del partido sería **negativa**.

**Bootstrap:** unidad team-season (60), B = 2,000, semilla 42, IC 95 % percentil (descriptivos). Sin tests de significancia y sin modelado.

**Outputs.**

| Archivo | Bloque | Contenido |
|---|---|---|
| `tables/e08_responsiveness__DEVX.csv` | E8A | Por métrica × ventana × zona (`n_prev ≥ 6` y tramos 6–10, 11–20, 21–37): media, mediana, P75 y P90 de \|cambio\|, % sin cambio, máximo y ratio last5/season |
| `tables/e08_next_match_association__TRAIN.csv` | E8B | Pearson y Spearman de season y last5 con el outcome (total, h y a), más la fila auxiliar de SOT |
| `tables/e08_association_bootstrap__TRAIN.csv` | E8B | IC 95 % de cada correlación y de la diferencia pareada `corr_last5 − corr_season` |
| `tables/e08_delta_persistence__TRAIN.csv` | E8B | Pearson y Spearman de cada `delta` con su outcome, con IC 95 % |
| `tables/e08_delta_groups__TRAIN.csv` | E8B | Outcome medio por tercil (cortes derivados solo de TRAIN) y por signo del delta |
| `tables/e08_window_evidence_summary__TRAIN.csv` | resumen | Por métrica: distinción y responsividad (columnas `devx_*`), asociaciones y señal del delta (`train_*`) e interpretación descriptiva. Sin puntuación agregada |
| `figures/e08_responsiveness_season_vs_last5__DEVX.png` | E8A | Media de \|cambio\| por tramo, season vs last5 |
| `figures/e08_next_match_association__TRAIN.png` | E8B | Spearman de season y last5 con su outcome, con IC 95 % |
| `figures/e08_delta_persistence__TRAIN.png` | E8B | Outcome medio por tercil del delta |

- Las dos tablas de bootstrap y de grupos son adicionales a las mínimas.
- En la tabla de resumen, las columnas `devx_*` resumen evidencia predictor-only (E6/E8A) y no contienen targets.
- Las `diff_*` no se analizaron con target: el foco son las features de equipo, porque una diff mezcla dos equipos.

### Evidencia estructural heredada de D47

- Por D47, last5 = season exactamente mientras `n_prev ≤ 5`.
- Fuera de esa zona, E6 midió en DEVX:
  - un MAE |last5 − season| de 0.359–0.374 en h/a;
  - una correlación de 0.69–0.75;
  - rango completo en las representaciones combinadas.
- **Criterio A cumplido:** fuera de la zona de identidad, last5 es una variable distinta de season, aunque correlacionada con ella.

### Responsividad season vs last5

**E8A, DEVX.** `step = x_t − x_(t−1)` entre apariciones consecutivas de un mismo team-season.

| Métrica | ventana | media \|step\| (`n ≥ 6`) | mediana | P90 | % sin cambio | 6–10 | 11–20 | 21–37 |
|---|---|---|---|---|---|---|---|---|
| PPG | season | 0.069 | 0.052 | 0.14 | 1.1 % | 0.147 | 0.079 | 0.041 |
| PPG | last5 | **0.257** | 0.200 | 0.60 | 39.0 % | 0.248 | 0.263 | 0.257 |
| GF/PG | season | 0.061 | 0.042 | 0.13 | 2.3 % | 0.133 | 0.068 | 0.035 |
| GF/PG | last5 | **0.263** | 0.200 | 0.60 | 24.5 % | 0.239 | 0.267 | 0.268 |
| GA/PG | season | 0.063 | 0.043 | 0.14 | 1.8 % | 0.140 | 0.070 | 0.036 |
| GA/PG | last5 | **0.262** | 0.200 | 0.60 | 26.4 % | 0.264 | 0.261 | 0.262 |

**HECHOS.**
- Con `n_prev ≥ 6`, last5 se mueve en promedio **3.7× (PPG), 4.3× (GF) y 4.2× (GA)** más que season en cada partido.
- El cociente crece con el historial: ≈ 1.7–1.9× en 6–10 y 6.3–7.6× en 21–37.
- last5 tiene a la vez más pasos sin cambio (24–39 %), por su discreción (E3), y pasos grandes más frecuentes (P90 = 0.60).

**Memoria de la ventana.** Se sigue de la definición:
- en last5, `step = (x_nuevo − x_que_sale) / 5`, así que cada partido deja de influir cuando sale de la ventana;
- en season, `step = (x_nuevo − season_previo) / n`, así que cada partido conserva su influencia, con peso relativo 1/n decreciente.

Lo observado coincide: el movimiento de season decrece aproximadamente como 1/n y el de last5 es estable (≈ 0.24–0.27).

**Criterio B cumplido:** last5 es mucho más responsiva. Más movimiento **no** implica más capacidad predictiva, y E8 no dice que last5 esté "mejor adaptada".

### Asociación con desempeño inmediatamente posterior

**E8B, TRAIN.** n = 1,920, `n_prev ≥ 6`. Las asociaciones son univariadas y descriptivas.

| Métrica → outcome | Spearman season [IC 95 %] | Spearman last5 [IC 95 %] | last5 − season [IC 95 %] | Pearson: last5 − season [IC 95 %] |
|---|---|---|---|---|
| PPG → puntos | 0.261 [0.172, 0.325] | 0.194 [0.115, 0.262] | **−0.066 [−0.089, −0.035]** | **−0.068 [−0.093, −0.043]** |
| GF/PG → goles a favor | 0.256 [0.177, 0.312] | 0.182 [0.109, 0.241] | **−0.074 [−0.102, −0.040]** | **−0.064 [−0.090, −0.036]** |
| GA/PG → goles en contra | 0.183 [0.102, 0.246] | 0.152 [0.083, 0.213] | −0.031 [−0.060, +0.006] | **−0.043 [−0.070, −0.012]** |
| SOT last5 → tiros a puerta (auxiliar) | — | 0.210 (Pearson 0.241) | — | — |

**HECHOS.**
- Ambas ventanas se asocian **positivamente** con el desempeño del partido, en el sentido esperable (en GA, más goles recibidos antes se asocia con más goles recibidos en el partido).
- La asociación de last5 es **menor** que la de season en las tres métricas.
- La diferencia pareada tiene un IC que **excluye 0** en PPG y GF (Spearman y Pearson). En GA lo excluye con Pearson pero no con Spearman.
- **Cómo leer la figura:** los IC de cada correlación por separado se solapan, pero eso no contradice lo anterior. La diferencia se estima de forma **pareada** en cada réplica bootstrap, y por eso su IC es más estrecho que el de cada correlación.
- **Por lado:** el patrón season > last5 se repite en local y en visitante en las tres métricas (p. ej. PPG: h 0.280 frente a 0.234; a 0.251 frente a 0.171). No depende artificialmente del lado. h y a se analizan como roles distintos, no como columnas intercambiables.

### Señal de desviación reciente

**E8B, TRAIN.** ¿Persiste en el partido siguiente la desviación de la forma reciente respecto de la media de temporada?

| Delta → outcome | signo esperado si persiste | Spearman [IC 95 %] | Pearson [IC 95 %] | outcome medio por tercil T1 / T2 / T3 |
|---|---|---|---|---|
| `delta_ppg` → puntos | + | −0.001 [−0.046, +0.044] | −0.006 [−0.051, +0.038] | 1.37 / 1.41 / 1.39 |
| `delta_gf_pg` → goles a favor | + | −0.029 [−0.077, +0.017] | −0.001 [−0.051, +0.046] | 1.53 / 1.50 / 1.48 |
| `delta_ga_improvement` → goles en contra | − | −0.046 [−0.090, +0.004] | −0.031 [−0.074, +0.018] | 1.60 / 1.48 / 1.43 |

Cortes de los terciles (TRAIN): ≈ ±0.18–0.20 en cada delta. Ver `e08_delta_groups__TRAIN.csv`.

**HECHOS.**
- En **PPG** y **GF** no hay señal de persistencia: la correlación es ≈ 0 y el outcome es prácticamente plano entre terciles. En GF el punto estimado va incluso en sentido contrario al de persistencia, aunque está dentro del ruido.
- En **GA**, el punto estimado va en el sentido de persistencia defensiva: los terciles bajan de forma monótona de 1.60 a 1.43 goles en contra. Sin embargo, el IC de la correlación incluye 0 por poco.

**INTERPRETACIÓN.**
- No hay evidencia descriptiva consistente de **persistencia de corto plazo** de la desviación reciente, salvo un indicio débil y no concluyente en la forma defensiva.
- Junto con la menor asociación de last5, esto es compatible con que, univariadamente, el movimiento adicional de last5 sobre season se comporte sobre todo como **variación transitoria alrededor del nivel de temporada**. E8 no lo demuestra ni lo atribuye a ninguna causa.

### Limitaciones

- **Asociación univariada ≠ valor incremental multivariable.** Que last5 se asocie menos que season no demuestra que no aporte nada a un modelo que ya contiene season. Que tuviera más tampoco lo habría demostrado. Solo el modelado con validación puede responderlo.
- **El outcome depende también del rival.** No se ajusta por su fuerza, y una parte de la señal de cualquier feature de un solo equipo se diluye por ello.
- **Muestra y dependencia:** 60 team-seasons y 1,920 filas dependientes (el mismo equipo aparece 32 veces). El bootstrap por team-season respeta esa estructura, pero los IC siguen siendo descriptivos.
- **Diseño fijo:** E8 no puede comparar 5 con otras longitudes, porque no forman parte del diseño evaluado. Nada aquí indica si otra ventana sería mejor o peor.
- **Discreción de last5 (E3):** muchos valores repetidos, que pueden atenuar las correlaciones de rango.
- **Alcance:** solo cubre las métricas con versión season (PPG, GF, GA). SOT last5 se analizó solo como auxiliar.

### Evaluación de P02

| Criterio | Resultado |
|---|---|
| **A. Distinción estructural** | **Sí.** Fuera de la zona D47, last5 ≠ season (MAE ≈ 0.36–0.37; r ≈ 0.69–0.75) |
| **B. Responsividad** | **Sí.** ≈ 3.7–4.3× más movimiento partido a partido, estable con el historial |
| **C. Plausibilidad temporal (TRAIN)** | **Parcial / desfavorable.** last5 se asocia positivamente con el desempeño, pero **menos** que season (IC de la diferencia < 0 en PPG y GF), y su desviación respecto de season **no** muestra persistencia distinguible de 0 (indicio débil solo en GA) |
| **D. Redundancia** | **No idénticas** fuera de la zona inicial (D47). Tampoco hay evidencia univariada de que last5 contenga una señal reciente propia más allá de season |
| **E. Limitaciones** | La evidencia no permite declarar superioridad ni inutilidad sin modelado multivariable |

**Conclusión:** se cumplen A y B, pero C no ofrece la plausibilidad temporal "razonable sin señales contradictorias fuertes" que el encargo fija para el Caso A. La señal target-aware es **débil o contraria** a la hipótesis de que last5 aporte forma reciente persistente. Corresponde, por tanto, al **Caso B**.

### Propuesta P02

**P02 — REMAINS OPEN AFTER E8.** Propuesta aprobada en la revisión de E8 (ver «Cierre de la revisión E8»).

> **Mantener P02 ABIERTA hasta el modelado (Caso B).** E8 demuestra que last5 es estructuralmente distinta de season fuera de la zona D47 y mucho más responsiva (≈ 4× más movimiento por partido). Sin embargo, en TRAIN su asociación univariada con el desempeño del partido es **menor** que la de season en PPG y GF (IC 95 % de la diferencia por debajo de 0), y la desviación reciente `last5 − season` no muestra persistencia de corto plazo distinguible de 0 (solo un indicio débil en GA). La evidencia del EDA **no basta** para cerrar P02 afirmando que last5 aporta una señal reciente propia, ni para descartarla. La pregunta decisiva es si last5 añade valor **incremental** sobre season en un modelo, y debe responderse en el modelado con TRAIN y validación, nunca con TEST.

**Implicaciones prácticas, ninguna decidida aquí:**
- last5 **no** se elimina: sigue en FEATURES v0.1, que no cambia, y disponible para el modelado.
- El modelado debería incluir explícitamente una comparación "solo season" frente a "season + last5" para cada representación candidata. Afecta a P04, porque el subconjunto `d = 5` incluye `diff_ppg_last5` y `diff_sot_pg_last5`.
- No se afirma que 5 sea la longitud óptima ni que otra ventana sea mejor.

### Decisiones

**Evidencia DEVX (predictor-only):**
- last5 es distinta de season fuera de la zona D47 (E6);
- es ≈ 3.7–4.3× más responsiva;
- su memoria es acotada a 5 partidos, mientras que la de season es completa con peso 1/n.

**Evidencia TRAIN (target-aware, diagnóstico):**
- las dos ventanas se asocian positivamente con el desempeño del partido;
- last5 lo hace menos que season (PPG y GF con IC de la diferencia < 0; GA no concluyente);
- no hay persistencia de la desviación reciente distinguible de 0.

**Estado:**
- **P02** sigue **abierta** hasta el modelado (aprobado en la revisión de E8);
- **P04** sigue provisional;
- D46, D47 y D48 no cambian;
- no se ha modificado el Decision Log;
- no se construyeron ventanas alternativas, no se modificó FEATURES y no hubo modelado;
- ninguna variable POST se usó como predictor;
- VAL y TEST no participaron en E8B.

### Cierre de la revisión E8

**E8 aprobado. P02 — REMAINS OPEN AFTER E8.** Es un resultado metodológico deliberado, no una fase incompleta: la evidencia univariada del EDA no basta ni para confirmar ni para descartar last5, y la pregunta pendiente (valor incremental) solo puede responderse en el modelado.

> **P02 permanece abierta.** E8 confirma que `last5` es estructuralmente distinta de `season` fuera de la zona definida en D47 y aproximadamente cuatro veces más responsiva a cambios recientes. Sin embargo, en TRAIN las versiones `last5` de PPG y GF/PG muestran una asociación univariada menor con el desempeño del partido siguiente que sus equivalentes `season`, y la desviación `last5 − season` no presenta persistencia clara en PPG ni GF/PG. Para GA/PG existe únicamente un indicio débil. Por tanto, E8 no aporta evidencia suficiente ni para confirmar ni para descartar `last5`.

La mayor responsividad de `last5` no equivale a mayor utilidad predictiva. E8 encuentra que el movimiento adicional de la ventana reciente se comporta mayoritariamente como variación transitoria en los diagnósticos univariados disponibles.

**Confirmado:**
- `last5` es distinta de `season` después de la zona D47;
- `last5` es considerablemente más responsiva;
- ambas mantienen asociación positiva con outcomes posteriores;
- en PPG y GF/PG, `last5` presenta menor asociación univariada que `season`;
- el delta reciente no muestra persistencia clara.

**No demostrado:**
- que `last5` sea inútil;
- que `last5` aporte valor incremental sobre `season`;
- que `season` sea superior dentro de un modelo multivariable;
- que cinco partidos sea la ventana óptima.

**Requisito de evaluación futura (no es una decisión de resultado):** el modelado deberá incluir una comparación que responda si `last5` aporta información incremental sobre `season`. Como mínimo, dentro de una representación coherente: features `season` frente a features `season + last5`; `last5` sola puede añadirse como diagnóstico. Toda selección se hará con TRAIN/VALIDATION; TEST nunca se usará para decidir mantener o eliminar `last5`.

**Estado:** P02 sigue PROVISIONAL en el Decision Log, solo con su trazabilidad actualizada; no se creó ninguna decisión Dxx. `last5` permanece en FEATURES v0.1. P04 sigue provisional, con una referencia mínima a P02. Las tablas y figuras E8 no cambiaron.

## E9 — Q01: AST > AS

**Scope:** `ALL_DESCRIPTIVE` (`__ALL`). La anomalía se localiza sobre el pipeline completo. No se usan targets (`result`, `goal_difference`) ni goles de ningún partido; `is_modeling_eligible` solo se usa para contar filas. RAW se lee en modo solo lectura con el módulo `csv` de la stdlib, independientemente del pipeline, y sus SHA-256 se comprueban contra `docs/data_dictionary/raw_manifest_v0.1.csv` antes y después. No se escribe nada en RAW, INTERIM, CANONICAL, team_match_log ni FEATURES. Sin aleatoriedad (`seed = null`). Script: `src/eda/e09_q01_anomaly.py`.

### Definición de la anomalía

En Football-Data, `AS` son los tiros del visitante y `AST` sus tiros a puerta. Por definición los tiros a puerta son un subconjunto de los tiros, así que debe cumplirse `AST ≤ AS` (y `HST ≤ HS`). Una fila con `AST > AS` es internamente incompatible. Esto distingue a Q01 de los 12 `GOALS_GT_SOT`, que no violan esa relación de subconjunto y no se reabren aquí.

Se distinguen tres cosas que no deben confundirse:
- **Valor observado:** lo que contiene la fuente (`AST = 9`, `AS = 8`).
- **Restricción lógica:** `AST ≤ AS`.
- **Escenarios diagnósticos:** la fila demuestra que el **par** (AS, AST) es incompatible, pero **no** qué columna es errónea. Hay dos reparaciones mínimas de un solo campo, ambas solo en memoria:
  - **Escenario A**, AS asumido correcto: `AST: 9 → 8`, es decir `min(AST, AS)`.
  - **Escenario B**, AST asumido correcto: `AS: 8 → 9`, es decir `max(AS, AST)`.

  Puede que ambos valores sean erróneos (escenario C), y E9 no tiene evidencia para distinguir entre los tres. Ningún escenario es el valor verdadero ni una corrección aprobada.

### Localización

| Campo | Valor |
|---|---|
| Temporada / split | 2021/22 / **TRAIN** |
| Fecha | 2021-08-15 (RAW `15/08/2021`), 14:00 |
| Partido | Newcastle United (local) – **West Ham United** (visitante) |
| Fuente | `PL_2021-2022_raw.csv`, `source_row = 9` |
| `match_id` | `EPL_2021-2022_20210815_newcastle_united_west_ham_united` |
| `AS` / `AST` | 8 / 9 → `AST − AS = +1` |
| `HS` / `HST` | 17 / 3 (consistente) |
| `dq_flags` | `AST_GT_AS` |

- **Conteos:** de los 1,900 partidos, exactamente **1** tiene `AST > AS` y **0** tienen `HST > HS`, tanto en CANONICAL como en el barrido independiente de RAW.
- **Flag:** `AST_GT_AS` marca exactamente esa fila y ninguna otra.

### Trazabilidad RAW → downstream

| Capa | Localizador | HS | AS | HST | AST | Observación |
|---|---|---|---|---|---|---|
| RAW | `source_row = 9` | 17 | 8 | 3 | 9 | valor fuente |
| INTERIM | `source_file` + `source_row` | 17 | 8 | 3 | 9 | idéntico carácter a carácter; solo `Date` está tipada a ISO (`interim_schema`), con el mismo día |
| CANONICAL | `match_id` | 17 | 8 | 3 | 9 | valor conservado (D03), `dq_flags = AST_GT_AS` |
| team_match_log, Newcastle (local) | `match_id` + `team_id` | — | — | — | — | `shots_on_target_for = 3` (HST) |
| team_match_log, West Ham (visitante) | `match_id` + `team_id` | — | — | — | — | `shots_on_target_for = 9` (AST) |

Tabla completa en `tables/e09_q01_traceability__ALL.csv`.

### Clasificación de la causa

**A. Anomalía presente en la fuente (inconsistencia lógica del par en la fila fuente).** Está demostrado por trazabilidad, no inferido:
- **RAW** ya contiene `AS = 8` y `AST = 9`;
- **INTERIM** los preserva sin cambios;
- **CANONICAL** los conserva sin corregir, según la política RAW (D03), y los marca;
- **team_match_log** asigna AST al visitante y HST al local, sin que el valor pase al otro equipo.

**Causas descartadas:**
- B (parseo): los enteros coinciden con el texto RAW;
- C (transformación): ninguna capa cambia el valor y la orientación home/away es correcta;
- D (otra causa): ninguna capa del pipeline altera el valor.

**Lo que no se demuestra:** qué campo es erróneo (AS, AST o ambos). El flag `AST_GT_AS` describe correctamente la violación observada, no atribuye el error a AST. No se consultaron fuentes externas.

### Propagación a SOT last5

- **Única feature expuesta:** `team_match_log` solo guarda los tiros a puerta propios (`shots_on_target_for`). La única feature que depende de AST es `sot_pg_last5` de West Ham en 2021/22 (como `h_` o `a_`, según la localía) y, a través de ella, `diff_sot_pg_last5`.
- **Features no afectadas:**
  - PPG, GF/PG, GA/PG y `n_prev`, que no dependen de tiros;
  - las features de Newcastle y de cualquier otro equipo.
- **Posición y ventana:** Q01 es el **partido 1 de 38** de West Ham. Por `shift(1)`, su propia feature tiene historia vacía (`n_prev = 0`, `a_sot_pg_last5` nulo): **Q01 no contamina el partido en el que aparece**. El valor entra en la ventana desde el partido 2 y permanece en ella exactamente **5 partidos** (posiciones 2–6, `n_prev` 1–5). En el partido 7 (`n_prev = 6`, ventana 2–6) ya ha salido. Como ocurre al inicio de temporada, la ventana nunca se trunca.
- **Comprobación:** recalculé en memoria `sot_pg_last5` con el valor observado para los 38 partidos de West Ham, y coincide exactamente con FEATURES.

| Pos. | Fecha | Partido | Lado WHU | n_prev | SOT last5 obs. | diff_sot_pg_last5 | Elegible |
|---|---|---|---|---|---|---|---|
| 1 (Q01) | 2021-08-15 | Newcastle – West Ham | a | 0 | — (no afectado) | — | no |
| 2 | 2021-08-23 | West Ham – Leicester | h | 1 | 9.000 | 4.000 | no |
| 3 | 2021-08-28 | West Ham – Crystal Palace | h | 2 | 8.000 | 6.500 | no |
| 4 | 2021-09-11 | Southampton – West Ham | a | 3 | 6.667 | −2.667 | **sí** |
| 5 | 2021-09-19 | West Ham – Man United | h | 4 | 5.750 | 0.250 | **sí** |
| 6 | 2021-09-25 | Leeds – West Ham | a | 5 | 5.400 | −1.000 | **sí** |
| 7 | 2021-10-03 | West Ham – Brentford | h | 6 | 5.000 (ya no contiene Q01) | 2.400 | sí |

En los 5 partidos afectados el rival tiene `sot_pg_last5` no nulo, así que también queda afectada `diff_sot_pg_last5`. Tabla completa en `tables/e09_q01_feature_propagation__ALL.csv`.

**Recuento:**

| Nivel | Afectados | Proporción |
|---|---|---|
| Filas fuente | 1 | de 1,900 |
| Filas team-match | 1 | de 3,800 |
| Partidos con `h_`/`a_sot_pg_last5` afectada | 5 (0.26 % de 1,900) | de ellos, 3 elegibles (0.17 % de 1,749) y 2 no elegibles por burn-in (1.3 % de 151) |
| Partidos con `diff_sot_pg_last5` afectada | los mismos 5, 3 elegibles | — |
| En TRAIN | 5 de 1,140 partidos (0.44 %); 3 de 1,049 elegibles (0.29 %) | — |
| En VALIDATION y TEST | 0 | — |
| Celdas de feature afectadas | 10 (5 `h_`/`a_` + 5 `diff_`) | — |

### Sensibilidad mínima

Cada escenario es una sensibilidad **condicionada a su asunción**, calculada en memoria. No mide el «impacto de corregir el dato», porque no se sabe qué campo corregir.

**Escenario A: AS asumido correcto, AST reparado 9 → 8.** El delta de `sot_pg_last5` vale exactamente −1/n_prev.

| n_prev | Obs. | Escenario A | Δ abs. | Δ rel. | Δ diff |
|---|---|---|---|---|---|
| 1 | 9.000 | 8.000 | −1.000 | −11.1 % | −1.000 |
| 2 | 8.000 | 7.500 | −0.500 | −6.3 % | −0.500 |
| 3 | 6.667 | 6.333 | −0.333 | −5.0 % | +0.333 |
| 4 | 5.750 | 5.500 | −0.250 | −4.3 % | −0.250 |
| 5 | 5.400 | 5.200 | −0.200 | −3.7 % | +0.200 |

El signo de Δ diff depende del lado: es −Δ cuando West Ham es visitante, porque `diff = h − a`. En las 3 filas elegibles, el cambio es ≤ 0.333 tiros por partido, que equivale a ≤ 0.24 DE de `sot_pg_last5` (DE ≈ 1.39 en `h_` y 1.42 en `a_`, DEVX elegible, tabla E3, predictor-only).

**Escenario B: AST asumido correcto, AS reparado 8 → 9.** El delta es **0** en `sot_pg_last5`, en `h_`/`a_sot_pg_last5` y en `diff_sot_pg_last5`, en los 5 partidos. SCOPE construye SOT con AST/HST, no con AS/HS, y AS no entra en ninguna feature de v0.1. Este escenario sí alteraría `away_shots`, una estadística POST de la fuente que no se usa como predictor.

**Sin cota del valor verdadero:** la versión anterior de E9 daba el rango 0 ≤ AST ≤ 8. Lo eliminé, porque solo es válido si se asume que AS = 8 es correcto; sin esa asunción, la fila no acota AST superiormente (por ejemplo, AST = 9 y AS = 9 es una reparación válida). No construyo ninguna distribución de valores posibles.

Tabla en `tables/e09_q01_minimal_repair_sensitivity__ALL.csv`; recuentos en `tables/e09_q01_impact_summary__ALL.csv`. La tabla de sensibilidad tiene una fila por partido afectado y escenario (A y B), con la columna `scenario`. No se generó figura, porque con 5 filas la tabla comunica mejor el resultado.

### Materialidad

**Hecho: la propagación del valor observado está localizada en extensión.**
- 1 fila fuente y 1 fila team-match;
- 5 partidos posteriores con el valor en la ventana, 3 de ellos elegibles (0.17 %);
- solo `sot_pg_last5` (`h_`/`a_`) y su `diff`.

**Separado de lo anterior, la magnitud del efecto que tendría una corrección es desconocida**, porque no sabemos qué campo de la fuente es erróneo:
- si AS = 8 fuera correcto y AST debiera bajar a 8 (escenario A), el efecto mínimo en las filas elegibles sería ≤ 0.33 tiros a puerta por partido;
- si AST = 9 fuera correcto y el error estuviera en AS (escenario B), las features SOT no cambiarían.

No se usan umbrales arbitrarios de materialidad.

### Opciones de tratamiento

| Opción | Ventajas | Problemas |
|---|---|---|
| **A. Conservar los valores fuente + flag** | No asume qué campo es erróneo (AS, AST o ambos); RAW fiel; FEATURES congeladas (D44); `dq_flags` mantiene la anomalía trazable; no inventa datos | Mantiene un par lógicamente incompatible en la fuente y el valor AST observado en 10 celdas de feature |
| **B. Reparación determinista de AST** (`AST = min(AST, AS)`) | Restaura el dominio lógico | **Asume** que AS es correcto; no recupera el valor verdadero; exige una nueva versión de CANONICAL, team_match_log y FEATURES (rompe D44 para v0.1) |
| **C. Reparación determinista de AS** (`AS = max(AS, AST)`) | Restaura el dominio lógico; en v0.1 no cambiaría las features SOT | **Asume** que AST es correcto; altera una estadística POST de la fuente; exige una nueva versión de CANONICAL |
| **D. Missing** (en el campo dudoso o en el par) | No inventa nada | No se sabe qué campo es el dudoso; introduce missingness donde hoy no hay; requiere una política downstream nueva y una nueva versión de datos |
| **E. Exclusión como sensibilidad** | Evita depender del dato dudoso | Sacrificaría 3 partidos elegibles de TRAIN con el resto de sus features correctas; solo como análisis de sensibilidad, nunca automática |

Ninguna de las opciones B–E se adopta.

### Propuesta Q01

**PROPUESTA, pendiente de revisión.** No se ha incorporado al Decision Log.

> Q01 es una **inconsistencia aislada presente en la fuente**. El pipeline la preserva y la marca correctamente. Sin verificación externa no puede determinarse si el error está en AS, en AST o en ambos, así que una reparación determinista introduciría una asunción no demostrada. Su propagación observada está localizada: `sot_pg_last5` de West Ham y su `diff` en los partidos 2–6 de 2021/22, con 3 filas elegibles, todas en TRAIN. **v0.1 conserva los valores fuente y la trazabilidad (Opción A).** Cualquier reparación futura requeriría una decisión y un versionado explícitos.

**Implicaciones, ninguna decidida aquí:**
- No hace falta reconstruir nada en v0.1.
- Si el equipo lo desea, el modelado podría incluir un análisis de sensibilidad opcional sin esas 3 filas elegibles, solo con TRAIN/VALIDATION. E9 no lo exige.
- El registro de calidad ya prevé «excluir de features… solo si el EDA demuestra impacto». E9 muestra una propagación localizada en extensión, con una magnitud que depende del campo erróneo (desconocido): no demuestra la necesidad de excluir.

### Limitaciones

- **Campo erróneo desconocido:** no se sabe si el error está en AS, en AST o en ambos. Los escenarios A y B están condicionados a su asunción, y no se acota el valor verdadero de ninguno de los dos campos.
- **Sin fuente externa:** la verificación externa sería una tarea separada.
- **EDA previo:** las fases que usaron SOT en DEVX o TRAIN (E3, E4, E7) incluyen estas filas; no se recalcularon. E8B usó `n_prev ≥ 6` y no contiene ninguna fila afectada.
- **Alcance:** E9 no evalúa los 12 `GOALS_GT_SOT` ni ninguna otra anomalía.

### Decisiones

- **Q01:** propuesta pendiente de revisión (Opción A); no se ha creado ninguna decisión Dxx.
- **Sin cambios:** no se modificó RAW, INTERIM, CANONICAL, team_match_log ni FEATURES, y los hashes D44 están intactos.
- **P02 y P04:** P02 sigue abierta y P04 sigue provisional. Q01 afecta a `diff_sot_pg_last5`, que está en el subconjunto `d = 5` de P04, pero no cambia su estado. P02 no depende directamente de SOT: E8 lo usó solo como auxiliar y con `n_prev ≥ 6`.
- **Sin modelado:** no hubo modelado y ningún target se usó para caracterizar ni tratar Q01.

### Cierre de la revisión E9

**E9 aprobado. Q01 queda cerrada formalmente con D49** (Decision Log, patch documental 9). Los resultados numéricos de E9 no cambian.

**Decidido:**
- conservar los valores fuente (`AS = 8`, `AST = 9`);
- mantener el flag `AST_GT_AS`;
- no aplicar ninguna reparación en v0.1;
- RAW permanece inmutable. Conservar los valores no significa considerarlos correctos; cualquier reparación futura será en una capa derivada, versionada y con una decisión explícita.

**No conocido:**
- qué campo es incorrecto (AS, AST o ambos);
- cuál es el valor verdadero;
- cuánto cambiaría exactamente una corrección real. Los escenarios A (≤ 0.33 tiros a puerta por partido en filas elegibles) y B (delta 0) son solo sensibilidades condicionadas.

La anomalía es **localizada en extensión** (un equipo, una ventana de cinco partidos, tres filas elegibles, una familia de feature y su diferencia), no necesariamente pequeña en magnitud real. Excluir esas filas no es obligatorio; queda solo como posible análisis de sensibilidad del modelado (TRAIN/VALIDATION, nunca TEST). P02 sigue abierta y P04 sigue provisional.

## E10 — Drift temporal

### Pregunta

¿Hasta qué punto cambian las distribuciones de las features pre-partido entre temporadas y entre los bloques TRAIN (2021/22–2023/24), VALIDATION (2024/25) y FINAL TEST (2025/26)? E10 caracteriza el cambio temporal: no selecciona features, no modifica transformaciones ni decide modelos.

### Población y scopes

- **Población:** filas elegibles (D48, `min(h_n_prev, a_n_prev) ≥ 3`): **350 / 350 / 349 / 350 / 350** por temporada, verificado desde datos. 2023/24 tiene 349 por su irregularidad de calendario (E7).
- **Features:** las 23 PRE, analizadas columna a columna:
  - season: h/a/diff de PPG, GF/PG y GA/PG;
  - last5: h/a/diff de PPG, GF/PG, GA/PG y SOT/PG;
  - `h_`/`a_n_prev_season`.

  **No se usan** targets, goles, POST ni MARKET.
- **Scopes:**
  - **TRAIN / DEVX** (`__DEVX`, predictor-only): TRAIN → VALIDATION. El bloque VAL coincide exactamente con el cargado desde `VAL_DESCRIPTIVE`.
  - **ALL** (`__ALL`): resumen por temporada, pares consecutivos, familias, composición de equipos y cobertura de fuente. Las filas que incluyen 2025/26 llevan `decision_use = DESCRIPTIVE_ONLY`.
  - **FINAL TEST** (`__TEST`): TRAIN → 2025/26, con `decision_use = DESCRIPTIVE_ONLY`.
- **Medidas:**
  - `SMD = (mean_B − mean_A) / s_p`, con `s_p` la DE pooled de ambos grupos (ddof = 1).
  - `KS = max_x |F_A(x) − F_B(x)|`, con ECDF empíricas evaluadas en la unión de valores. La implementación es propia con NumPy y se comprueba con casos simples (idénticas, disjuntas, desplazamiento, empates y tamaños distintos).
  - KS = 0 significa ECDF idénticas; valores mayores, más separación. **No hay umbrales, cortes PASS/FAIL ni p-values**, y no se agrega ningún «drift score».

### Distribuciones por temporada

Tabla `e10_feature_summary_by_season__ALL.csv`: n, media, mediana, DE, Q1, Q3, IQR, P5, P10, P90, P95, mínimo y máximo para cada feature y temporada.

- **GF/PG, GA/PG y SOT/PG (h/a) tienen un pico en 2023/24.** En la transición 2022/23 → 2023/24, el SMD es de +0.27 a +0.41 en las 10 features de nivel h/a (GF y GA en season y last5, y SOT last5), y ese salto se revierte en parte en 2023/24 → 2024/25 (SMD −0.20 a −0.26). Por ejemplo, `h_sot_pg_last5` tiene media 4.33 / 4.35 / **4.86** / 4.51 / 4.13 y `a_ga_pg_season` 1.38 / 1.41 / **1.58** / 1.47 / 1.36.
- **PPG (h/a) apenas cambia de centro** (|SMD| ≤ 0.06 en todos los pares). Es compatible con la escala restringida de PPG, pero que esté acotada no explica por sí solo el bajo drift. E10 no investiga otras causas.
- **Las `diff_*` son muy estables en el centro** (|SMD| ≤ 0.05 en todos los pares). Un cambio de nivel que afecta a toda la liga desplaza por igual a local y visitante y se cancela en la diferencia.
- **`n_prev`** es prácticamente idéntico (|SMD| ≤ 0.005, KS ≤ 0.009). Es estructural: la población elegible tiene el mismo calendario cada temporada.
- **Dispersión de GF/PG season:** la DE de `h_gf_pg_season` es 0.56 / 0.62 / 0.54 / 0.46 / 0.38, es decir, menor en las dos últimas temporadas.

### TRAIN → VALIDATION

Evidencia que puede informar la comprensión del desarrollo (TRAIN / DEVX). Tabla `e10_train_val_drift__DEVX.csv`, figura `e10_train_val_drift__DEVX.png`.

- **Centro:** la media de VALIDATION es prácticamente la de TRAIN pooled. |SMD| ≤ 0.030 en las 23 features (máximo `h_gf_pg_season`, +0.030).
- **Forma:** la KS es mayor en las features season (0.08–0.10 en GF, GA y PPG h/a) que en last5 (≤ 0.071). El caso más claro es **GF/PG season**: la media no cambia, pero la DE de VAL es ≈ 0.77–0.79 veces la de TRAIN (más concentrada), con KS 0.095–0.104. Es un cambio de dispersión, no de localización.
- **Advertencia de lectura:** la cercanía TRAIN → VAL **no** significa que el periodo sea homogéneo. TRAIN es internamente heterogéneo: contiene la temporada 2023/24 alta, y su media pooled queda cerca de la de 2024/25. Los saltos entre temporadas consecutivas dentro de TRAIN (hasta |SMD| ≈ 0.41) son mucho mayores que el salto TRAIN → VAL.
- **Pool de TRAIN:** su DE incluye una pequeña componente entre temporadas. Con SMD entre temporadas ≤ 0.41, esa componente es menor y no cambia el patrón.

### TRAIN → FINAL TEST — descriptivo

**Evidencia descriptiva, no decisional.** Tabla `e10_train_test_drift__TEST.csv` (`decision_use = DESCRIPTIVE_ONLY`), figura `e10_train_test_drift__TEST.png` (título «DESCRIPTIVE ONLY — FINAL TEST»).

- **Nivel más bajo:** 2025/26 tiene niveles más bajos de producción ofensiva previa que TRAIN.
  - SOT/PG last5: SMD −0.29 / −0.30 (h/a), medias 4.51 → 4.13 y 4.61 → 4.20;
  - GA/PG season: −0.20 / −0.22;
  - GF/PG season: −0.18 / −0.16;
  - GF/GA last5: −0.14 a −0.17.
- **Distribuciones más concentradas:** la DE de TEST es 0.66–0.88 veces la de TRAIN en GF, GA y SOT, y 0.85–0.86 en PPG season. Por eso PPG season tiene KS 0.12–0.14 con SMD ≈ 0.
- **Lo que no cambia:** las `diff_*` siguen estables en el centro (|SMD| ≤ 0.026), aunque `diff_gf_pg_season` tiene KS 0.12 (DE × 0.68). `n_prev` no cambia.
- **Top 10:** por |SMD| y por KS, las listas TRAIN → TEST las encabezan SOT last5, GA season y GF season. Las listas están en la tabla (columnas `rank_*`, `top10_*`).

> Esto documenta una diferencia de distribución que debe tenerse en cuenta al interpretar el desempeño final, pero no modifica el protocolo. Nada observado en TEST cambia features, burn-in, umbrales, transformaciones, selección, modelos, hiperparámetros, calibración ni el tratamiento de anomalías.

### Cambios por familia de feature

Tabla `e10_family_drift_summary__ALL.csv`: mediana y máximo de |SMD| y de KS por métrica, ventana y lado. No es una puntuación agregada.

1. **¿Season más estable que last5?** No de forma general. A igual métrica, los desplazamientos de media son similares (2022/23 → 2023/24: GF season +0.27 frente a last5 +0.28–0.31; GA season +0.36–0.41 frente a last5 +0.31–0.36). En estas comparaciones, algunas features season tienen KS mayor que sus equivalentes last5 (hasta 0.27 frente a 0.17), pese a desplazamientos de media similares. Eso indica diferencias en la forma de las distribuciones empíricas; E10 no atribuye la magnitud de KS a continuidad, discreción ni concentración. La mediana por ventana favorece a season solo porque esa familia incluye PPG.
2. **¿SOT cambia más?** Es la familia con mayor |SMD| en TRAIN → TEST (−0.29 / −0.30) y en 2024/25 → 2025/26 (−0.32 / −0.34). En 2022/23 → 2023/24 (+0.35 / +0.38) cambia de forma comparable a GA season (+0.36 / +0.41). En TRAIN → VAL no destaca (|SMD| ≤ 0.010).
3. **¿diff más estable que h/a?** Sí, en el centro, en todas las comparaciones: la mediana de |SMD| de diff es ≤ 0.02 frente a 0.16–0.31 de h/a en las transiciones con cambio. También en KS, salvo `diff_gf_pg_season` en TEST (cambio de dispersión).
4. **¿Local y visitante cambian igual?** Sí: las trayectorias h_ y a_ son casi superpuestas (figura `e10_feature_means_by_season__ALL.png`) y sus SMD tienen el mismo signo y magnitud similar en cada transición.

### Composición de equipos

Tabla `e10_team_composition_by_season__ALL.csv`: 20 equipos por temporada; en cada transición consecutiva hay **17 compartidos, 3 entrantes y 3 salientes**.

**Sensibilidad con equipos comunes** (`e10_common_teams_sensitivity__ALL.csv`, formato team-match, filas elegibles; PPG, GF y GA season y SOT last5):

| Transición | Feature | SMD todos | SMD comunes |
|---|---|---|---|
| 2022/23 → 2023/24 | GF season | +0.27 | +0.40 |
| | GA season | +0.39 | +0.30 |
| | SOT last5 | +0.36 | +0.46 |
| 2023/24 → 2024/25 | GF, GA y SOT | −0.21 a −0.24 | −0.23 a −0.24 |
| 2024/25 → 2025/26 (descriptivo) | GF season | −0.25 | −0.41 |
| | GA season | −0.24 | −0.07 |
| | SOT last5 | −0.33 | −0.46 |

**Lectura:**
- El pico de 2023/24 y su reversión **persisten entre los 17 equipos comunes**, así que no se explican solo por el cambio de composición.
- En la transición a 2025/26 (descriptivo), la caída de GA casi desaparece entre equipos comunes; eso es compatible con que parte de ella dependa de los equipos entrantes y salientes.
- Esta sensibilidad no corrige nada ni excluye equipos ascendidos.

### Fútbol vs pipeline

- **Sin indicio técnico de que el drift venga del pipeline:**
  - todas las columnas fuente que alimentan las features (`Date`, `Time`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, `FTR`, `HST`, `AST`) están presentes y sin vacíos en las 5 temporadas (`e10_source_coverage__ALL.csv`);
  - los anchos RAW son 106 / 106 / 106 / 120 / 132 columnas. La columna `interim_columns_nonempty` de `e10_source_coverage__ALL.csv` (110 / 110 / 110 / 124 / 136) cuenta columnas de INTERIM, es decir RAW más las 4 de trazabilidad (`season`, `source_name`, `source_file`, `source_row`), que no son columnas de la fuente. Según `docs/data_dictionary/raw_dictionary_v0.1.csv`, las 74 columnas que no están en las cinco temporadas pertenecen todas a familias de cuotas (`odds_1x2_pre`/`close`, `odds_ou25_*`, `odds_ah_*`). Las ampliaciones del esquema no implican, por tanto, pérdida de cobertura de los predictores usados en E10;
  - el código de features es el mismo para todas las temporadas (D44).
- **Interpretación:** los cambios observados son compatibles con cambios reales de la distribución deportiva (nivel de goles y tiros a puerta de la liga, y su dispersión entre equipos), en parte modulados por la composición. E10 no verifica ninguna causa externa.
- **MARKET:** los cambios de mercado de E2m (overround, composición de casas) no son drift de predictores, porque MARKET no es predictor en v0.1.

### SMD vs KS

Las dos métricas no cuentan siempre la misma historia:
- **SMD ≈ 0 con KS relativamente mayor** (cambio de forma o dispersión): PPG season h/a (TRAIN → TEST, SMD 0.01–0.03, KS 0.12–0.14), GF season en TRAIN → VAL (SMD 0.01–0.03, KS 0.10) y `diff_gf_pg_season` en TEST (SMD −0.01, KS 0.12).
- **SMD relativamente alto con KS más moderada:** SOT last5 y GF/GA last5 en TEST (SMD hasta −0.30, KS 0.08–0.14). Predomina un desplazamiento de localización. No se atribuye causalmente la magnitud de KS a la discreción de last5.
- **Cuantiles** (P10 / P25 / P50 / P75 / P90): en `h_gf_pg_season`, TEST recorta sobre todo la cola alta (P90 2.32 / 2.30 / 2.32 / 2.00 / 1.87); en `h_sot_pg_last5`, todo el centro y la cola alta bajan (P50 4.0 / 4.2 / 4.8 / 4.4 / 4.0; P90 6.4 / 6.2 / 7.0 / 6.2 / 5.6).

### Implicaciones

**Evidencia que puede informar la comprensión del desarrollo (TRAIN / DEVX):**
- TRAIN → VAL tiene un desplazamiento de medias muy pequeño (|SMD| ≤ 0.030) y algunos cambios de forma o dispersión visibles en KS en las features season (sobre todo GF).
- TRAIN es internamente heterogéneo (pico de 2023/24). Cualquier escalado o modelo ajustado en TRAIN verá una mezcla de niveles de liga; esto es una característica del periodo, no un defecto de datos.
- Las representaciones en diferencias son más estables en el centro que los niveles absolutos h/a. Esto es relevante para interpretar la comparación HA frente a DIFF (D46) en el modelado, **sin decidirla aquí**.

**Evidencia descriptiva no decisional (FINAL TEST):**
- 2025/26 tiene niveles más bajos y menos dispersos de GF, GA y SOT que TRAIN. Es un riesgo de generalización que deberá tenerse en cuenta al interpretar el desempeño final; no modifica el protocolo.

**No decidido:** eliminar features, P02, P04, D48, escalado, domain adaptation, recalibración, reentrenamiento ni selección de modelo. No se creó ninguna decisión ni propuesta nueva.

### Limitaciones

- Análisis marginal, columna a columna: no capta cambios en la dependencia entre features.
- Las filas dentro de una temporada son dependientes (mismo equipo, ventanas solapadas). Las magnitudes son descriptivas, sin IC ni tests.
- Solo hay 5 temporadas, así que no se puede separar una tendencia de la variación entre temporadas.
- last5 es discreta: su ECDF tiene saltos y empates, lo que afecta la forma de la distribución empírica. Comparar KS entre ventanas de distinta granularidad requiere cautela, sin suponer que la discreción la reduzca necesariamente.
- La sensibilidad con equipos comunes cubre solo 4 features a nivel team-match.
- Q01 (D49) afecta a 3 de las 350 filas elegibles de 2021/22, solo en SOT last5. No se recalculó E10 excluyéndolas.

### Decisiones

- **Sin cambios en decisiones:** no se creó ni modificó ninguna decisión; P02 sigue abierta, P04 provisional y D46–D49 sin cambios.
- **TEST:** solo se usó de forma descriptiva.
- **Datos:** no se usaron targets ni POST y no se modificó ningún dataset.

## E11 — Síntesis final

**Scope:** `ALL_DESCRIPTIVE`. Fase de síntesis: no hay análisis nuevos, targets, modelado ni recálculo de fases anteriores. `src/eda/e11_synthesis.py` verifica:
- los hashes D44 y RAW;
- que las fases E1–E10 están en el manifiesto con todos sus outputs y hashes;
- en el Decision Log: D46–D49 presentes y ninguna D50; P01, P05 y P08 cerradas; P02, P03, P04, P06 y P07 vigentes.

También ensambla tres tablas: `e11_eda_phase_summary__ALL.csv` (matriz de fases: 12 filas, E0 de infraestructura y las 11 fases analíticas E1, E2, E2m y E3–E10; E11 no tiene fila porque es la síntesis), `e11_decision_status__ALL.csv` (estado de decisiones) y `e11_modeling_handoff__ALL.csv` (requisitos para modelado). El documento narrativo formal es `docs/Documentacion del proyecto/03_analisis_exploratorio_eda.md`. No se generó figura de roadmap, porque sería redundante con el documento.

### Hallazgos principales

- **Datos:** íntegros (D44); missingness solo estructural (50 partidos inaugurales); 1,749 partidos elegibles; 13 `dq_flags` documentados.
- **Targets:** H 45.8 % / D 22.5 % / A 31.7 % en TRAIN. El empate es la clase minoritaria y se solapa ampliamente con H y A en las features individuales.
- **Mercado:** benchmark externo coherente (Σp = 1). El empate nunca es favorito. No es predictor en v0.1.
- **Features:** regulares; E3 no detectó violaciones de dominio bajo las reglas evaluadas (Q01 es una incidencia de la fuente, tratada en E9); ruidosas con poco historial; last5 muy discreta. `h_`/`a_` son marginalmente similares; `diff_` centradas en 0.
- **Relaciones:** asociaciones con el resultado moderadas (|r| ≤ 0.41), mayores en `diff_` y en season.
- **Last5:** distinta de season fuera de la zona inicial y ≈ 4 veces más responsiva, pero con menor asociación univariada y sin persistencia clara de su desviación.
- **Drift:** se observan cambios de nivel y distribución entre temporadas (pico de 2023/24), compatibles con variación de la liga y de la composición de equipos; E10 no lo demuestra causalmente. TRAIN → VAL tiene un desplazamiento de medias muy pequeño. TEST tiene niveles más bajos y menos dispersos (solo descriptivo).

### Decisiones

- **Cerradas:**
  - **D46:** HADIFF no se usa en lineales no regularizados;
  - **D47:** season = last5 solo en la zona inicial;
  - **D48:** burn-in k = 3;
  - **D49:** Q01 conserva los valores fuente + flag.
- **No se creó ninguna decisión nueva en E11.**

### Abiertos

- **P02:** last5, por valor incremental en modelado.
- **P04:** subconjuntos d = 5 / d = 10.
- **P03:** GD como respuesta OLS, en Matemáticas.
- **P06:** split temporal, protocolo operativo vigente y provisional (TRAIN 2021/22–2023/24, VAL 2024/25, FINAL TEST 2025/26); P06 sigue abierta.
- **P07:** zona horaria.
- **C01–C06:** pendientes de confirmación docente.

### Handoff

- **TRAIN/VAL:** TRAIN y VALIDATION son el único terreno de decisión.
- **TEST:** 2025/26 se reserva para la evaluación final y nunca para seleccionar nada.
- **Reglas que se mantienen:** k = 3; HA y DIFF como representaciones distintas, sin HADIFF completa en lineales no regularizados; subconjunto de features explícito por modelo; escalado ajustado solo en train.
- **Pendientes de resolver en modelado:** P02 (incremental de last5) y P04.
- **Modelos y métricas:** al menos 4 modelos con baseline (requisito docente comunicado; respaldo documental/rúbrica pendiente, C06); métricas multiclase más log loss, Brier y calibración.
- **Benchmark y Q01:** mercado solo como benchmark; Q01 sin corrección.

Detalle completo en el documento 03 y en `e11_modeling_handoff__ALL.csv`.

### Consistencia documental

Estas son menciones de estado anteriores a D46–D49 en documentos formales. Se reportan aquí y **no** se modificaron:
- **`01_arquitectura_y_data_contract.md`:** alineado en la revisión final de E11. Sus dos menciones del burn-in (§14 y tabla de limitaciones) indican ahora `k = 3` aprobado en D48 con P01 cerrada. La ventana last5 sigue descrita como provisional, correctamente (P02).
- **`02_data_pipeline_v0.1.md`:** no se modificó. El Documento 02 conserva deliberadamente el estado histórico del proyecto al cierre del pipeline v0.1 (P01 «provisional», M1/M3 y Q01 como pendientes del EDA); las decisiones posteriores del EDA están documentadas en el Decision Log y en el Documento 03.
- **`docs/Home.md`:** fuera de alcance; no se revisó para modificarlo.
- **Coherentes con el estado actual:** el Data Contract (§5.3, §5.4, §9 alineados con D48), el registro de calidad (Q01 alineado con D49) y el Decision Log.

### Estado

**SCOPE EDA v0.1 — COMPLETE.** E0–E11 consolidadas. No hubo modelado, ningún dataset se reconstruyó y TEST no generó decisiones.

