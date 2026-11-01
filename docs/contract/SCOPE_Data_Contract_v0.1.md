# SCOPE Data Contract v0.1

**Proyecto:** SCOPE — Sports Computational Outcome Prediction Engine
**Alcance:** Premier League (temporadas 2021/22 a 2025/26), fuente Football-Data.co.uk
**Estado:** **FROZEN FOR IMPLEMENTATION** (patch documental 1 aplicado y verificado el 2026-10-28)
**Historial:** patch 1 — ver `../DECISION_LOG.md` D27–D41 y E06–E14; patch 2 (cierre de P08) — D42; patch 3 (serialización de floats con valor entero) — D43; alineación documental con D48 (2026-11-01): burn-in `k = 3` aprobado, sin cambios de reglas, esquema ni datos.
**Documentos hermanos:** `../DECISION_LOG.md`, `../data_dictionary/`, `../quality/`, `../validation/`

> Este contrato define *qué datos existen, qué significan, cuándo están disponibles y qué reglas no pueden violarse*. No contiene código. Distingue **[R]** requisito de rúbrica, **[D]** decisión del equipo y **[P]** propuesta del asesor aprobada.

---

## 1. Principios

1. **RAW es inmutable.** Nunca se modifica, sobrescribe, limpia, elimina ni sustituye. Su integridad se verifica con SHA-256 (`../data_dictionary/raw_manifest_v0.1.csv`, que incluye también `notes.txt`).
2. **Temporalidad estricta.** Para predecir el partido `t` solo se usa información de partidos de liga ya finalizados con `kickoff_datetime` estrictamente anterior (sección 6).
3. **CANONICAL ≠ FEATURES ≠ base de datos relacional.** CANONICAL guarda hechos observados; FEATURES guarda decisiones de modelado; la BD relacional es un diseño normalizado distinto.
4. **MVP pequeño y escalable.** Todo lo que no esté en este contrato queda fuera de v0.1 (sección 13).

## 2. Arquitectura de datos

```
RAW → INTERIM → CANONICAL → team_match_log → FEATURES → MODELS → PREDICTIONS
```

| Capa | Responsabilidad (una frase) |
|---|---|
| **RAW** | Copia inmutable y verificada por SHA-256 de lo que entregó cada fuente. |
| **INTERIM** | Cada temporada parseada, tipada y limpiada superficialmente (BOM, espacios), con la unión de las 162 columnas y trazabilidad por fila, sin descartar información. |
| **CANONICAL** | Un partido por fila con hechos observados estables, nombres SCOPE e integridad validada. |
| **team_match_log** | Artefacto auxiliar con dos filas por partido (perspectiva de cada equipo), ordenado por equipo y `kickoff_datetime`, usado exclusivamente para calcular acumulados y ventanas de forma segura. |
| **FEATURES** | Variables pre-partido versionadas, una fila por partido, unidas a CANONICAL por `match_id`, con targets y elegibilidad. |
| **MODELS** | Artefactos entrenados con sus metadatos (feature subset, split, versión de datos, hiperparámetros, métricas). |
| **PREDICTIONS** | P(H), P(D), P(A) por `match_id` y modelo, junto con el benchmark de mercado evaluado con el mismo protocolo. |

Una fuente complementaria futura (p. ej. la obtenida por web scraping en R) entra por su propia RAW e INTERIM y se integra mediante `team_id` y la clave natural del partido. No se añade ninguna columna hipotética a v0.1.

## 3. Unidad de observación

- **CANONICAL:** una fila = un partido de liga. [D]
- **team_match_log:** una fila = un equipo en un partido (dos por partido). Es un artefacto de cálculo, no una unidad de análisis ni sustituto de CANONICAL. [D]
- **FEATURES:** una fila = un partido (misma granularidad que CANONICAL). [D]

Contenido conceptual de `team_match_log` (el esquema exacto se fija al implementarlo, sin añadir información que no derive de CANONICAL): identificación del partido y del equipo, indicador de localía, `kickoff_datetime`, y los hechos del equipo en ese partido (goles a favor y en contra, puntos obtenidos, tiros a puerta propios).

## 4. CANONICAL v0.1 (42 campos)

Formato de archivo y serialización: ver sección 4.0 (convenciones) y 4.9 (esquema normativo). Las tablas 4.1–4.8 describen el significado; **en caso de discrepancia prevalece 4.9**.
Categorías temporales: **META** metadata · **POST** generado durante/después del partido · **TARGET** variable a explicar o predecir · **MARKET** información de mercado.

### 4.0 Convenciones de serialización (normativas para CANONICAL y FEATURES)

| Aspecto | Regla v0.1 |
|---|---|
| Archivo | CSV, UTF-8 **sin BOM**, separador coma, fin de línea LF (incluida la última línea), una fila de cabecera con los `column_name` exactos y en el orden de 4.9 / 5.4 |
| Comillas | RFC 4180: un campo se entrecomilla solo si contiene coma, comillas o salto de línea; las comillas internas se duplican |
| Orden de filas | `kickoff_datetime` ascendente y, en empate, `match_id` ascendente (solo disposición del archivo; no es frontera temporal, ver T5) |
| **Fecha RAW** | `Date` en RAW es `dd/mm/yyyy` y se parsea con `%d/%m/%Y` (estricto). `Time` en RAW es `HH:MM` |
| **`match_date`** | `YYYY-MM-DD` |
| **`kickoff_time`** | `HH:MM` (24 h, con ceros) |
| **`kickoff_datetime`** | `YYYY-MM-DDTHH:MM:SS`, segundos `00`, **sin zona horaria** en v0.1; igual a `match_date` + `T` + `kickoff_time` + `:00` |
| Verificación de fecha | La transformación RAW → CANONICAL debe comprobar que `Date`/`Time` de RAW se parsearon correctamente (re-parseo estricto) **antes** de serializarlos a ISO (V06) |
| Strings | Sin espacios al inicio o al final; sin saltos de línea; cadena vacía **solo** en campos nullable (cadena vacía = nulo) |
| Enteros | Base 10, sin separadores de miles, sin `+`, sin ceros a la izquierda; negativos con `-` |
| Floats | Punto decimal; **sin redondear** durante la generación; representación decimal más corta que reproduce exactamente el mismo `double` al leerla (p. ej. `1.85`, `0.3333333333333333`); sin separadores de miles. **Valores numéricamente enteros: siempre con parte decimal explícita** (`4.0`, `2.0`, `10.0`; nunca `4`, `2`, `10`), también cuando el texto RAW de origen era `4` (D43). Aplica a toda columna de tipo lógico `float`, incluidas las de INTERIM y las seis `mkt_avg_*` de CANONICAL |
| Booleanos | `true` / `false` (minúsculas) |
| Valores ausentes | Campo CSV **vacío**; nunca el literal `NaN`, `NA`, `NULL` ni `None`. En el modelo lógico se leen como nulo/NaN solo en columnas nullable |
| Categóricas | `H`, `D`, `A` (una letra mayúscula) |
| Tipado en lectura | El lector debe aplicar los tipos lógicos del esquema (dtypes explícitos); en particular `season` y `feature_version` se leen como **string** (nunca como número) |

### 4.1 Identidad y trazabilidad

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `match_id` | string | Derivado | META | ID interno estable de SCOPE | Sección 8; único; no nulo |
| `competition_code` | string | Mapeo desde `Div` | META | Código de competición propio de SCOPE | `E0` → `EPL` |
| `season` | string | Nombre del archivo | META | Temporada | `^\d{4}-\d{4}$` con años consecutivos |
| `source_name` | string | Constante | META | Fuente del registro (corresponde a la columna `source` de `team_mapping`; no es el alias de un equipo) | `football-data.co.uk` |
| `source_file` | string | Nombre de archivo | META | Archivo RAW de origen | Debe existir en el manifiesto |
| `source_row` | int | Posición | META | Fila de datos en RAW (base 1, sin cabecera) | Correspondencia 1:1 con RAW |
| `source_div` | string | `Div` | META | Código original del proveedor | `E0` |

### 4.2 Temporalidad

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `match_date` | date | `Date` | META | Fecha del partido | Derivado de RAW `Date` (parseo estricto `%d/%m/%Y`); serializado `YYYY-MM-DD`; ventana agosto–junio de la temporada |
| `kickoff_time` | time | `Time` | META | Hora de inicio, local, sin zona | `HH:MM`, `00:00`–`23:59` |
| `kickoff_datetime` | datetime sin zona | `Date` + `Time` | META | **Clave de orden y frontera temporal** | `YYYY-MM-DDTHH:MM:SS`, sin zona; = `match_date`+`T`+`kickoff_time`+`:00`; no nulo |
| `match_seq_season` | int | Derivado | META | **Orden determinista auxiliar** dentro de la temporada (1–380) | Ver aviso siguiente |

> **Aviso sobre `match_seq_season`.** Es únicamente un orden determinista auxiliar (rango por `kickoff_datetime`, desempate por `match_id`). Si varios partidos comienzan a la misma hora, el desempate por `match_id` **no implica precedencia temporal real**. **Nunca debe usarse como frontera temporal** para feature engineering. La frontera válida es siempre `kickoff_datetime`. Para features futuras que dependan de partidos de otros equipos se deberá comprobar que esos partidos hayan **finalizado** antes de `t` (regla T10).

### 4.3 Participantes

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `home_team_id`, `away_team_id` | string | `team_mapping_v0.1.csv` | META | Identidad canónica interna (p. ej. `manchester_city`) | `team_id` obtenido del alias RAW exacto de `HomeTeam`/`AwayTeam` vía `(source, source_name)` del mapeo (no basta con que exista); local ≠ visitante |
| `home_team_name`, `away_team_name` | string | `display_name` del mapeo | META | Nombre de presentación | Sin espacios sobrantes. El nombre original queda en RAW/INTERIM |
| `referee` | string | `Referee` | META | Árbitro (no es predictor en v0.1) | `strip()` |

### 4.4 Resultados

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `home_goals`, `away_goals` | int | FTHG, FTAG | POST | Goles finales | Enteros ≥ 0 |
| `ht_home_goals`, `ht_away_goals` | int | HTHG, HTAG | POST | Goles al descanso | 0 ≤ HT ≤ FT |
| `ht_result` | cat {H,D,A} | HTR | POST | Resultado al descanso | = sign(`ht_home_goals` − `ht_away_goals`) |

### 4.5 Estadísticas observadas (todas POST, enteros ≥ 0)

| Campo | Origen | Nota |
|---|---|---|
| `home_shots`, `away_shots` | HS, AS | Tiros |
| `home_shots_on_target`, `away_shots_on_target` | HST, AST | Si superan a los tiros, se marca en `dq_flags`; no se corrige |
| `home_corners`, `away_corners` | HC, AC | |
| `home_fouls`, `away_fouls` | HF, AF | |
| `home_yellow_cards`, `away_yellow_cards` | HY, AY | Según `notes.txt`, las amarillas inglesas no incluyen la primera amarilla de una doble amonestación |
| `home_red_cards`, `away_red_cards` | HR, AR | |

### 4.6 Targets

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `result` | cat {H,D,A} | FTR | TARGET | Target de Machine Learning (clasificación multiclase) | = sign(`goal_difference`) |
| `goal_difference` | int (cuantitativa **discreta**) | Derivado | TARGET | Variable respuesta provisional para la regresión lineal múltiple (Matemáticas) | = `home_goals` − `away_goals` |

### 4.7 Benchmark de mercado (bloque separado; **nunca son features en v0.1**)

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `mkt_avg_pre_home`, `mkt_avg_pre_draw`, `mkt_avg_pre_away` | float | AvgH, AvgD, AvgA | MARKET | Cuota decimal media del mercado, pre-closing: **benchmark principal** | > 1.0; no nula |
| `mkt_avg_close_home`, `mkt_avg_close_draw`, `mkt_avg_close_away` | float | AvgCH, AvgCD, AvgCA | MARKET | Cuota decimal media de cierre: **benchmark secundario** | > 1.0; no nula |

Las probabilidades implícitas (normalización del overround) **no** se almacenan en CANONICAL: dependen del método de normalización y pertenecen a la capa de evaluación. Los bookmakers individuales, `Max*`, O/U y Asian handicap permanecen solo en INTERIM.

### 4.8 Calidad de datos

| Campo | Tipo | Origen | Cat. | Descripción | Regla / validación |
|---|---|---|---|---|---|
| `dq_flags` | string, nullable | Derivado | META | Códigos de aviso separados por `\|` | Solo códigos del catálogo, en orden de catálogo, sin duplicados; campo vacío si no hay avisos (`../quality/data_quality_register_v0.1.md`) |

### 4.9 Esquema normativo de CANONICAL (42 columnas)

Orden exacto de columnas del archivo. Convenciones en 4.0. Todas las columnas son no nulas salvo `dq_flags`.

| position | column_name | logical_type | nullable | allowed / domain | CSV serialization |
|---|---|---|---|---|---|
| 1 | `match_id` | string | no | `{competition_code}_{season}_{YYYYMMDD}_{home_team_id}_{away_team_id}`; único (sección 8) | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 2 | `competition_code` | string | no | `EPL` | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 3 | `season` | string | no | `^\d{4}-\d{4}$`, segundo año = primero + 1 | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 4 | `source_name` | string | no | `football-data.co.uk` (fuente del registro; **no** es un alias de equipo) | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 5 | `source_file` | string | no | nombre de un archivo con `role = raw_data` en el manifiesto | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 6 | `source_row` | int | no | 1–380 (fila de datos en RAW, base 1, sin cabecera) | entero base 10, sin separadores ni `+` |
| 7 | `source_div` | string | no | `E0` | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 8 | `match_date` | date | no | fecha válida del calendario; `YYYY-MM-DD` | `YYYY-MM-DD` |
| 9 | `kickoff_time` | time | no | `00:00`–`23:59`; hora local sin zona | `HH:MM` (24 h, con ceros) |
| 10 | `kickoff_datetime` | datetime | no | = `match_date` + `T` + `kickoff_time` + `:00`; sin zona horaria en v0.1 | `YYYY-MM-DDTHH:MM:SS` (segundos `00`; sin `Z` ni desfase) |
| 11 | `match_seq_season` | int | no | 1–380; único por temporada; **solo orden auxiliar** (T5) | entero base 10, sin separadores ni `+` |
| 12 | `home_team_id` | string | no | `team_id` del alias RAW de `HomeTeam`; `^[a-z0-9_]+$`; congelado en v0.1 | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 13 | `away_team_id` | string | no | `team_id` del alias RAW de `AwayTeam`; ≠ `home_team_id` | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 14 | `home_team_name` | string | no | `display_name` de `home_team_id` | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 15 | `away_team_name` | string | no | `display_name` de `away_team_id` | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 16 | `referee` | string | no | no vacío; sin espacios al inicio/fin (`strip()`) | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 17 | `home_goals` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 18 | `away_goals` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 19 | `ht_home_goals` | int | no | 0 ≤ valor ≤ `home_goals` | entero base 10, sin separadores ni `+` |
| 20 | `ht_away_goals` | int | no | 0 ≤ valor ≤ `away_goals` | entero base 10, sin separadores ni `+` |
| 21 | `ht_result` | categorical | no | `H`/`D`/`A` = signo de `ht_home_goals − ht_away_goals` | una letra mayúscula |
| 22 | `home_shots` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 23 | `away_shots` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 24 | `home_shots_on_target` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 25 | `away_shots_on_target` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 26 | `home_corners` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 27 | `away_corners` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 28 | `home_fouls` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 29 | `away_fouls` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 30 | `home_yellow_cards` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 31 | `away_yellow_cards` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 32 | `home_red_cards` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 33 | `away_red_cards` | int | no | ≥ 0 | entero base 10, sin separadores ni `+` |
| 34 | `result` | categorical | no | `H`/`D`/`A` = signo de `goal_difference` | una letra mayúscula |
| 35 | `goal_difference` | int | no | = `home_goals − away_goals`; puede ser negativo | entero base 10, sin separadores ni `+` (negativo con `-`) |
| 36 | `mkt_avg_pre_home` | float | no | > 1.0 | decimal con punto, valor sin redondear (ver 4.0) |
| 37 | `mkt_avg_pre_draw` | float | no | > 1.0 | decimal con punto, valor sin redondear (ver 4.0) |
| 38 | `mkt_avg_pre_away` | float | no | > 1.0 | decimal con punto, valor sin redondear (ver 4.0) |
| 39 | `mkt_avg_close_home` | float | no | > 1.0 | decimal con punto, valor sin redondear (ver 4.0) |
| 40 | `mkt_avg_close_draw` | float | no | > 1.0 | decimal con punto, valor sin redondear (ver 4.0) |
| 41 | `mkt_avg_close_away` | float | no | > 1.0 | decimal con punto, valor sin redondear (ver 4.0) |
| 42 | `dq_flags` | string | **sí** | vacío, o códigos del catálogo en **orden de catálogo** (`HST_GT_HS`, `AST_GT_AS`, `GOALS_GT_SOT`) separados por `\|`, sin duplicados | campo CSV vacío = sin avisos; nunca `NONE`/`NaN` |

## 5. FEATURES v0.1

Cada fila es un partido. Columnas (30): claves `match_id`, `season`, `kickoff_datetime`; 16 features por equipo (8 × `h_`/`a_`); 7 diferencias; etiquetas `result` y `goal_difference`; control `is_modeling_eligible` y `feature_version` (`"0.1"`).

**Ventanas.** Para un equipo y un partido `t`: la ventana **season** (S) son los partidos de liga del equipo en la misma temporada con `kickoff_datetime` < el de `t`; la ventana **last5** (L5) son los `min(5, n_prev_season)` más recientes de S. Los puntos se calculan 3/1/0 desde la perspectiva del equipo.

### 5.1 Features por equipo (se materializan como `h_<feature>` para el local y `a_<feature>` para el visitante)

| Feature | Definición exacta | Ventana | PRE_MATCH | Uso | Prioridad |
|---|---|---|---|---|---|
| `n_prev_season` | Número de partidos de liga del equipo en S | S | ✓ | Control, elegibilidad, análisis de estabilidad | MVP |
| `ppg_season` | Σ puntos en S / `n_prev_season`; NaN si `n_prev_season` = 0 | S | ✓ | Mat, ML, Comp | MVP |
| `gf_pg_season` | Σ goles a favor en S / `n_prev_season` | S | ✓ | Mat, ML, Comp | MVP |
| `ga_pg_season` | Σ goles en contra en S / `n_prev_season` | S | ✓ | Mat, ML, Comp | MVP |
| `ppg_last5` | Σ puntos en L5 / tamaño de L5 | L5 | ✓ | Mat, ML, Comp | MVP |
| `gf_pg_last5` | Promedio de goles a favor en L5 | L5 | ✓ | ML (Mat según EDA) | MVP |
| `ga_pg_last5` | Promedio de goles en contra en L5 | L5 | ✓ | ML (Mat según EDA) | MVP |
| `sot_pg_last5` | Promedio de tiros a puerta **propios** en L5 (HST cuando jugó de local, AST cuando fue visitante) | L5 | ✓ | Mat, ML, Comp | MVP |

### 5.2 Diferencias

| Feature | Definición exacta | Ventana | PRE_MATCH | Uso | Prioridad |
|---|---|---|---|---|---|
| `diff_x` para x ∈ {`ppg_season`, `gf_pg_season`, `ga_pg_season`, `ppg_last5`, `gf_pg_last5`, `ga_pg_last5`, `sot_pg_last5`} | `h_x − a_x`; NaN si cualquiera de los dos es NaN | S o L5 según x | ✓ | Representación compacta (Mat, ML, Comp) | MVP |

### 5.3 Control

| Campo | Definición |
|---|---|
| `is_modeling_eligible` | `min(h_n_prev_season, a_n_prev_season) ≥ 3` (umbral aprobado `k = 3`, formalizado en D48 tras el EDA E7; P01 cerrada / promovida a D48) |
| `feature_version` | `"0.1"` |

Los valores ausentes de inicio de temporada (NaN en el modelo lógico, **campo vacío** en el CSV) **no se imputan**. Las filas no elegibles permanecen en FEATURES y se excluyen del modelado mediante `is_modeling_eligible`. CANONICAL conserva los 1,900 partidos.

### 5.4 Esquema normativo de FEATURES (30 columnas)

Orden exacto de columnas del archivo. Convenciones en 4.0. Un valor ausente es un campo CSV vacío (nunca `NaN`). Los floats **no se redondean** al generar el archivo.

| position | column_name | logical_type | nullable | allowed / domain | CSV serialization |
|---|---|---|---|---|---|
| 1 | `match_id` | string | no | existe en CANONICAL; único | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 2 | `season` | string | no | `^\d{4}-\d{4}$` | texto UTF-8 tal cual, sin comillas salvo necesidad CSV |
| 3 | `kickoff_datetime` | datetime | no | igual al de CANONICAL | `YYYY-MM-DDTHH:MM:SS` |
| 4 | `h_n_prev_season` | int | no | 0–37 | entero base 10, sin separadores ni `+` |
| 5 | `h_ppg_season` | float | **sí** | [0, 3]; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 6 | `h_gf_pg_season` | float | **sí** | ≥ 0; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 7 | `h_ga_pg_season` | float | **sí** | ≥ 0; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 8 | `h_ppg_last5` | float | **sí** | [0, 3]; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 9 | `h_gf_pg_last5` | float | **sí** | ≥ 0; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 10 | `h_ga_pg_last5` | float | **sí** | ≥ 0; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 11 | `h_sot_pg_last5` | float | **sí** | ≥ 0; vacío solo si `h_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 12 | `a_n_prev_season` | int | no | 0–37 | entero base 10, sin separadores ni `+` |
| 13 | `a_ppg_season` | float | **sí** | [0, 3]; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 14 | `a_gf_pg_season` | float | **sí** | ≥ 0; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 15 | `a_ga_pg_season` | float | **sí** | ≥ 0; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 16 | `a_ppg_last5` | float | **sí** | [0, 3]; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 17 | `a_gf_pg_last5` | float | **sí** | ≥ 0; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 18 | `a_ga_pg_last5` | float | **sí** | ≥ 0; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 19 | `a_sot_pg_last5` | float | **sí** | ≥ 0; vacío solo si `a_n_prev_season` = 0 | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 20 | `diff_ppg_season` | float | **sí** | = `h_ppg_season − a_ppg_season`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 21 | `diff_gf_pg_season` | float | **sí** | = `h_gf_pg_season − a_gf_pg_season`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 22 | `diff_ga_pg_season` | float | **sí** | = `h_ga_pg_season − a_ga_pg_season`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 23 | `diff_ppg_last5` | float | **sí** | = `h_ppg_last5 − a_ppg_last5`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 24 | `diff_gf_pg_last5` | float | **sí** | = `h_gf_pg_last5 − a_gf_pg_last5`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 25 | `diff_ga_pg_last5` | float | **sí** | = `h_ga_pg_last5 − a_ga_pg_last5`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 26 | `diff_sot_pg_last5` | float | **sí** | = `h_sot_pg_last5 − a_sot_pg_last5`; vacío si cualquiera de los dos es vacío | decimal con punto, valor sin redondear (ver 4.0); ausente = campo vacío |
| 27 | `result` | categorical | no | `H`/`D`/`A`; igual a CANONICAL | una letra mayúscula |
| 28 | `goal_difference` | int | no | igual a CANONICAL | entero base 10, sin separadores ni `+` (negativo con `-`) |
| 29 | `is_modeling_eligible` | bool | no | = (`min(h_n_prev_season, a_n_prev_season)` ≥ 3) con umbral aprobado `k = 3` (D48; P01 cerrada / promovida a D48) | `true` / `false` (minúsculas) |
| 30 | `feature_version` | string | no | exactamente `0.1` (cadena de 3 caracteres) | texto `0.1`; **el lector debe declararlo string** (no float) |

## 6. Reglas temporales (T1–T10) — la implementación NO puede violarlas

| ID | Regla |
|---|---|
| **T1** | Las features de un partido `t` solo pueden usar partidos `m′` con `kickoff_datetime(m′) < kickoff_datetime(t)`. La desigualdad es **estricta**. |
| **T2** | En v0.1 solo cuentan partidos de liga de la misma competición. |
| **T3** | En v0.1 solo cuentan partidos de la misma temporada (reinicio por temporada). |
| **T4** | Ningún campo POST, TARGET o MARKET del partido `t` puede usarse en sus propias features. |
| **T5** | El orden temporal lo define únicamente `kickoff_datetime`. Nunca el orden de las filas, la jornada, `source_row` ni `match_seq_season`. |
| **T6** | Todo acumulado o ventana se calcula sobre `team_match_log`, con desplazamiento equivalente a `shift(1)` por equipo y temporada; el resultado se reconstruye a una fila por partido mediante `match_id`. |
| **T7** | Las cuotas no son features en v0.1; solo son benchmark. |
| **T8** | Todo ajuste (scaler, selección de features, hiperparámetros) usa solo datos de entrenamiento. La validación principal es temporal, nunca aleatoria. |
| **T9** | Prohibido usar como feature cualquier agregado de temporada completa o posterior a `t`. |
| **T10** | Si una feature futura usa partidos de **otros** equipos, la condición pasa a ser "partido **finalizado** antes de `kickoff_datetime(t)"; haber *comenzado* antes no basta. |

Garantía principal: **modificar el resultado o las estadísticas del partido `t` no debe modificar ninguna feature utilizada para predecir `t`**; solo puede afectar a features de partidos posteriores (prueba V14).

**Ejemplo conceptual.** Arsenal recibe al Chelsea el 20/10 y es su 9.º partido de liga. `h_ppg_season` usa los partidos 1–8 del Arsenal; el resultado del 20/10 no entra. Si el Chelsea tiene un aplazado y solo ha jugado 7, su `a_ppg_season` usa esos 7 (por eso se emplean tasas por partido). `h_sot_pg_last5` promedia los tiros a puerta propios del Arsenal en sus partidos 4–8. Los tiros del propio 20/10 solo aparecerán en las features de su 10.º partido.

### 6.1 Hipótesis operativa de v0.1: historial del mismo equipo

En v0.1 las features usan **exclusivamente el historial del mismo equipo** dentro de la Premier League. Hipótesis operativa:

- ningún equipo tiene dos partidos de liga simultáneos;
- para este conjunto histórico, `kickoff_datetime(m′) < kickoff_datetime(t)` es **suficiente** para ordenar el historial propio del equipo.

Si aparecen partidos suspendidos, abandonados o incompatibles con esta hipótesis (p. ej. un equipo con dos partidos en el mismo día o con el mismo `kickoff_datetime`), deben **detectarse y bloquear la validación o documentarse** explícitamente (V06). T10 se mantiene: cuando una feature futura dependa de partidos de **otros** equipos, no bastará con que hayan comenzado antes de `t`; deberán haber **finalizado** antes de `t`.

### 6.2 Protocolo temporal de evaluación (conceptual)

Para SCOPE v0.1 se adopta una **evaluación histórica secuencial (walk-forward) sobre las features**. Para cada partido `t`:

- las features se calculan únicamente con partidos disponibles antes de `t`;
- una vez ocurrido un partido histórico, su resultado puede formar parte legítimamente de las features de partidos posteriores;
- nunca se usan resultados futuros respecto a `t`.

Por tanto, durante una temporada de validación o prueba las features pueden actualizarse cronológicamente con resultados ya conocidos. Esto **no** implica reentrenar automáticamente el modelo tras cada partido. El protocolo de reentrenamiento, su frecuencia y la calibración se decidirán en la etapa de modelado y **no se definen aquí**.

**Disciplina sobre 2025/26 (política definitiva, D42).** 2025/26 se mantiene como test final de v0.1, pero **no es un test completamente ciego**: algunas estadísticas descriptivas agregadas de 2025/26 fueron observadas antes de congelar esta política.

- **Permitido:** EDA descriptivo global con fines de documentación (distribución H/D/A por temporada, goles, distribución general de variables, valores faltantes, características del mercado, drift temporal descriptivo).
- **Prohibido:** usar cualquier observación, patrón o resultado de 2025/26 para seleccionar o eliminar features, modificar reglas de feature engineering, elegir el burn-in, escoger modelos, ajustar hiperparámetros, seleccionar transformaciones o thresholds, ajustar calibración, cambiar el protocolo de entrenamiento o modificar decisiones metodológicas con el objetivo de mejorar resultados sobre 2025/26.
- El EDA usado para desarrollar y seleccionar features o tomar decisiones de modelado utiliza **solo datos de desarrollo (2021/22–2024/25)**, no el test final.
- El split exacto sigue siendo provisional hasta la etapa de modelado (propuesta actual: Train 2021/22–2023/24, Validation 2024/25, Test 2025/26; Decision Log P06).

## 7. Reglas de multicolinealidad (M1–M4)

| ID | Regla |
|---|---|
| **M1** | `diff_x = h_x − a_x` exactamente. En una regresión lineal que deba evitar multicolinealidad perfecta **nunca** deben entrar juntas `h_x`, `a_x` y `diff_x`; hay que elegir entre la representación pareada o la de diferencias. El feature store puede conservar las tres porque modelos distintos usan representaciones distintas. |
| **M2** | No se almacena `gd_pg` (diferencia de goles por partido): es exactamente `gf_pg − ga_pg`. Si se deriva, no puede convivir con `gf_pg` y `ga_pg` en un modelo lineal. |
| **M3** | Mientras `n_prev_season ≤ 5`, cada feature last5 es **idéntica** a su versión de temporada (L5 = S). La correlación entre ambas familias estará inflada en esas filas; el EDA debe medirla (VIF, estratificando por `n_prev_season`). Puede justificar conservar una sola familia. |
| **M4** | Cada modelo declara un **feature subset** explícito en MODELS. Para la regresión lineal de Matemáticas, el subset debe evitar combinaciones linealmente dependientes. |

## 8. Identificador de partido

Se separan dos conceptos:

- **Clave natural** (se valida como única): `(competition_code, season, match_date, home_team_id, away_team_id)`. Incluir la fecha evita depender de que cada pareja local/visitante se enfrente una sola vez por temporada (copas, playoffs, otras ligas).
- **`match_id`** interno de SCOPE, determinista, construido desde la clave natural:

```
{competition_code}_{season}_{YYYYMMDD}_{home_team_id}_{away_team_id}
ejemplo: EPL_2021-2022_20210813_brentford_arsenal
```

Propiedades: legible, reproducible, independiente del orden de filas, sin contadores, hashes ni registro central. Si en el futuro un deporte admite dos partidos entre los mismos equipos el mismo día, se añade `HHMM` al formato; no es necesario ahora. En la base de datos relacional se podrá añadir una clave primaria entera subrogada con `match_id` como columna `UNIQUE`; es una decisión del diseño de BD, no de este contrato.

Limitación documentada: el ID depende de la fecha en que se jugó. Para datos históricos es estable. Al predecir partidos futuros (p. ej. 2026/27), un aplazamiento cambiaría el ID; eso exigirá un registro de fixtures con ID asignado la primera vez que se ve el partido. **Fuera de v0.1.**

**Identidad de equipos.** `team_id` es la identidad canónica interna (no deriva de abreviaturas de ninguna fuente). El mapeo `source_name → team_id → display_name` está en `../data_dictionary/team_mapping_v0.1.csv` con **una fila por alias** (`source`, `source_name`, `team_id`, `display_name`). Para incorporar otra fuente basta añadir filas con otro `source` y el mismo `team_id`; **los 27 `team_id` actuales quedan congelados para v0.1**. Una fuente nueva debe añadir aliases a un `team_id` existente; un `team_id` ya usado en un `match_id` no se modifica, y si en una versión futura fuera absolutamente necesario cambiarlo se tratará como una **migración explícita y versionada**.

**Semántica de `source_name` (dos significados distintos).** En CANONICAL, `source_name` = `football-data.co.uk` (la fuente del registro). En `team_mapping`, `source` = `football-data.co.uk` y `source_name` = el **alias original del equipo** (p. ej. `Man City`). La relación verificable es `(fuente, alias RAW) → team_id → display_name`: `CANONICAL.source_name == team_mapping.source` y `RAW.HomeTeam`/`RAW.AwayTeam == team_mapping.source_name` (V07).

## 9. Políticas MVP

| Tema | Política v0.1 |
|---|---|
| Burn-in | `is_modeling_eligible` con umbral aprobado `k = 3`: mínimo de 3 partidos previos por equipo (D48, tras el EDA E7; P01 cerrada / promovida a D48). Con ese umbral hay 1,749 filas elegibles de 1,900. Se conserva `n_prev_season` para comparar 3 vs 5 u otros valores sin reconstruir CANONICAL. |
| Nueva temporada | Se reinician: puntos, PPG, goles acumulados, tasas de goles, forma reciente, ventanas móviles y estadísticas históricas de temporada. No se usa información de la temporada anterior. |
| Equipos ascendidos | Empiezan sin historia, igual que todos los equipos, por el reinicio. No se usa información externa (Championship, Elo) en v0.1. |
| Partidos aplazados | Se usa solo la fecha real en que se jugó (`kickoff_datetime`). No se asume que la jornada represente el orden efectivo. Se usan tasas por partido porque la diferencia de partidos jugados entre equipos llega a 6 en el conjunto. |
| Nulos iniciales | Si `n_prev_season = 0`, las features de tasa y ventana son NaN y **no se imputan**. Las filas no elegibles se excluyen del modelado, no de CANONICAL. |
| Nombres de equipo | Mapeo explícito; ningún nombre sin mapear (V07). |
| Valores faltantes en RAW | No hay nulos en resultados ni estadísticas. Los nulos de bookmakers individuales no afectan: `Avg*` está completo y es el único bloque de mercado que pasa a CANONICAL. |
| Diferencias de esquema | INTERIM conserva la unión de las 162 columnas; CANONICAL usa solo campos presentes y completos en las cinco temporadas. |
| Cuotas | Estrategia C (sección 10). |
| Datos externos | Ninguno en v0.1. |
| Deducciones de puntos | Los puntos son "deportivos" (derivados de resultados) y pueden diferir de la tabla oficial. No afecta a v0.1 (no hay posición en tabla). |

## 10. Tratamiento de cuotas (Estrategia C)

- **Modelo SCOPE:** usa únicamente features deportivas históricas.
- **Mercado:** benchmark probabilístico externo. Las cuotas **no** son predictores del modelo principal v0.1.
- **Pregunta guía:** ¿qué tan cerca está un modelo basado exclusivamente en información deportiva histórica del consenso probabilístico del mercado?
- **Benchmark principal:** `AvgH/AvgD/AvgA` (pre-closing). **Secundario:** `AvgCH/AvgCD/AvgCA` (cierre; documentado por la regla de la `C` de `notes.txt`; la hora exacta de captura de las cuotas de cierre no está documentada).
- **Conversión a probabilidades (normalización proporcional del overround), en la capa de evaluación, no en CANONICAL.** Para las tres cuotas decimales `o_H`, `o_D`, `o_A`: primero `q_i = 1 / o_i`; después `p_i = q_i / Σ_j q_j`, es decir `p_i = (1/o_i) / [(1/o_H) + (1/o_D) + (1/o_A)]`. Debe cumplirse `P(H) + P(D) + P(A) = 1` con tolerancia numérica `1e-9`.
- **Mismo conjunto de partidos:** cuando se comparen, el modelo y el benchmark de mercado se evalúan sobre **exactamente el mismo conjunto de partidos elegibles**.
- **Sin equivalencia temporal supuesta:** no se afirma que las cuotas de cierre contengan exactamente la misma información temporal que las predicciones de SCOPE (la hora de captura de las cuotas de cierre no está documentada).
- La convención exacta de Brier multiclase, el *clipping* de probabilidades y demás detalles de evaluación se definirán en la etapa de ML.
- Los datos deportivos y de mercado son bloques conceptualmente distintos dentro de CANONICAL (secciones 4.4–4.6 frente a 4.7); en el futuro `Odds` podrá separarse como entidad propia.

## 11. Targets

- **`result`** ∈ {H, D, A}: clasificación multiclase (ML). El objetivo eventual son probabilidades P(H), P(D), P(A).
- **`goal_difference`** = `home_goals − away_goals`: variable **cuantitativa discreta** (toma valores enteros). Se mantiene provisionalmente como respuesta de la regresión lineal múltiple OLS de Matemáticas con fines analíticos y académicos, evaluando explícitamente las limitaciones del modelo y sus supuestos (normalidad, independencia por equipos repetidos y dependencia temporal). Es interpretable, se relaciona con H/D/A y permite predictores pre-partido sin construir un modelo casi tautológico con estadísticas del mismo partido. Un R² bajo no se interpreta automáticamente como fracaso.
- **Poisson** solo se analiza para conteos no negativos (`home_goals`, `away_goals`, `total_goals`); no para `goal_difference`. La relación con la distribución Skellam es solo una línea futura.

## 12. Compatibilidad académica

No se inventan requisitos desconocidos; lo no disponible figura en el Decision Log (sección 3).

- **Matemáticas [R]:** datos tidy (una observación por fila, una variable por columna); `lm()` con predictores pre-partido; matriz de correlación y exclusión de multicolinealidad (M1–M4); análisis de residuos. El requisito de web scraping desde R **no está cubierto por este contrato** y queda pendiente (Decision Log C01–C03).
- **Machine Learning:** clasificación H/D/A con validación temporal; probabilidades para log loss, Brier score y calibración; benchmark de mercado. Rúbrica no disponible.
- **Complejidad Computacional [R]:** KNN y regresión logística a mano, sin IA, a cargo del estudiante; mediciones de tiempo con la base del proyecto; comparación con una librería de código abierto. Subconjuntos propuestos (todas numéricas, sin encoding; estandarización ajustada solo con train):
  - **`d = 5`:** `diff_ppg_season`, `diff_gf_pg_season`, `diff_ga_pg_season`, `diff_ppg_last5`, `diff_sot_pg_last5`. Representación **comprimida basada en diferencias**.
  - **`d = 10`:** versiones separadas `h_*` y `a_*` de esas mismas cinco métricas. **Conserva los niveles absolutos** de local y visitante.
  - Ambas representaciones están conceptualmente relacionadas, pero **no contienen la misma información**: `diff_x = h_x − a_x` pierde los niveles absolutos. Por tanto, si el rendimiento predictivo cambia entre ambas, **no puede atribuirse exclusivamente al cambio de dimensionalidad**. Aun así, ambas sirven para estudiar experimentalmente el coste computacional asociado a `d`.
  - `n` ≈ 1,749 observaciones elegibles (umbral 3). Si hace falta variar `n`, hay que confirmarlo con el docente (C05).
- **Bases de Datos:** conceptos naturales (no es el esquema SQL): `Team` (`team_id`, nombre canónico, aliases por fuente); `Season`; `Match` (`match_id`, temporada, equipos, kickoff, árbitro, resultado, goles); `MatchStatistics` (estadísticas por lado); `Odds` (partido, bookmaker/agregado, mercado, momento pre-closing o cierre, cuota); `Model` (versión, algoritmo, subset, datos, métricas); `Prediction` (partido, modelo, P(H), P(D), P(A), fecha). **CANONICAL ≠ modelo relacional.** La plantilla de reporte disponible pide fuente, formato, tipos, relaciones y flujo de datos.
- **Probabilidad y Estadística, Java:** sin rúbrica disponible. CANONICAL provee entidades y variables claras (goles como conteos, probabilidades implícitas, equipos/partidos) sin asumir requisitos.

## 13. Elementos deliberadamente fuera de v0.1

- **Features y modelado:** Elo; posición en tabla; H2H; ventana de 10 partidos; rendimiento separado local/visitante; días de descanso; efecto del árbitro; memoria entre temporadas; Skellam.
- **Mercado:** cuotas como predictores (Estrategia B); mercados O/U y Asian handicap; bookmakers individuales en CANONICAL; value betting.
- **Datos externos:** xG; lesiones; alineaciones; Championship; la fuente del scraping (aún no elegida); deducciones de puntos.
- **Alcance:** temporada 2026/27 y registro de fixtures futuros; otras ligas, copas y deportes; zona horaria explícita; formato Parquet.
- **Sistemas:** esquema SQL completo; APIs; automatización; despliegue.

## 14. Índice de documentos de referencia

| Documento | Ruta (dentro de `SCOPE/docs/`) |
|---|---|
| Este contrato | `contract/SCOPE_Data_Contract_v0.1.md` |
| Manifiesto RAW (SHA-256) | `data_dictionary/raw_manifest_v0.1.csv` |
| Diccionario RAW | `data_dictionary/raw_dictionary_v0.1.csv` y `.md` |
| Mapeo de equipos | `data_dictionary/team_mapping_v0.1.csv` |
| Registro de calidad | `quality/data_quality_register_v0.1.md` |
| Especificación de validaciones | `validation/validation_spec_v0.1.md` |
| Decision Log | `DECISION_LOG.md` |
| Documentación oficial de la fuente (`notes.txt`) | `../Documentacion de datos/notes.txt` (relativa a `docs/`; es `Documentacion de datos/notes.txt` desde la raíz de `SCOPE/`; incluida en el manifiesto) |

Todas las rutas `relative_path` del manifiesto se interpretan **desde la raíz de `SCOPE/`**. Los archivos `.xlsx` existentes son copias auxiliares de inspección manual y no son fuente de verdad.
