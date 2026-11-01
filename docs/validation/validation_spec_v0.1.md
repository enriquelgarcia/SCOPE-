# Especificación de validaciones — SCOPE Data Contract v0.1

> Criterios de aceptación. **Un dataset generado solo es válido si pasan todas las pruebas bloqueantes.** Este documento no contiene código; la implementación se hará después de congelar el contrato.
> Severidad: **BLOQ** = bloquea (el dataset no es válido); **AVISO** = se registra pero no bloquea.

## 1. Reglas generales

- Cada prueba tiene un ID estable (`V01`–`V17`). Un informe de validación debe listar cada ID con `PASS` / `FAIL` y el detalle de fallos.
- Las pruebas de CANONICAL y FEATURES se ejecutan sobre archivos **generados**; RAW solo se lee.
- Una nueva versión del contrato puede añadir pruebas, pero no eliminarlas sin quedar registrado en el Decision Log.

## 2. Pruebas

### RAW

| ID | Capa | Prueba | Criterio de aceptación | Sev. |
|---|---|---|---|---|
| V01 | RAW | Integridad por SHA-256 | El SHA-256 de **cada archivo del manifiesto** (los 5 CSV con `role = raw_data` y `notes.txt`) coincide con `raw_manifest_v0.1.csv` **antes y después** de ejecutar cualquier proceso; en los CSV coinciden además filas, columnas, BOM, fecha mínima y fecha máxima. Hay exactamente 5 filas `raw_data`. Los `relative_path` se resuelven desde la raíz de `SCOPE/` | BLOQ |

### CANONICAL

| ID | Capa | Prueba | Criterio de aceptación | Sev. |
|---|---|---|---|---|
| V02 | CANONICAL | Esquema normativo | Se cumple el esquema de contrato 4.9 **completo**: cabecera exacta con las 42 columnas en el orden indicado; cada columna respeta tipo lógico, nulabilidad, dominio y serialización de 4.0/4.9 (fechas `YYYY-MM-DD`, datetime `YYYY-MM-DDTHH:MM:SS`, enteros, floats sin redondear, vacío = ausente); sin literales `NaN`/`NA`/`NULL`/`None`; UTF-8 sin BOM y LF; filas ordenadas por (`kickoff_datetime`, `match_id`); **idempotencia**: leer con los tipos del esquema y reserializar produce un archivo idéntico byte a byte | BLOQ |
| V03 | CANONICAL | Trazabilidad completa | Cada fila tiene un `(source_file, source_row)` existente (archivo `raw_data` del manifiesto); correspondencia 1:1 sin filas repetidas ni omitidas. Para cada fila se **recarga la fila RAW de forma independiente** y se compara campo por campo, aplicando solo las transformaciones documentadas: `Div`→`source_div` (y `competition_code` por mapeo); temporada derivada del nombre del archivo; `Date`→`match_date` y `Time`→`kickoff_time` (re-parseo estricto, ver V06); `HomeTeam`/`AwayTeam`→ids y nombres (ver V07); `Referee`→`referee` (`strip()`); `FTHG`, `FTAG`, `FTR`, `HTHG`, `HTAG`, `HTR`; `HS/AS`, `HST/AST`, `HF/AF`, `HC/AC`, `HY/AY`, `HR/AR`; `AvgH/AvgD/AvgA`→`mkt_avg_pre_*`; `AvgCH/AvgCD/AvgCA`→`mkt_avg_close_*` (igualdad numérica exacta del valor parseado). **Autoprueba:** en una copia en memoria, intercambiar cuotas o estadísticas entre dos partidos (valores válidos y dentro de rango) debe hacer fallar V03 | BLOQ |
| V04 | CANONICAL | Unicidad | `match_id` único; la clave natural `(competition_code, season, match_date, home_team_id, away_team_id)` única; `match_id` coincide con la regla de construcción | BLOQ |
| V05 | CANONICAL | Conteos y calendario | Total 1,900 filas; por temporada: 380 partidos, 20 equipos, 19 partidos de local y 19 de visitante por equipo, **y cada pareja ordenada `(home_team_id, away_team_id)` con local ≠ visitante aparece exactamente una vez** (380 = 20 × 19; el conjunto de parejas es el producto completo sin la diagonal). Así un calendario con un enfrentamiento duplicado y otro omitido no pasa los conteos | BLOQ |
| V06 | CANONICAL | Fechas y orden temporal | **Formato CANONICAL:** `match_date` cumple `YYYY-MM-DD` y es una fecha válida; `kickoff_time` cumple `HH:MM` (`00:00`–`23:59`); `kickoff_datetime` cumple `YYYY-MM-DDTHH:MM:SS` sin zona horaria y **es exactamente `match_date` + `T` + `kickoff_time` + `:00`**. **Fecha RAW:** `Date` de RAW se re-parsea de forma estricta con `%d/%m/%Y` (y `Time` con `%H:%M`) y su serialización ISO coincide con el valor CANONICAL antes de aceptarse (detecta confusión día/mes). **Calendario:** cada fecha dentro de agosto–junio de su temporada; `match_seq_season` es 1–380 sin huecos ni repeticiones y es consistente con el orden por `kickoff_datetime`; ningún equipo tiene dos partidos con el mismo `kickoff_datetime` ni el mismo día (hipótesis operativa del contrato 6.1: cualquier violación bloquea o debe documentarse explícitamente) | BLOQ |
| V07 | CANONICAL | Equipos y mapeo | Para cada fila, `CANONICAL.source_name == team_mapping.source` y el `(source, alias)` con `alias` = `HomeTeam`/`AwayTeam` de la fila RAW citada (V03) existe en `team_mapping_v0.1.csv`. Entonces: `home_team_id` es **exactamente** el `team_id` de ese alias de `HomeTeam`; `away_team_id` es exactamente el de `AwayTeam`; `home_team_name`/`away_team_name` son el `display_name` de esos IDs. No basta con que el `team_id` exista en el catálogo (permitiría intercambiar IDs entre equipos). Además: `home_team_id ≠ away_team_id`; 27 `team_id` distintos en el conjunto; los 27 `team_id` coinciden con los congelados en v0.1 | BLOQ |
| V08 | CANONICAL | Rangos | Goles y estadísticas son enteros ≥ 0; `ht_* ≤ final` (goles); `mkt_*` son decimales > 1.0 y no nulos; `ht_result` coincide con el signo de la diferencia de goles al descanso; sin nulos en resultados ni estadísticas | BLOQ |
| V09 | CANONICAL | Targets | `goal_difference == home_goals − away_goals` y `result == sign(goal_difference)` (H/D/A) en todas las filas | BLOQ |
| V10 | CANONICAL | Calidad (`dq_flags`) por fila | **Se recalcula el conjunto esperado de flags de cada fila** a partir de sus valores (`HST_GT_HS`: `home_shots_on_target > home_shots`; `AST_GT_AS`: `away_shots_on_target > away_shots`; `GOALS_GT_SOT`: `home_goals > home_shots_on_target` o `away_goals > away_shots_on_target`) y debe coincidir **exactamente** con `dq_flags`: (1) conjunto exacto por fila; (2) sin flags incorrectos; (3) sin duplicados; (4) solo códigos del catálogo; (5) serialización determinista en orden de catálogo, separados por `\|`; (6) sin flags = campo vacío. **Después**, como comprobación adicional: conteos globales `AST_GT_AS` = 1 (2021-22, `source_row` 9), `HST_GT_HS` = 0, `GOALS_GT_SOT` = 12 y las localizaciones del registro de calidad | BLOQ |

### FEATURES

| ID | Capa | Prueba | Criterio de aceptación | Sev. |
|---|---|---|---|---|
| V11 | FEATURES | Integridad referencial | Mismo número de filas que CANONICAL; cada `match_id` existe en CANONICAL y es único; `result` y `goal_difference` iguales a los de CANONICAL | BLOQ |
| V12 | FEATURES | Reinicio de temporada | `n_prev_season = 0` en el primer partido de cada equipo en cada temporada y crece exactamente de 1 en 1 en sus partidos siguientes (ordenados por `kickoff_datetime`), con máximo 37. Features de tasa/ventana son NaN cuando `n_prev_season = 0` | BLOQ |
| V13 | FEATURES | Elegibilidad | `is_modeling_eligible == (min(h_n_prev_season, a_n_prev_season) ≥ umbral)`; las filas elegibles no contienen **valores vacíos** en ninguna feature. Con umbral 3 se esperan 350, 350, 349, 350 y 350 filas elegibles por temporada (1,749 en total); un cambio de umbral debe cambiar este conteo de forma coherente | BLOQ |
| V14 | FEATURES | Test de perturbación (leakage) con controles | Se altera de forma **internamente coherente** un partido histórico `t` y se recalculan las features. Principio: la perturbación debe modificar de manera coherente suficientes hechos POST del partido para que exista una propagación observable hacia las features históricas posteriores, manteniendo al mismo tiempo una fila válida conforme al esquema y las validaciones de CANONICAL (V02/V08/V09/V10). Perturbación implementada y aprobada (D45): se modifican los **goles finales** para invertir el ganador (si gana el local, pasa a ganar el visitante, y viceversa) o romper el empate a favor de uno de los equipos; se suma `+1` a los tiros y a los tiros a puerta de **ambos** equipos (`home_shots`, `away_shots`, `home_shots_on_target`, `away_shots_on_target`); se recalculan coherentemente `goal_difference`, `result` y `dq_flags`. Los campos `ht_*` (`ht_home_goals`, `ht_away_goals`, `ht_result`) **no se modifican**, siempre que sigan satisfaciendo V08/V09 y la coherencia con los goles finales (la perturbación solo aumenta goles finales, por lo que `ht_* ≤ final` se conserva). **Controles negativos (deben permanecer invariantes):** todas las features del propio `t`; las features de equipos no involucrados; las features de otras temporadas. **Control positivo (debe cambiar):** al menos una feature posterior que dependa directamente de los valores alterados, para los equipos involucrados, cuando exista un partido posterior dentro de la ventana afectada (ventana season, y ventana last5 si `t` cae en ella). Se ejecuta sobre una muestra reproducible de 100 partidos (semilla `42`) más los partidos con anomalías conocidas; el informe documenta cuántos controles positivos fueron aplicables. Si el control positivo no cambia donde debía cambiar, la prueba no detecta nada y es FAIL | BLOQ |
| V15 | FEATURES | Test oráculo | Se construye primero un **conjunto obligatorio** que cubre: (a) los primeros 5 partidos de cada equipo-temporada; (b) partidos alrededor de aplazamientos (proxy operativo: partidos con `\|h_n_prev_season − a_n_prev_season\| ≥ 2` y los dos partidos anterior y posterior, por kickoff, de cada equipo implicado); (c) partidos con kickoff simultáneo (mismo `kickoff_datetime` que otro partido de la temporada); (d) anomalías conocidas (filas con `dq_flags` y la fila de `J Gillett `); (e) comienzos y finales de temporada (`match_seq_season` 1–10 y 371–380). Después se añade una **muestra aleatoria reproducible** de 100 partidos con semilla fija `42`. Se recalcula cada feature con un procedimiento **independiente** del cálculo principal (filtrado explícito `kickoff < t` sobre CANONICAL, sin reutilizar `team_match_log`, `shift` ni funciones rolling) y los valores coinciden (tolerancia 1e-9). El informe de validación debe **documentar el tamaño final** de cada subconjunto y del total evaluado | BLOQ |
| V16 | FEATURES | Identidad de diferencias | `diff_x == h_x − a_x` en todas las filas (NaN donde cualquiera sea NaN) para las 7 métricas definidas; `feature_version = "0.1"` | BLOQ |
| V17 | FEATURES | Esquema normativo | Se cumple el esquema de contrato 5.4 **completo**: cabecera exacta con las 30 columnas en el orden indicado; tipos lógicos, nulabilidad y dominios (`n_prev_season` entero 0–37 no vacío; `ppg_*` en [0, 3]; `is_modeling_eligible` `true`/`false`; `feature_version` **string** exactamente `0.1`, leído con dtype string); valores ausentes como campo vacío (nunca `NaN`); floats sin redondear y con ida y vuelta exacta (parsear y reserializar da la misma cadena); UTF-8 sin BOM y LF; filas en el mismo orden que CANONICAL; **idempotencia** byte a byte | BLOQ |

## 3. Notas

- **V12:** el máximo de `n_prev_season` en un partido es 37 (el equipo ya jugó 37 partidos y este es el 38).
- **V14/V15:** estas dos pruebas son la defensa principal contra data leakage; ninguna puede reemplazarse por inspección visual. V14 exige controles negativos **y** positivo; V15 exige el conjunto obligatorio antes de la muestra aleatoria (semilla `42`, 100 partidos, parámetros de especificación).
- **Autopruebas:** cada prueba bloqueante de CANONICAL/FEATURES debe demostrar, con un defecto sintético en memoria, que es capaz de fallar (obligatorio para V03; recomendado para el resto).
- **V17** se añadió en el patch 1 (esquema normativo de FEATURES); V02 queda limitado a CANONICAL.
- **V01 también se ejecuta al terminar el pipeline**, para probar que RAW no se modificó.
- **Alcance futuro:** la regla T10 (partidos de otros equipos deben haber *finalizado*) añadirá una prueba específica cuando exista alguna feature que la requiera. No aplica en v0.1.

## 4. Cambios del patch 1 (2026-10-28)

| ID | Cambio |
|---|---|
| V01 | Incluye `notes.txt`, `role` y resolución de rutas desde la raíz de `SCOPE/` |
| V02 | Esquema normativo completo de CANONICAL (42 columnas, serialización, idempotencia) |
| V03 | Comparación campo por campo con RAW; autoprueba de intercambio de filas |
| V05 | Añade unicidad de parejas ordenadas `(home_team_id, away_team_id)` |
| V06 | Valida el formato **CANONICAL** (ISO), no el de RAW; `kickoff_datetime == match_date + kickoff_time`; re-parseo estricto de RAW; hipótesis operativa de equipo |
| V07 | Relación real `(fuente, alias RAW) → team_id → display_name` |
| V10 | Recalcula flags por fila; conteos globales como prueba adicional |
| V13 | "Valores vacíos" en lugar de "NaN" |
| V14 | Controles negativos y positivo; perturbación coherente |
| V15 | Conjunto obligatorio + muestra aleatoria con semilla fija |
| **V17** | **Nueva:** esquema normativo de FEATURES (30 columnas) |
