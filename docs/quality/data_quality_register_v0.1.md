# Registro de calidad de datos — SCOPE Data Contract v0.1

> Estado: aprobado como parte de SCOPE Data Contract v0.1 (2026-10-28). Patch documental 1 aplicado (2026-10-28). Hallazgos Q17–Q19 añadidos el 2026-10-29 (auditoría de CHECKPOINT A).
> Convención de filas: `source_row` es la posición **1-based de la fila de datos** en el CSV RAW (sin contar la cabecera). La línea física del archivo es `source_row + 1`.
> Principio: RAW nunca se corrige. Cada anomalía se documenta aquí y se trata en INTERIM o capas posteriores.

## 1. Catálogo de `dq_flags`

El campo `dq_flags` de CANONICAL es `string` anulable. Contiene uno o más códigos de este catálogo separados por `|`, o vacío si no hay avisos (campo CSV vacío, sin literal). El orden de serialización es el **orden de este catálogo** (`HST_GT_HS`, `AST_GT_AS`, `GOALS_GT_SOT`), sin duplicados. Un código fuera del catálogo, o un conjunto de flags distinto del recalculado por fila, invalida el dataset (V10).

| Código | Condición (por partido) | Severidad | Tratamiento |
|---|---|---|---|
| `HST_GT_HS` | `home_shots_on_target > home_shots` | warning | Se conserva el valor; no se corrige. Ocurrencias actuales: **0** |
| `AST_GT_AS` | `away_shots_on_target > away_shots` | warning | Se conserva el valor; no se corrige. Ocurrencias actuales: **1** |
| `GOALS_GT_SOT` | `home_goals > home_shots_on_target` **o** `away_goals > away_shots_on_target` | info | Plausible por autogoles u omisiones de la fuente. Solo informativo. Ocurrencias actuales: **12** |

Valores esperados totales (referencia para V10): `AST_GT_AS` = 1, `HST_GT_HS` = 0, `GOALS_GT_SOT` = 12.

## 2. Anomalías conocidas

### 2.1 Datos imposibles o sospechosos en los partidos

| ID | Archivo | `source_row` | Partido | Evidencia | Flag | Decisión |
|---|---|---|---|---|---|---|
| Q01 | PL_2021-2022_raw.csv | 9 | 15/08/2021 Newcastle – West Ham | `AS = 8`, `AST = 9` (tiros a puerta mayores que tiros) | `AST_GT_AS` | **Estado: caracterizada en E9 y cerrada mediante D49 (2026-11-01).** El par viola `AST ≤ AS`; RAW conserva los valores de la fuente. **Tratamiento v0.1:** conservar los valores originales de la fuente y el flag `AST_GT_AS`; no se aplica ninguna reparación determinista. **Justificación:** sin verificación externa no puede determinarse si el error está en AS, en AST o en ambos. La propagación observada está localizada en extensión: cinco partidos posteriores de West Ham, tres de ellos elegibles, únicamente en `sot_pg_last5` y `diff_sot_pg_last5`. **Política:** RAW permanece inmutable; cualquier reparación futura deberá ocurrir en una capa derivada, versionada y respaldada por una nueva decisión. Detalle en `reports/eda/eda_report_v0.1.md` (sección E9) y D49 (Decision Log). *Decisión original (2026-10-28), sustituida por D49:* «Conservar sin corregir. Excluir de features que dependan de `away_shots_on_target` solo si el EDA demuestra impacto. Sin otra fuente no puede determinarse el valor correcto» |

### 2.2 Goles mayores que tiros a puerta (`GOALS_GT_SOT`)

| Archivo | `source_row` | Fecha | Partido | Goles (L–V) | Tiros a puerta (L–V) |
|---|---|---|---|---|---|
| 2021-2022 | 15 | 21/08/2021 | Man City – Norwich | 5–0 | 4–0 |
| 2021-2022 | 79 | 17/10/2021 | Newcastle – Tottenham | 2–3 | 1–4 |
| 2021-2022 | 205 | 21/01/2022 | Watford – Norwich | 0–3 | 4–2 |
| 2022-2023 | 106 | 20/10/2022 | Leicester – Leeds | 2–0 | 1–2 |
| 2022-2023 | 319 | 26/04/2023 | Chelsea – Brentford | 0–2 | 4–1 |
| 2023-2024 | 66 | 30/09/2023 | Wolves – Man City | 2–1 | 1–8 |
| 2023-2024 | 91 | 27/10/2023 | Crystal Palace – Tottenham | 1–2 | 3–1 |
| 2023-2024 | 329 | 21/04/2024 | Crystal Palace – West Ham | 5–2 | 7–1 |
| 2024-2025 | 123 | 30/11/2024 | Crystal Palace – Newcastle | 1–1 | 4–0 |
| 2024-2025 | 139 | 05/12/2024 | Fulham – Brighton | 3–1 | 2–3 |
| 2025-2026 | 132 | 02/12/2025 | Fulham – Man City | 4–5 | 6–4 |
| 2025-2026 | 208 | 07/01/2026 | Burnley – Man United | 2–2 | 1–10 |

Decisión: no son errores demostrables (los autogoles cuentan como gol sin ser tiro a puerta propio). Se marcan solo para trazabilidad; no se excluyen.

### 2.3 Texto

| ID | Archivo | `source_row` | Evidencia | Decisión |
|---|---|---|---|---|
| Q02 | PL_2023-2024_raw.csv | 357 | `Referee = "J Gillett "` (espacio final), 06/05/2024. Sin `strip()` cuenta como un árbitro distinto de `J Gillett` | `strip()` en INTERIM. Es la única fila afectada |

### 2.4 Cuotas O/U 2.5 y Asian handicap (verificado contra RAW, 2026-10-29)

Valores comprobados **directamente en los CSV RAW** (lectura independiente) y en INTERIM: en los tres casos INTERIM reproduce RAW exactamente (igualdad numérica; INTERIM serializa `0` → `0.0` y `22` → `22.0` por D43). Son **anomalías de la fuente, no errores del pipeline**.

| ID | Archivo | `source_row` | Partido | Evidencia en RAW | Mercado |
|---|---|---|---|---|---|
| Q17 | PL_2021-2022_raw.csv | 167 | 19/12/2021 Newcastle – Man City | `B365C>2.5 = 0` y `B365C<2.5 = 0` (cuota decimal imposible, ≤ 1.0). En la misma fila `B365>2.5`/`B365<2.5` están vacíos (es el nulo citado en §4); el resto del mercado de cierre es normal (`AvgC>2.5 = 1.37`, `AvgC<2.5 = 3.14`). Es el único valor de cuota ≤ 1.0 en las cinco temporadas | O/U 2.5 (cierre) |
| Q18 | PL_2025-2026_raw.csv | 121–130 | 29/11/2025 a 30/11/2025 (10 partidos consecutivos) | `MaxAHA = 22` en los diez partidos, frente a ~1.8–2.1 de los bookmakers individuales (`B365AHA`, `PAHA`, `BFEAHA`). `AvgAHA` de esas filas también está fuera de rango (4.04–5.19), compatible con un agregado contaminado. Las filas 120 y 131 son normales; `MaxCAHA`/`AvgCAHA` (cierre) del bloque son normales | Asian handicap (pre-closing) |
| Q19 | PL_2025-2026_raw.csv | 312 | 11/04/2026 Brentford – Everton | `MaxAHH = 3.5` frente a `AvgAHH = 2.09`, `B365AHH = 1.83`, `BFEAHH = 1.9` (`PAHH` vacío) | Asian handicap (pre-closing) |

Tratamiento:

- RAW **no se modifica**; INTERIM **conserva los valores originales**.
- Todas las columnas afectadas pertenecen a los mercados **O/U 2.5 o Asian handicap**, que **no pasan a CANONICAL v0.1** (solo pasan `AvgH/AvgD/AvgA` y `AvgCH/AvgCD/AvgCA`, 1X2). Por tanto **no afectan al modelo principal de SCOPE v0.1** ni al benchmark de mercado.
- **No se convierten automáticamente a nulo ni se corrigen** sin evidencia externa.
- No generan `dq_flags`: el catálogo de §1 no contempla anomalías de cuotas.

### 2.5 Formato de archivo y documentación

| ID | Hallazgo | Decisión |
|---|---|---|
| Q03 | BOM UTF-8 presente en 2021-22, 2024-25 y 2025-26; ausente en 2022-23 y 2023-24 | Leer siempre como UTF-8 con BOM tolerado (`utf-8-sig` / `UTF-8-BOM`). INTERIM y capas posteriores se escriben **sin BOM** |
| Q04 | Los cinco archivos usan fin de línea CRLF | Se tolera en lectura; las capas nuevas se escriben con LF |
| Q05 | `notes.txt` documenta `Date` como `dd/mm/yy`; los archivos usan `dd/mm/yyyy` | Parseo estricto con `%d/%m/%Y`; cualquier otro formato es un error. En CANONICAL se serializa como `YYYY-MM-DD` (D28) |
| Q06 | La zona horaria de `Time` no está documentada | Se guarda como hora local sin zona (`kickoff_datetime` sin zona). Decisión de zona pospuesta (ver Decision Log) |
| Q07 | Columnas `BFE>2.5`, `BFE<2.5`, `BFEAHH`, `BFEAHA`, `AHCh` y sus cierres no están en `notes.txt` | Marcadas `inferred_not_documented` en el diccionario. Solo INTERIM; no pasan a CANONICAL |
| Q08 | No existe columna de jornada en ningún archivo | Prohibido inventarla. El orden lo define solo `kickoff_datetime` |

## 3. Cambios de esquema entre temporadas

| Temporada | Columnas | Cambio respecto a la anterior |
|---|---|---|
| 2021-22 | 106 | Base: 88 comunes + IW, WH, VC (pre y cierre) |
| 2022-23 | 106 | Sin cambios |
| 2023-24 | 106 | Sin cambios de esquema (pero `IW*` queda vacío desde 12/01/2024) |
| 2024-25 | 120 | Desaparecen IW y VC. Aparecen BF, 1XB y Betfair Exchange (`BFE*`) |
| 2025-26 | 132 | Desaparecen BF, 1XB y WH. Aparecen BFD, BMGM, BV, CL y LB (pre y cierre) |

Decisión: INTERIM conserva la unión de las 162 columnas; CANONICAL solo usa columnas que existen en las cinco temporadas y están completas (los seis campos `Avg*` y `AvgC*`).

## 4. Disponibilidad de cuotas por bookmaker (huecos)

| ID | Columnas | Temporada | Patrón de nulos | Decisión |
|---|---|---|---|---|
| Q09 | `PS*`, `PSC*`, `P>2.5/P<2.5` (+cierres), `PAHH/PAHA` (+cierres) | 2025-26 | 170 nulos; todos los partidos desde el **17/01/2026 12:30** hasta el final están vacíos (210 partidos previos sí tienen dato) | No usar Pinnacle como serie continua |
| Q10 | `IW*`, `IWC*` | 2023-24 | 182 nulos; todos desde el **12/01/2024** | Solo INTERIM |
| Q11 | `BW*`, `BWC*` | 2024-25 | 141 nulos; todos desde el **12/02/2025** (2023-24: 2 y 12 nulos dispersos) | Solo INTERIM |
| Q12 | `WH*`, `WHC*` | 2024-25 | 91 nulos; todos desde el **01/04/2025** | Solo INTERIM |
| Q13 | `CL*` / `LB*` (y cierres) | 2025-26 | 94–120 nulos **intermitentes** entre 24/01/2026 y 19/05/2026 | Solo INTERIM |
| Q14 | `BFE*`, `BFEC*` | 2024-25 / 2025-26 | 20–22 nulos en un bloque de abril–mayo 2026 (2025-26) y 3 en 2024-25 (O/U) | Solo INTERIM |
| Q15 | `1XB*` | 2024-25 | 9 nulos entre 07/12/2024 y 09/12/2024 | Solo INTERIM |
| Q16 | `BFD*`/`BV*` cierre | 2025-26 | 8 nulos entre 25/04/2026 y 03/05/2026 | Solo INTERIM |

Los campos `Avg*`/`AvgC*` 1X2 no presentan ningún nulo en las cinco temporadas. También están completos `B365*` y `Max*` (1X2). Se eligió `Avg*` por ser el consenso del mercado, no por ser el único completo.

Otras observaciones menores: `B365>2.5`/`B365<2.5` (1 nulo, 2021-22), `AHh` (1 nulo, 2025-26), `MaxCAHH`/`MaxCAHA` (1 nulo, 2023-24), `B365CAHH`/`B365CAHA` (1 nulo, 2021-22). Ninguna se usa en v0.1.

## 5. Observaciones de comportamiento (no son errores)

| Observación | Dato | Implicación |
|---|---|---|
| Calendario irregular | Diferencia máxima de partidos jugados entre equipos: 6 (18/01/2022), 4 (04/03/2023), 3, 2, 2 en las otras temporadas | Usar tasas por partido (política MVP de partidos aplazados), nunca acumulados brutos |
| Parón largo | 42 días sin partidos antes del 26/12/2022 (Mundial) | No afecta al diseño; queda para el EDA de forma |
| Drift de resultados | 2025-26: 104 empates (27.4 %); media de goles 2023-24 = 3.28 | EDA de drift temporal |
| Overround | Media (`Avg`, pre-closing): 1.041 (2021-23), 1.045 (2024-25), **1.058 (2025-26)** | Normalizar overround en la evaluación |
| Favorito del mercado | El porcentaje de partidos ganados por el favorito del mercado disminuye en 2025/26 (49.5 %) respecto a temporadas anteriores (54–59 %) | Su efecto sobre log loss, Brier score y calibración deberá evaluarse posteriormente. No se deriva una dificultad probabilística solo del acierto del favorito |

## 6. Integridad verificada en la auditoría

Sin hallazgos negativos: sin duplicados exactos ni por clave natural; 380 partidos y 20 equipos por temporada; 19 partidos de local y 19 de visitante por equipo; `FTR` coincide con los goles; `HTR` coincide con los goles al descanso; `HT ≤ FT`; sin valores negativos; ningún equipo juega dos veces el mismo día; nombres de equipo consistentes (27 distintos); archivos ordenados cronológicamente.

## 7. Corrección a la auditoría inicial

En el primer informe se afirmó que "solo `Avg*`/`Max*` tienen 0 nulos en las cinco temporadas". La verificación posterior mostró que **también `B365` (1X2) tiene cero nulos**. La decisión de usar `Avg*` como benchmark no cambia, pero se corrige el motivo.

## 8. Cambios del patch 1

- Catálogo de `dq_flags`: se fija el orden de serialización y la representación vacía (D33).
- Q05: se añade el formato CANONICAL de fecha (D28).
- Sección 5: la observación del favorito del mercado pasa a ser neutral (E12); no se infiere dificultad del benchmark a partir del acierto del favorito.
