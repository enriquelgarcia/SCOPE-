# SCOPE — Data Pipeline v0.1: implementación, validación y artefactos congelados

**Documento narrativo n.º 02**
**Proyecto:** SCOPE — Sports Computational Outcome Prediction Engine
**Fase que describe:** Data Pipeline v0.1 (`RAW → INTERIM → CANONICAL → team_match_log → FEATURES`)
**Estado formal de la fase:** SCOPE DATA PIPELINE v0.1 — COMPLETED / FROZEN (Decision Log D44, 2026-10-29)
**Documento previo:** `01_arquitectura_y_data_contract.md` (arquitectura y reglas)
**Evidencia de referencia:** `../contract/SCOPE_Data_Contract_v0.1.md`, `../DECISION_LOG.md`, `../validation/validation_spec_v0.1.md`, `../quality/data_quality_register_v0.1.md`, `../data_dictionary/`, y los informes `reports/checkpoint_a/`, `reports/checkpoint_b/` y `reports/checkpoint_c/` en la raíz de `SCOPE/`.

---

## Tabla de contenidos

1. [Propósito y alcance del Data Pipeline v0.1](#1-propósito-y-alcance-del-data-pipeline-v01)
2. [Datos de partida](#2-datos-de-partida)
3. [Inmutabilidad y trazabilidad en la práctica](#3-inmutabilidad-y-trazabilidad-en-la-práctica)

**Checkpoint A**

4. [Checkpoint A — RAW → INTERIM](#4-checkpoint-a--raw--interim)
5. [Construcción de INTERIM](#5-construcción-de-interim)
6. [Limpieza superficial aplicada](#6-limpieza-superficial-aplicada)
7. [Fidelidad de INTERIM respecto a RAW](#7-fidelidad-de-interim-respecto-a-raw)
8. [Resultado del Checkpoint A](#8-resultado-del-checkpoint-a)

**Checkpoint B**

9. [Checkpoint B — INTERIM → CANONICAL](#9-checkpoint-b--interim--canonical)
10. [Identidad de equipos](#10-identidad-de-equipos)
11. [Identidad y trazabilidad de partidos](#11-identidad-y-trazabilidad-de-partidos)
12. [Transformación temporal](#12-transformación-temporal)
13. [Targets y estadísticas](#13-targets-y-estadísticas)
14. [Calidad de datos y `dq_flags`](#14-calidad-de-datos-y-dq_flags)
15. [Anomalías conocidas preservadas](#15-anomalías-conocidas-preservadas)
16. [Validación del Checkpoint B](#16-validación-del-checkpoint-b)
17. [Resultado del Checkpoint B](#17-resultado-del-checkpoint-b)

**Checkpoint C**

18. [Checkpoint C — CANONICAL → team_match_log → FEATURES](#18-checkpoint-c--canonical--team_match_log--features)
19. [Construcción de `team_match_log`](#19-construcción-de-team_match_log)
20. [Construcción de FEATURES](#20-construcción-de-features)
21. [Reinicio por temporada](#21-reinicio-por-temporada)
22. [Elegibilidad](#22-elegibilidad)

**Validación temporal**

23. [Prevención de data leakage en la implementación](#23-prevención-de-data-leakage-en-la-implementación)
24. [V14 — Test de perturbación](#24-v14--test-de-perturbación)
25. [V15 — Oráculo independiente](#25-v15--oráculo-independiente)
26. [V16 y V17](#26-v16-y-v17)

**Validación general**

27. [Sistema de validaciones V01–V17](#27-sistema-de-validaciones-v01v17)
28. [Tests automatizados](#28-tests-automatizados)
29. [Determinismo, idempotencia y reproducibilidad](#29-determinismo-idempotencia-y-reproducibilidad)

**Cierre**

30. [Artefactos finales congelados](#30-artefactos-finales-congelados)
31. [Qué quedó fuera del pipeline](#31-qué-quedó-fuera-del-pipeline)
32. [Riesgos y cuestiones transferidas al EDA](#32-riesgos-y-cuestiones-transferidas-al-eda)
33. [Estado final del pipeline](#33-estado-final-del-pipeline)

[Anexo A — Manifiesto RAW](#anexo-a--manifiesto-raw)

---

## 1. Propósito y alcance del Data Pipeline v0.1

El Documento 01 describió la arquitectura de datos de SCOPE y las reglas que el Data Contract impone a cualquier implementación. Este documento explica cómo se implementó realmente esa arquitectura, qué produjo cada etapa y qué evidencia permite afirmar que el resultado cumple el contrato.

La fase que aquí se documenta cubre la primera mitad del flujo:

```
RAW → INTERIM → CANONICAL → team_match_log → FEATURES
```

Las capas MODELS y PREDICTIONS no forman parte de esta fase. El pipeline termina en FEATURES: al cierre de v0.1 **no se ha entrenado ningún modelo**, no se ha calculado ninguna predicción y no se ha realizado la comparación con el mercado.

La implementación se dividió en tres checkpoints. Cada uno transforma una capa en la siguiente y debe aprobar todas sus validaciones antes de que el siguiente pueda comenzar. El checkpoint posterior, además, comprueba al arrancar que su entrada es exactamente la que se aprobó, comparando su SHA-256 con el valor registrado.

| Checkpoint | Transformación | Validaciones propias |
|---|---|---|
| **A** | RAW → INTERIM | V01 (antes y después) y A01–A11 |
| **B** | INTERIM → CANONICAL | V01, B00–B01 y V02–V10 |
| **C** | CANONICAL → team_match_log → FEATURES | V01, C00–C03 y V11–V17 |

Las pruebas `V01`–`V17` son las definidas en la especificación de validaciones del contrato. Las pruebas con prefijo `A`, `B` y `C` son controles propios de cada checkpoint: integridad de la entrada, determinismo y comprobaciones específicas de la capa intermedia.

---

## 2. Datos de partida

### 2.1 La instantánea RAW

El pipeline parte de una única instantánea de datos descargada de **Football-Data.co.uk**: un archivo CSV por temporada de la Premier League, de 2021/22 a 2025/26, más el archivo `notes.txt`, que es la documentación oficial de columnas de la propia fuente. El manifiesto `raw_manifest_v0.1.csv` registra cada archivo con su ruta, número de filas y columnas, presencia de BOM, rango de fechas, tamaño en bytes, tipo de fin de línea y SHA-256. Según el Decision Log (D40), la URL exacta de descarga y la fecha de incorporación no quedaron registradas; la instantánea usada por v0.1 permanece congelada y no se volvió a descargar nada.

| Archivo | Temporada | Filas | Columnas | BOM | Primera fecha | Última fecha |
|---|---|---|---|---|---|---|
| `PL_2021-2022_raw.csv` | 2021/22 | 380 | 106 | sí | 2021-08-13 | 2022-05-22 |
| `PL_2022-2023_raw.csv` | 2022/23 | 380 | 106 | no | 2022-08-05 | 2023-05-28 |
| `PL_2023-2024_raw.csv` | 2023/24 | 380 | 106 | no | 2023-08-11 | 2024-05-19 |
| `PL_2024-2025_raw.csv` | 2024/25 | 380 | 120 | sí | 2024-08-16 | 2025-05-25 |
| `PL_2025-2026_raw.csv` | 2025/26 | 380 | 132 | sí | 2025-08-15 | 2026-05-24 |

Los cinco CSV están en `Premier_League_data_raw_csv/` y usan fin de línea CRLF; `notes.txt` está en `Documentacion de datos/`. En total hay **1,900 partidos**, 380 por temporada. Los SHA-256 completos figuran en el [Anexo A](#anexo-a--manifiesto-raw).

### 2.2 Cambios de esquema entre temporadas

El número de columnas no es constante: 106 en las tres primeras temporadas, 120 en 2024/25 y 132 en 2025/26. No se trata de un error, sino de *schema drift* de la fuente. Según el registro de calidad, los cambios se deben a la entrada y salida de casas de apuestas en el archivo: en 2024/25 desaparecen IW y VC y aparecen BF, 1XB y Betfair Exchange; en 2025/26 desaparecen BF, 1XB y WH y aparecen BFD, BMGM, BV, CL y LB.

Al unir las cinco temporadas existen **162 columnas RAW distintas**, de las cuales **88 son comunes** a las cinco. Este dato, confirmado en el informe del Checkpoint A (A02), condiciona directamente el diseño de INTERIM.

### 2.3 Particularidades de formato

El registro de calidad documenta además tres rasgos de formato que la implementación tuvo que tolerar sin modificar RAW: la marca BOM aparece en tres archivos y no en los otros dos (Q03); los cinco archivos usan CRLF (Q04); y `notes.txt` describe la fecha como `dd/mm/yy`, mientras que los archivos usan en realidad `dd/mm/yyyy` (Q05). La fuente tampoco documenta la zona horaria de la hora de inicio (Q06) ni incluye una columna de jornada (Q08).

---

## 3. Inmutabilidad y trazabilidad en la práctica

### 3.1 Verificación de RAW antes y después

La regla "RAW es inmutable" se convirtió en una comprobación ejecutable, V01. Al principio y al final de **cada uno de los tres checkpoints** se recalculó el SHA-256 de los seis archivos del manifiesto —los cinco CSV y `notes.txt`— y se comparó con el valor registrado. En los CSV se comprobaron además filas, columnas, BOM y fechas mínima y máxima. Los tres informes registran coincidencia total, antes y después, en los seis archivos.

Como protección adicional, la configuración del pipeline declara como zonas de solo lectura la carpeta RAW, `Documentacion de datos/`, `docs/` y las copias en Excel, y rechaza cualquier intento de escribir en ellas. Uno de los tests automatizados comprueba que esa protección funciona.

### 3.2 Trazabilidad por fila

Para que cualquier dato procesado pueda reconstruirse hasta su origen, INTERIM añade a cada fila cuatro columnas de trazabilidad que se conservan en CANONICAL:

- `season`: temporada, derivada del nombre del archivo;
- `source_name`: fuente del registro (`football-data.co.uk`);
- `source_file`: archivo RAW de origen;
- `source_row`: posición de la fila de datos en ese archivo, contando desde 1 y sin la cabecera. La línea física del archivo es `source_row + 1`.

Con estas cuatro columnas, cualquier valor de CANONICAL puede compararse con la celda exacta de RAW de la que procede. Las validaciones A04 y V03 hacen precisamente eso.

---

# Checkpoint A

## 4. Checkpoint A — RAW → INTERIM

El objetivo de INTERIM es convertir cinco archivos heterogéneos en una única tabla técnica y uniforme sin perder información. En concreto, el Checkpoint A debía:

- unificar las cinco temporadas en un solo archivo;
- aplicar un tipado técnico estricto a cada celda;
- resolver los aspectos superficiales de formato (BOM, CRLF, espacios sobrantes);
- conservar todas las columnas y todos los valores de RAW;
- añadir la trazabilidad descrita en la sección 3.2.

Igual de importante es lo que INTERIM **no** hace. No selecciona variables ni construye features; no corrige datos de origen, aunque sean sospechosos; no elimina anomalías; y no traduce todavía la información al esquema conceptual de SCOPE. Los nombres de columna siguen siendo los de Football-Data (`FTHG`, `HST`, `AvgH`…) y los equipos siguen escritos con los alias de la fuente.

---

## 5. Construcción de INTERIM

### 5.1 Estructura

Cada fila de RAW produce exactamente una fila de INTERIM. Las filas se ordenan por temporada y, dentro de cada temporada, por `source_row`, es decir, en el orden original de cada archivo.

Las columnas son las cuatro de trazabilidad seguidas de la unión de las 162 columnas RAW con sus nombres originales: **166 columnas**. El resultado tiene **1,900 filas**.

Cuando una columna no existe en una temporada —por ejemplo, las cuotas de una casa de apuestas que solo aparece en 2025/26—, todas las filas de esa temporada tienen ese campo vacío. La validación A07 contabilizó **240 pares (temporada, columna)** en esa situación, todos representados como vacíos al 100 %, que corresponden exactamente a las 162 × 5 combinaciones posibles menos las 570 columnas presentes por temporada. Qué columnas existen en cada temporada queda documentado en el diccionario RAW, así que un campo vacío por ausencia de columna puede distinguirse de un nulo dentro de una columna existente.

### 5.2 Tipado técnico

Cada celda se interpreta según el tipo que le asigna el diccionario RAW, con reglas estrictas que no imputan, corrigen ni descartan valores:

- una celda vacía se convierte en nulo y se escribe como campo vacío;
- las fechas se parsean estrictamente con `%d/%m/%Y` y se escriben como `YYYY-MM-DD`;
- las horas se parsean estrictamente con `HH:MM`;
- los enteros y decimales deben cumplir un formato numérico estricto: un valor con espacios o con un formato inesperado provoca un error en lugar de "arreglarse";
- los textos solo se someten a `strip()`, registrando cada celda modificada (sección 6).

### 5.3 Convenciones de lectura y escritura

La lectura tolera tanto la presencia como la ausencia de BOM y acepta CRLF; uno de los tests comprueba que ambas variantes producen exactamente la misma lectura. La escritura sigue siempre la misma convención: UTF-8 **sin BOM**, fin de línea **LF**, valores ausentes como campo vacío —nunca los literales `NaN`, `NA`, `NULL` o `None`— y una serialización estable de cada tipo.

Para los números decimales se aplica la regla D43: los valores sin parte fraccionaria se escriben siempre con decimal explícito (`4.0`, no `4`), aunque el texto RAW fuera `4`, y los demás se escriben con la representación decimal más corta que reproduce exactamente el mismo valor de coma flotante, sin redondear. D43 se formalizó durante el Checkpoint A para eliminar una ambigüedad detectada; según el Decision Log, la implementación ya cumplía la regla, por lo que INTERIM no tuvo que regenerarse.

---

## 6. Limpieza superficial aplicada

La limpieza de INTERIM fue deliberadamente mínima, y conviene distinguir dos operaciones de naturaleza muy distinta:

- la **limpieza técnica** elimina problemas de formato que no alteran el significado del dato, como un espacio al final de un texto;
- la **corrección de contenido** cambia el valor de un dato porque se cree que es erróneo, como sustituir un número de tiros que parece imposible.

INTERIM realiza la primera y nunca la segunda.

En toda la instantánea, la limpieza técnica afectó a **una sola celda**, documentada en el registro de calidad como Q02:

| Archivo | `source_row` | Columna | RAW | INTERIM |
|---|---|---|---|---|
| `PL_2023-2024_raw.csv` | 357 | `Referee` | `"J Gillett "` | `"J Gillett"` |

Sin el `strip()`, ese partido habría aparecido con un árbitro distinto de `J Gillett`. La operación se aplicó solo en INTERIM; la fila RAW original conserva el espacio, como confirman los SHA-256 de V01. La validación A06 verificó que esta es la única celda modificada en toda la tabla.

---

## 7. Fidelidad de INTERIM respecto a RAW

El Checkpoint A no se dio por bueno porque el código "pareciera correcto", sino porque un conjunto de comprobaciones independientes confirmó que INTERIM es una representación fiel de RAW. Las once pruebas A01–A11, junto con V01, pueden agruparse en cinco bloques.

**Integridad.** V01 pasó antes y después de la ejecución, con los seis archivos intactos. A03 confirmó cinco temporadas de 380 filas, 1,900 en total, y A09 confirmó que el proceso no introdujo filas duplicadas.

**Formato.** A01 verificó que el archivo es UTF-8 sin BOM, con LF y sin literales nulos. A02 verificó el esquema: 4 columnas de trazabilidad más la unión de 162 columnas RAW, 166 en total, con 88 comunes a las cinco temporadas. A10 comprobó que cada celda está tipada y serializada de forma estable.

**Fidelidad.** A05 volvió a leer RAW de forma independiente y comparó INTERIM **celda a celda**: **216,600 celdas RAW**, que son todas las celdas de datos de las cinco temporadas (380 filas × 570 columnas presentes). A06 verificó que la única diferencia es el `strip()` de Q02. A07 verificó que los nulos de cada temporada y columna coinciden exactamente con los de RAW. A08 verificó que las anomalías conocidas se conservaron sin corregir: el valor de Q01 y los conteos de los avisos de calidad, recalculados sobre INTERIM, son 0, 1 y 12 (sección 14).

**Trazabilidad.** A04 confirmó la correspondencia uno a uno entre cada fila de INTERIM y su fila de origen, a través de `season`, `source_name`, `source_file` y `source_row`.

**Determinismo.** A11 confirmó que construir INTERIM dos veces produce exactamente los mismos bytes, y que volver a leerlo y serializarlo también los reproduce (idempotencia).

---

## 8. Resultado del Checkpoint A

| Artefacto | Ruta | Dimensiones | Tamaño | SHA-256 |
|---|---|---|---|---|
| INTERIM | `data/interim/pl_interim_v0.1.csv` | 1,900 × 166 | 1,140,220 bytes | `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad` |

**El Checkpoint A terminó en PASS**: V01, antes y después, y A01–A11 en PASS. Este hash pasó a ser la entrada aprobada del Checkpoint B.

---

# Checkpoint B

## 9. Checkpoint B — INTERIM → CANONICAL

En el Checkpoint B los datos dejan de ser una representación cercana a la fuente y pasan a ser la representación oficial de un partido dentro de SCOPE. Antes de transformar nada, el checkpoint comprobó que INTERIM existía y que su SHA-256 era exactamente el aprobado en el Checkpoint A, y volvió a ejecutar A01–A11 sobre él (B00).

A partir de ahí, la construcción de CANONICAL materializó lo que el contrato establece en sus secciones 4.0–4.9:

- **selección de campos:** de las 166 columnas de INTERIM se conservaron solo las necesarias para los 42 campos del esquema, todas presentes y completas en las cinco temporadas;
- **renombrado:** los nombres de la fuente pasan a nombres SCOPE (`FTHG` → `home_goals`, `HST` → `home_shots_on_target`, `AvgH` → `mkt_avg_pre_home`…);
- **tipos estables:** cada columna adopta el tipo lógico, la nulabilidad y la serialización del esquema normativo;
- **normalización temporal:** fecha, hora e instante de inicio en formato ISO (sección 12);
- **identidad de equipos y partidos:** alias de la fuente sustituidos por `team_id` y `display_name`, y construcción de `match_id` (secciones 10 y 11);
- **targets:** `result` y `goal_difference` (sección 13);
- **bloque de mercado:** solo las seis cuotas medias 1X2 (sección 13);
- **calidad:** cálculo de `dq_flags` (sección 14).

La construcción se diseñó para fallar en lugar de improvisar: un alias de equipo que no esté en el mapeo, o un código de división distinto de `E0`, detienen el proceso. Ambos comportamientos están cubiertos por tests.

---

## 10. Identidad de equipos

El mapeo `team_mapping_v0.1.csv` contiene una fila por alias, con cuatro columnas: la fuente (`source`), el alias original del equipo en esa fuente (`source_name`), el identificador interno (`team_id`) y el nombre de presentación (`display_name`). En v0.1 hay un alias por equipo y **27 `team_id`**, congelados por D27. Algunos ejemplos:

| `source` | Alias en RAW | `team_id` | `display_name` |
|---|---|---|---|
| football-data.co.uk | `Man City` | `manchester_city` | Manchester City |
| football-data.co.uk | `Nott'm Forest` | `nottingham_forest` | Nottingham Forest |
| football-data.co.uk | `Brighton` | `brighton_and_hove_albion` | Brighton & Hove Albion |
| football-data.co.uk | `Wolves` | `wolverhampton_wanderers` | Wolverhampton Wanderers |

La validación V07 no se limitó a comprobar que cada `team_id` de CANONICAL existiera en el catálogo, porque eso no detectaría dos identificadores intercambiados entre equipos. Para cada partido, V07 tomó el `HomeTeam` y el `AwayTeam` **reales** de la fila RAW citada por la trazabilidad y verificó que `home_team_id` y `away_team_id` fueran exactamente los `team_id` de esos alias, y que los nombres fueran exactamente sus `display_name`. Comprobó además que local y visitante sean distintos, que haya 27 identificadores distintos en el conjunto y que coincidan con los congelados. Los tests incluyen defectos sintéticos de este tipo —identificadores intercambiados entre dos equipos en todo el archivo, local y visitante intercambiados en una sola fila, un `display_name` incorrecto— y V07 los detecta.

---

## 11. Identidad y trazabilidad de partidos

### 11.1 `match_id`

Cada partido recibió un `match_id` construido de forma determinista a partir de la clave natural, con el formato `{competition_code}_{season}_{YYYYMMDD}_{home_team_id}_{away_team_id}`. Un test comprueba que el ejemplo del contrato, `EPL_2021-2022_20210813_brentford_arsenal`, aparece efectivamente en CANONICAL con la semántica esperada.

V04 validó tres propiedades: que `match_id` es único, que la clave natural `(competition_code, season, match_date, home_team_id, away_team_id)` también es única, y que cada `match_id` coincide con el que resulta de aplicar la regla de construcción a los campos de su fila.

### 11.2 Trazabilidad campo por campo

V03 es la validación que conecta CANONICAL con RAW. Para cada una de las **1,900 filas**, volvió a leer la fila RAW citada por `source_file` y `source_row` **de forma independiente**, sin pasar por INTERIM ni reutilizar el código de construcción, y comparó los **34 campos trasladados desde RAW** aplicando solo las transformaciones documentadas: código de división y competición, fecha y hora con reparseo estricto, equipos a través del mapeo, árbitro con `strip()`, goles y resultado final y al descanso, las doce estadísticas del partido y las seis cuotas medias, estas últimas con igualdad numérica exacta. También verificó la correspondencia uno a uno, sin filas repetidas ni omitidas.

La especificación exige que V03 demuestre que es capaz de fallar. En una copia en memoria se intercambiaron cuotas o estadísticas entre dos partidos —valores válidos y dentro de rango, pero en la fila equivocada— y V03 lo detectó. Los tests añaden variantes del mismo defecto: cuotas de cierre de otro partido, estadísticas de otro partido o un `source_row` incorrecto.

---

## 12. Transformación temporal

La fecha de RAW (`Date`, en formato `dd/mm/yyyy`) se parsea estrictamente con `%d/%m/%Y`, y la hora (`Time`) con `%H:%M`. A partir de ellas, CANONICAL materializa tres campos:

- `match_date`, en formato `YYYY-MM-DD`;
- `kickoff_time`, en formato `HH:MM`;
- `kickoff_datetime`, en formato `YYYY-MM-DDTHH:MM:SS`, sin zona horaria, exactamente igual a `match_date` + `T` + `kickoff_time` + `:00`.

V06 comprobó estos formatos y la igualdad anterior, y volvió a parsear la fecha y la hora de RAW para confirmar que su versión ISO coincide con la de CANONICAL. Esta comprobación existe para detectar una confusión entre día y mes, un error silencioso porque produce fechas válidas. Los tests la ejercitan con dos variantes: una fecha escrita en formato RAW y una confusión día/mes aplicada de forma consistente en ISO. V06 verificó además que cada fecha cae dentro de la ventana agosto–junio de su temporada y que ningún equipo tiene dos partidos el mismo día ni en el mismo instante, que es la hipótesis operativa 6.1 del contrato.

Las filas de CANONICAL se escribieron ordenadas por `kickoff_datetime` y, en caso de empate, por `match_id`. Ese orden es solo la disposición física del archivo, necesaria para que la serialización sea idéntica byte a byte entre ejecuciones. Sobre él se construyó `match_seq_season`, un número del 1 al 380 dentro de cada temporada que V06 verificó sin huecos ni repeticiones y coherente con el orden por `kickoff_datetime`. `match_seq_season` es un orden auxiliar y **no una frontera temporal**: cuando dos partidos empiezan a la misma hora, el desempate por `match_id` es alfabético y no indica que uno ocurriera antes que el otro.

Esta precisión es relevante porque los inicios simultáneos son frecuentes en la Premier League. V06 contó, por temporada, los partidos que comparten `kickoff_datetime` con al menos otro partido: 213, 208, 204, 227 y 218. No son anomalías; son la forma normal del calendario, con varios partidos de distintos equipos a la misma hora. El pipeline los contempla explícitamente: V06 descarta que un mismo equipo juegue dos veces en el mismo instante, y V15 dedica un subconjunto específico a los partidos con inicio simultáneo (sección 25).

---

## 13. Targets y estadísticas

CANONICAL contiene, para cada partido:

- **`result`**, tomado de `FTR` (`H`, `D` o `A`);
- **`goal_difference`**, calculado como `home_goals − away_goals`;
- **las estadísticas post-partido**: goles finales y al descanso, resultado al descanso, tiros, tiros a puerta, córneres, faltas y tarjetas amarillas y rojas de cada equipo, sin ninguna corrección;
- **las seis cuotas medias del mercado 1X2**, previas al cierre (`AvgH/AvgD/AvgA`) y de cierre (`AvgCH/AvgCD/AvgCA`), como `mkt_avg_pre_*` y `mkt_avg_close_*`. Las cuotas de casas individuales, los máximos y los mercados O/U y hándicap asiático permanecen solo en INTERIM; un test comprueba que no pasa a CANONICAL ninguna columna de mercado adicional.

Como se explicó en el Documento 01, almacenar campos POST o MARKET en CANONICAL **no significa** que puedan usarse como predictores del propio partido. CANONICAL guarda hechos. Los predictores de v0.1 se seleccionarán del bloque de variables históricas pre-partido almacenado en FEATURES (las métricas `h_`, `a_` y `diff_`). Las claves (`match_id`, `season`, `kickoff_datetime`), los targets (`result`, `goal_difference`) y los campos de control (`is_modeling_eligible`, `feature_version`) cumplen otras funciones y no forman parte automáticamente del conjunto predictor. La sección 23 explica cómo se comprobó empíricamente que las features históricas no incorporan información del propio partido ni del mercado.

La coherencia de los targets se verificó en todas las filas mediante V09: `goal_difference` es exactamente `home_goals − away_goals`, y `result` es exactamente el signo de `goal_difference` (positivo, `H`; cero, `D`; negativo, `A`). V09 no se limita a confirmar que los valores son válidos, sino que comprueba la relación exacta entre campos. Los tests incluyen un resultado inconsistente con los goles, una diferencia de goles mal calculada y un marcador falso pero internamente coherente, este último detectado por V03 al compararlo con RAW.

---

## 14. Calidad de datos y `dq_flags`

El campo `dq_flags` marca, sin corregirlas, ciertas inconsistencias de las estadísticas de origen. El catálogo del registro de calidad define tres códigos, en este orden de serialización:

| Código | Condición | Severidad | Ocurrencias |
|---|---|---|---|
| `HST_GT_HS` | el local tiene más tiros a puerta que tiros | warning | **0** |
| `AST_GT_AS` | el visitante tiene más tiros a puerta que tiros | warning | **1** |
| `GOALS_GT_SOT` | algún equipo marca más goles que tiros a puerta | info | **12** |

Si un partido tiene varios códigos, se escriben en el orden del catálogo separados por `|`; si no tiene ninguno, el campo queda vacío.

V10 no se conformó con comprobar esos totales. Para **cada fila**, recalculó desde cero el conjunto de códigos que le corresponde según sus propios valores y verificó que coincide exactamente con `dq_flags`: los mismos códigos, ninguno de más, sin duplicados, solo del catálogo, en el orden correcto y con el campo vacío cuando no hay avisos. Solo después comprobó los totales (0, 1 y 12) y que cada aviso aparece en la fila localizada por el registro de calidad. Esta forma de validar detecta defectos que un simple conteo no vería, como un aviso trasladado a la fila equivocada, que está cubierto por un test.

`GOALS_GT_SOT` tiene severidad informativa y **no se interpreta como un error**. Un equipo puede marcar más goles que tiros a puerta propios, entre otras razones porque los autogoles cuentan como gol sin ser un tiro a puerta del equipo beneficiado; también pueden influir particularidades del registro de la fuente. El registro de calidad concluye que estos doce casos no son errores demostrables y que se marcan solo para trazabilidad. Ningún partido se excluye por tener avisos.

---

## 15. Anomalías conocidas preservadas

El principio aplicado a todas las anomalías es el mismo: se documentan, se conservan y, cuando procede, se marcan, pero no se corrigen sin evidencia. A continuación se resumen las que son relevantes para entender el pipeline.

### Q01 — Tiros a puerta mayores que tiros

En `PL_2021-2022_raw.csv`, `source_row = 9`, partido Newcastle – West Ham del 15/08/2021, el visitante tiene `AS = 8` tiros y `AST = 9` tiros a puerta, lo cual es imposible. Es la única ocurrencia de `AST_GT_AS`.

El valor se conserva sin corregir en INTERIM y CANONICAL, porque sin otra fuente no puede saberse cuál es el dato correcto. Por construcción de la ventana `last5`, que promedia los tiros a puerta propios de los últimos cinco partidos, este `AST = 9`, que son tiros a puerta de West Ham, entra en el `sot_pg_last5` de West Ham en sus partidos posteriores de 2021/22 mientras ese encuentro forme parte de su ventana, es decir, como máximo en los cinco siguientes. Es una consecuencia lógica de la definición de la ventana, no el resultado de una validación específica de impacto. Nunca afecta a las features del propio partido. El registro de calidad reserva al EDA la decisión de si su impacto justifica algún tratamiento.

### Q02 — Espacio final en el nombre del árbitro

`"J Gillett "` en `PL_2023-2024_raw.csv`, `source_row = 357`. Se resolvió únicamente en INTERIM mediante `strip()` (sección 6). RAW conserva el valor original y `referee` no es predictor en v0.1.

### Q17–Q19 — Anomalías en mercados O/U 2.5 y hándicap asiático

La auditoría del Checkpoint A detectó tres anomalías en cuotas, verificadas con una lectura independiente de RAW:

- **Q17** (2021/22, `source_row` 167): cuotas de cierre de más/menos 2.5 goles de una casa de apuestas con valor `0`, imposible para una cuota decimal;
- **Q18** (2025/26, `source_row` 121–130): diez partidos consecutivos con una cuota máxima de hándicap asiático de `22`, muy por encima de los valores de las casas individuales, y un promedio también fuera de rango;
- **Q19** (2025/26, `source_row` 312): una cuota máxima de hándicap asiático de `3.5` frente a valores en torno a 1.8–2.1 en las demás.

Las tres son anomalías de la fuente y no del pipeline: INTERIM reproduce RAW exactamente, y un test comprueba que siguen presentes. Se preservan en RAW e INTERIM y no se convirtieron en nulos ni se corrigieron, porque no hay evidencia externa que indique el valor correcto. Todas pertenecen a los mercados O/U 2.5 y hándicap asiático, que **no pasan a CANONICAL v0.1**, de modo que no afectan al modelo ni al benchmark 1X2 que usa SCOPE. Tampoco generan `dq_flags`, porque el catálogo no contempla anomalías de cuotas.

### Huecos en cuotas de casas individuales

El registro de calidad documenta también huecos en las cuotas de varias casas de apuestas, en algunos casos desde una fecha determinada de la temporada (Q09–Q16). Ninguno afecta a CANONICAL: las seis cuotas medias 1X2 que pasan a esa capa no tienen ningún nulo en las cinco temporadas.

---

## 16. Validación del Checkpoint B

Las validaciones V02–V10 se ejecutaron sobre el archivo CANONICAL generado, junto con V01 antes y después y los controles B00 y B01. Todas terminaron en PASS. Agrupadas por objetivo:

**Esquema y serialización — V02.** Se comprobó el esquema normativo completo del contrato: **1,900 filas × 42 columnas**, cabecera exacta y en orden, tipo lógico, nulabilidad, dominio y serialización de cada columna, ausencia de literales nulos, UTF-8 sin BOM, LF y filas ordenadas por (`kickoff_datetime`, `match_id`). También se comprobó la idempotencia: leer el archivo con los tipos del esquema y volver a escribirlo produce exactamente los mismos bytes.

**Trazabilidad — V03.** Comparación independiente con RAW de 1,900 filas y 34 campos por fila, con autoprueba de intercambio (sección 11.2).

**Identidad — V04 y V07.** Unicidad de `match_id` y de la clave natural, conformidad con la regla de construcción y mapeo exacto desde el alias real de RAW; 27 `team_id` distintos, coincidentes con los congelados (secciones 10 y 11).

**Conteos y calendario — V05 y V06.** Cada temporada tiene **380 partidos y 20 equipos**, con 19 partidos de local y 19 de visitante por equipo, y cada pareja ordenada local–visitante aparece exactamente una vez: 380 parejas por temporada. Esta última condición detecta un calendario con un enfrentamiento duplicado y otro omitido, que pasaría los conteos simples; un test lo comprueba. V06 cubrió fechas, formatos, ventana de temporada, `match_seq_season` y la hipótesis de equipo (sección 12).

**Rangos y coherencia — V08 y V09.** Goles y estadísticas enteros y no negativos, goles al descanso que no superan los finales, cuotas mayores que 1.0 y sin nulos, resultado al descanso coherente con sus goles, y coherencia exacta de los dos targets (sección 13).

**Calidad — V10.** Recalculo de `dq_flags` por fila, con totales de 0, 1 y 12 y localizaciones coincidentes con el registro de calidad (sección 14).

Como parte de V09, el informe registra la distribución global de `result`: **H = 839, D = 454 y A = 607**. Esta cifra aparece aquí únicamente como evidencia descriptiva de la ejecución: su suma es 1,900 y es coherente con el reparto de puntos de `team_match_log` (sección 19). No se usa para tomar ninguna decisión de modelado, que corresponde al EDA y debe respetar la política D42 sobre la temporada 2025/26.

---

## 17. Resultado del Checkpoint B

| Artefacto | Ruta | Dimensiones | SHA-256 |
|---|---|---|---|
| CANONICAL | `data/canonical/pl_canonical_v0.1.csv` | 1,900 × 42 | `06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1` |

Además:

- **INTERIM permaneció intacto**: su SHA-256 antes y después del checkpoint es el aprobado, `cec123ce…c7d543ad`.
- **RAW permaneció intacto**: V01 pasó antes y después en los seis archivos.
- **Dos construcciones independientes a partir del mismo INTERIM produjeron exactamente los mismos bytes** (B01), con el mismo SHA-256 en ambas.

**El Checkpoint B terminó en PASS.**

---

# Checkpoint C

## 18. Checkpoint C — CANONICAL → team_match_log → FEATURES

El Checkpoint C es la fase metodológicamente más delicada del pipeline. Calcular un promedio de puntos o de goles es sencillo; lo difícil es garantizar que, para cada uno de los 1,900 partidos, ese promedio se haya calculado **solo** con información disponible antes de que el partido empezara. Un error de un solo índice —incluir el propio partido en su historial, o el partido siguiente— produce features con un rendimiento aparentemente excelente y sin ninguna validez. Por eso este checkpoint concentra las pruebas más exigentes del pipeline.

Al comenzar, el checkpoint verificó que INTERIM y CANONICAL eran exactamente los aprobados y volvió a ejecutar V02–V10 sobre CANONICAL en modo lectura (C00). Al terminar, verificó que ambos seguían intactos.

El Checkpoint C **no entrena modelos**. Su salida es una tabla de variables pre-partido lista para el análisis exploratorio y el modelado, que se realizarán en fases posteriores.

---

## 19. Construcción de `team_match_log`

El primer paso fue desdoblar cada partido de CANONICAL en dos perspectivas: una fila para el equipo local y otra para el visitante.

```
1 partido de CANONICAL  →  2 filas de team_match_log
   (local, visitante)        (perspectiva de cada equipo)
```

El resultado tiene **3,800 filas × 10 columnas**:

| Columna | Contenido |
|---|---|
| `match_id` | partido al que pertenece la fila |
| `season` | temporada |
| `kickoff_datetime` | instante de inicio del partido |
| `team_id` | equipo cuya perspectiva describe la fila |
| `opponent_team_id` | rival |
| `is_home` | si el equipo jugó como local |
| `goals_for` | goles marcados por el equipo |
| `goals_against` | goles recibidos por el equipo |
| `points` | puntos obtenidos (3, 1 o 0) |
| `shots_on_target_for` | tiros a puerta del propio equipo |

El archivo se ordena por equipo y por `kickoff_datetime`. Como en CANONICAL, ese orden es solo la disposición física; la frontera temporal sigue siendo `kickoff_datetime`. Todos los valores se derivan exclusivamente de CANONICAL, y `team_match_log` no contiene ninguna cuota.

C01 verificó el formato, la cabecera, el número de filas —exactamente el doble que partidos— y el orden. C02 verificó que las dos filas de cada partido son un **espejo** coherente: los goles a favor de un lado son los goles en contra del otro, la localía es complementaria, cada lado toma los tiros a puerta que le corresponden y todos los valores coinciden con CANONICAL. En particular, C02 comprobó el reparto de puntos: **1,446 partidos decisivos con reparto 3 + 0** y **454 empates con reparto 1 + 1**. Ambas cifras cuadran con la distribución de `result` de CANONICAL: 839 + 607 = 1,446 partidos con ganador, y 454 empates.

---

## 20. Construcción de FEATURES

### 20.1 Cálculo del historial previo

A partir de `team_match_log`, las features se calcularon así:

1. las filas se agrupan por temporada y equipo, de modo que cada grupo es la secuencia de partidos de un equipo en una temporada;
2. dentro de cada grupo, los partidos se ordenan por `kickoff_datetime`;
3. para el partido en la posición *i*, el historial son los partidos en las posiciones 0 a *i* − 1, lo que equivale a un desplazamiento `shift(1)`: el propio partido nunca forma parte de su historial;
4. la ventana *season* es todo ese historial y la ventana *last5* son sus `min(5, n_prev_season)` elementos más recientes;
5. sobre cada ventana se calculan los promedios por partido;
6. los resultados se reconstruyen a una fila por partido mediante `match_id`, usando `is_home` para asignar cada perspectiva al lado local (`h_`) o visitante (`a_`).

Las cuotas no participan en la construcción de FEATURES. Las estadísticas observadas del partido están presentes en `team_match_log`, pero el desplazamiento temporal garantiza que las correspondientes al propio partido `t` no contribuyan a sus predictores; únicamente pueden incorporarse al historial de encuentros posteriores. Si un equipo tuviera dos partidos con el mismo `kickoff_datetime`, el cálculo se detendría con un error explícito en lugar de elegir un orden arbitrario; con los datos de v0.1 esa situación no ocurre, como confirma V06.

### 20.2 Contenido de FEATURES

FEATURES tiene **1,900 filas × 30 columnas**, una por partido y en el mismo orden que CANONICAL:

| Bloque | Columnas | Número |
|---|---|---|
| Claves | `match_id`, `season`, `kickoff_datetime` | 3 |
| Local | `h_n_prev_season`, `h_ppg_season`, `h_gf_pg_season`, `h_ga_pg_season`, `h_ppg_last5`, `h_gf_pg_last5`, `h_ga_pg_last5`, `h_sot_pg_last5` | 8 |
| Visitante | las mismas ocho métricas con prefijo `a_` | 8 |
| Diferencias | `diff_x = h_x − a_x` para las siete métricas de rendimiento (todas salvo `n_prev_season`) | 7 |
| Targets | `result`, `goal_difference`, copiados de CANONICAL | 2 |
| Control | `is_modeling_eligible`, `feature_version` (`"0.1"`) | 2 |

Las definiciones de las ocho métricas y la lógica de las dos ventanas se explican en el Documento 01 (sección 11). Las features iniciales sin historial quedan vacías y no se imputan. V11 verificó la integridad referencial con CANONICAL: el mismo número de filas, cada `match_id` presente y único, y `result` y `goal_difference` idénticos a los de CANONICAL.

---

## 21. Reinicio por temporada

El contrato establece que en v0.1 no hay memoria entre temporadas. V12 lo verificó directamente sobre FEATURES:

- hay **100 combinaciones equipo-temporada** (20 equipos × 5 temporadas) y **cada una contiene exactamente 38 partidos**;
- en el primer partido de cada equipo en cada temporada, `n_prev_season` vale **0**;
- en los partidos siguientes, ordenados por `kickoff_datetime`, crece exactamente de uno en uno: **0, 1, 2, …, 37**;
- cuando `n_prev_season` vale 0, todas las features de tasa y ventana están **vacías**.

Si el historial arrastrara partidos de la temporada anterior, el primer partido de un equipo tendría `n_prev_season` mayor que cero, y V12 fallaría. Un test introduce exactamente ese defecto —eliminar el reinicio por temporada— y comprueba que se detecta.

---

## 22. Elegibilidad

La regla de elegibilidad vigente es:

```
is_modeling_eligible = min(h_n_prev_season, a_n_prev_season) ≥ 3
```

V13 verificó que el indicador coincide con la regla en todas las filas, que las filas elegibles no tienen ningún valor vacío en sus features, y que los conteos son los esperados:

| Temporada | Partidos elegibles |
|---|---|
| 2021/22 | 350 |
| 2022/23 | 350 |
| 2023/24 | 349 |
| 2024/25 | 350 |
| 2025/26 | 350 |
| **Total** | **1,749** |

Las **151 filas restantes no se eliminaron**: siguen en FEATURES, y por supuesto en CANONICAL, con `is_modeling_eligible = false`. Simplemente no son elegibles con el umbral actual.

El umbral de 3 sigue siendo **provisional** (P01). Como se conserva `n_prev_season`, podrá compararse con otros valores sin reconstruir ninguna capa, pero esa revisión corresponde al EDA y debe hacerse **solo con datos de desarrollo (2021/22–2024/25)**, conforme a D42. Las cifras de esta tabla son evidencia de ejecución, no un argumento a favor o en contra del umbral.

---

# Validación temporal

## 23. Prevención de data leakage en la implementación

El Documento 01 explicó las reglas temporales T1–T10. Aquí interesa otra pregunta: **¿cómo se comprobó que la implementación las cumple?** Para responderla conviene distinguir tres niveles.

- **La regla contractual** dice qué debe cumplirse. Por ejemplo, T1: las features de `t` solo pueden usar partidos con `kickoff_datetime` estrictamente anterior.
- **La implementación** es la forma concreta en que el código intenta cumplirla: agrupar por equipo y temporada, ordenar por `kickoff_datetime` y tomar como historial las posiciones 0 a *i* − 1.
- **La validación independiente** es la prueba que verifica el resultado sin dar por supuesto que la implementación es correcta.

El tercer nivel es el que aporta la evidencia. Revisar el código puede convencer a quien lo lee, pero no sustituye a una comprobación sobre los datos generados. Por eso la especificación establece que V14 y V15 son la defensa principal contra el data leakage y que ninguna de las dos puede sustituirse por una inspección visual.

| Regla | Cómo se cumple en la implementación | Qué la verifica |
|---|---|---|
| T1: historial estrictamente anterior | historial = posiciones 0 … *i* − 1 por `kickoff_datetime` | V14 (anteriores y simultáneos invariantes), V15 (filtrado explícito `<`) |
| T3: reinicio por temporada | agrupación por (temporada, equipo) | V12, V14 (otras temporadas invariantes) |
| T4: nada del propio partido | el partido *i* queda fuera de su historial | V14 (propio partido invariante), V15 |
| T5: única frontera `kickoff_datetime` | el orden se calcula por `kickoff_datetime`, no por posición en el archivo | V06, V15 (subconjunto de inicios simultáneos) |
| T6: acumulados desplazados sobre `team_match_log` | cálculo por equipo y reconstrucción por `match_id` | C01, C02, V14, V15 |
| T7: cuotas fuera de FEATURES | las cuotas no participan en la construcción de FEATURES | V17 (esquema exacto), tests de cuota infiltrada |
| T9: sin agregados de temporada completa | solo ventanas sobre el historial previo | V14, V15, test de agregado de temporada completa |

T2 se cumple porque el único conjunto de datos es la Premier League. T8 se refiere al ajuste de modelos y corresponde a una fase posterior. T10 solo se aplicará cuando exista alguna feature que dependa de partidos de otros equipos, lo que no ocurre en v0.1.

---

## 24. V14 — Test de perturbación

### 24.1 El principio

La idea de V14 es sencilla: si las features se calculan correctamente, cambiar lo que ocurrió en un partido solo puede afectar a lo que se sabe *después* de ese partido. Para comprobarlo, se toma un partido histórico `t`, se modifica de forma **internamente coherente** y se vuelven a calcular todas las features, que después se comparan con las originales.

La modificación cambia a la vez varios hechos del partido, de modo que sus efectos puedan rastrearse en distintas features:

- **se invierte el ganador o se rompe el empate**, aumentando los goles finales de uno de los dos equipos: si ganaba el local, el visitante pasa a tener un gol más que él; si ganaba el visitante, ocurre lo contrario; si había empate, el local suma un gol;
- **los goles al descanso no se modifican**, pero como los goles finales solo aumentan, se mantiene la condición de que no superen a los finales;
- **se suma un tiro y un tiro a puerta a cada equipo**;
- **se recalculan `goal_difference`, `result` y `dq_flags`** a partir de los nuevos valores, de modo que la fila siga siendo válida para las reglas de CANONICAL.

Así, la perturbación altera puntos, goles a favor y en contra y tiros a puerta de ambos equipos, que son exactamente los hechos de los que dependen las ocho métricas históricas.

Si la implementación es correcta, **no deben cambiar** (controles negativos):

- las features del propio partido `t`, porque su resultado no puede intervenir en su predicción;
- las features de los partidos anteriores o simultáneos a `t`;
- las features de los equipos no involucrados en `t`, incluso en partidos posteriores;
- las features de otras temporadas, por el reinicio.

Y **sí debe cambiar** (control positivo) alguna feature posterior de los equipos involucrados cuando exista un partido posterior al que afecte el cambio.

El control positivo es tan importante como los negativos. Un test que solo comprobara que "nada cambia" pasaría también con un pipeline averiado que ignorara los resultados por completo. Exigir que el cambio sí aparezca donde debe aparecer muestra que la prueba tiene capacidad real de detección.

### 24.2 Resultados

Se perturbaron **113 partidos**: una muestra reproducible de 100 elegidos al azar con semilla `42`, más los partidos con anomalías conocidas. Cada perturbación se comparó con el resto del conjunto de datos, lo que dio el siguiente volumen de controles:

| Control negativo | Comparaciones (fila × perturbación) | Resultado |
|---|---|---|
| Features del propio partido perturbado | 113 | sin cambios |
| Partidos anteriores o simultáneos | 20,940 | sin cambios |
| Partidos posteriores (lado no involucrado) | 21,887 | sin cambios |
| — de ellos, partidos posteriores sin ningún equipo involucrado | 17,661 | sin cambios |
| Partidos de otras temporadas | 171,760 | sin cambios |

En los partidos posteriores en los que juega uno de los equipos perturbados, solo se exige invariancia en el lado del equipo no involucrado. El lado del equipo involucrado puede cambiar legítimamente, y es ahí donde se evalúa el control positivo.

| Control positivo | Número |
|---|---|
| Aplicables (siguiente partido de un equipo involucrado dentro de la temporada) | 218 |
| Con cambio detectado | **218 / 218** |
| No aplicables (era el último partido del equipo en la temporada) | 8 |

En los 113 casos, ninguna feature que debía permanecer igual cambió, y en los 218 casos en que debía aparecer un cambio, apareció. Los ocho casos no aplicables corresponden a perturbaciones del último partido de un equipo en la temporada, que por el reinicio no tiene ningún partido posterior al que afectar.

Para confirmar que V14 detecta lo que debe detectar, los tests introducen un defecto concreto: eliminar el desplazamiento `shift(1)`, de modo que el propio partido entre en su historial. V14 lo detecta.

---

## 25. V15 — Oráculo independiente

### 25.1 Por qué es distinto de repetir el cálculo

Volver a ejecutar el mismo algoritmo y obtener el mismo resultado solo demuestra que el algoritmo es determinista, no que sea correcto: un error en la lógica se reproduciría idéntico. V15 sigue otro camino. Reconstruye cada feature con un procedimiento **independiente** del cálculo principal: no usa `team_match_log`, ni desplazamientos, ni funciones de ventana móvil. Para cada partido `t` y cada equipo, recorre CANONICAL y selecciona explícitamente los partidos de ese equipo en la misma temporada que cumplen

```
kickoff_datetime(m′) < kickoff_datetime(t)
```

Después calcula los promedios directamente sobre esa selección y compara cada valor con el que figura en FEATURES, con una tolerancia de `1e-9`.

Si el cálculo principal tuviera un error de desplazamiento, de ventana, de lado o de orden, el oráculo, que no comparte esa lógica, obtendría un valor distinto.

### 25.2 Qué partidos se evaluaron

En lugar de una muestra puramente aleatoria, la especificación exige cubrir primero los casos en los que es más probable que un error se manifieste:

| Subconjunto | Motivo | Partidos |
|---|---|---|
| (a) Primeros cinco partidos de cada equipo-temporada | zona de historial vacío o corto y de coincidencia entre ventanas | 251 |
| (b) Aplazamientos y partidos vecinos | equipos con distinto número de partidos jugados | 306 |
| (c) Inicios simultáneos | partidos que comparten `kickoff_datetime` con otro | 1,070 |
| (d) Anomalías conocidas | filas con `dq_flags` y la fila de Q02 | 14 |
| (e) Comienzo y final de temporada | `match_seq_season` 1–10 y 371–380 | 100 |
| **Conjunto obligatorio (unión de a–e)** | | **1,336** |
| Muestra aleatoria (semilla `42`) | cobertura general | 100 |
| **Total de partidos distintos evaluados** | | **1,436** |

Los subconjuntos se solapan, por eso la unión es menor que la suma. En total se compararon **34,464 valores** y todos coincidieron dentro de la tolerancia.

### 25.3 Alcance de la evidencia

V15 aporta una evidencia fuerte contra el data leakage y contra errores de ventana y desplazamiento, por dos motivos: la implementación de referencia es independiente y aplica literalmente la regla del contrato, y la selección de partidos se concentra en los casos frontera —inicios de temporada, aplazamientos, partidos simultáneos— donde esos errores suelen aparecer. Además, cubre 1,436 de los 1,900 partidos.

Esta evidencia tiene un alcance concreto. V15 demuestra que, en los partidos evaluados, FEATURES coincide con una reconstrucción independiente basada en la definición del contrato. No es una demostración matemática de que la implementación no contenga ningún error posible.

V15 reconstruyó de forma independiente 1,436 de los 1,900 partidos. Los 464 partidos que no forman parte de V15 siguen sujetos a las validaciones globales V12, V13 y V16, además de los controles de invariancia de V14 cuando resultan aplicables. Sin embargo, no fueron reconstruidos individualmente mediante el oráculo independiente. V14 y V15 son pruebas complementarias, no equivalentes: V14 comprueba cómo se propagan los cambios en un conjunto de partidos perturbados, y V15 recalcula desde cero los valores de un conjunto de partidos seleccionados.

Lo razonable es afirmar que el conjunto de pruebas no encontró ninguna violación de las reglas temporales y que sus controles positivos, junto con los defectos sintéticos de la suite de tests, indican que es capaz de detectar los errores típicos de desplazamiento y ventana.

---

## 26. V16 y V17

### V16 — Identidad de diferencias

V16 verificó que, para las siete métricas, cada `diff_x` es exactamente `h_x − a_x`, y que está vacía cuando alguno de los dos lados lo está. Se comprobaron **12,950 diferencias no vacías** con igualdad exacta del valor de coma flotante, sin tolerancia. V16 verificó también que `feature_version` vale exactamente `"0.1"` en todas las filas.

### V17 — Esquema normativo de FEATURES

V17 es para FEATURES lo que V02 es para CANONICAL. Comprobó:

- la cabecera exacta, con las **30 columnas** en el orden del contrato;
- el tipo lógico, la nulabilidad y el dominio de cada columna: `n_prev_season` entero entre 0 y 37 y nunca vacío, `ppg_*` entre 0 y 3, `is_modeling_eligible` como `true`/`false` y `feature_version` leído como texto;
- valores ausentes como campo vacío, sin ningún literal `NaN`, `NA`, `NULL` o `None`;
- números decimales sin redondear y con ida y vuelta exacta: leer y volver a escribir un valor produce la misma cadena;
- la regla D43 de decimales con parte entera;
- UTF-8 sin BOM, LF y el mismo orden de filas que CANONICAL;
- idempotencia byte a byte;
- **0 valores en notación científica**.

Al fijar el conjunto exacto de columnas, V17 también impide que entre en FEATURES cualquier columna no prevista, incluida una cuota de mercado.

---

# Validación general

## 27. Sistema de validaciones V01–V17

Las diecisiete validaciones del contrato no son independientes entre sí. Forman varias capas de defensa, de modo que un mismo tipo de error suele tener más de una oportunidad de ser detectado.

| Grupo | Validaciones | Objetivo |
|---|---|---|
| Integridad RAW | V01, antes y después de cada checkpoint | demostrar que los datos originales no cambiaron |
| Esquema y serialización | V02 (CANONICAL), V17 (FEATURES) | asegurar columnas, tipos, formatos e idempotencia exactos |
| Trazabilidad | V03 | comprobar campo por campo que CANONICAL procede de RAW |
| Identidad | V04, V07 | identificadores únicos, deterministas y correctamente mapeados |
| Calendario | V05, V06 | temporadas completas, emparejamientos únicos, fechas y orden coherentes |
| Rangos y targets | V08, V09 | valores posibles y relaciones exactas entre goles y resultado |
| Calidad | V10 | avisos de calidad exactos fila por fila |
| Referencialidad | V11 | correspondencia uno a uno entre FEATURES y CANONICAL |
| Temporalidad | V12, V13 | reinicio por temporada y elegibilidad correctos |
| Leakage | V14, V15 | detectar uso indebido de información del propio partido o del futuro mediante perturbación y reconstrucción independiente |
| Coherencia de features | V16 | diferencias exactas y versión correcta |
| Determinismo | A11, B01, C03 y la idempotencia de V02 y V17 | mismas entradas, mismos bytes |

Todas son **bloqueantes**: un solo fallo invalida el dataset. Una validación también debe demostrar que es capaz de fallar ante un defecto sintético. La especificación exige formalmente esta autoprueba para V03 y la recomienda para las demás validaciones bloqueantes. La suite de tests extiende este principio e introduce defectos sintéticos para comprobar numerosas validaciones adicionales (sección 28).

Las validaciones propias de cada checkpoint completan este sistema: A01–A11 para la fidelidad de INTERIM; B00 y C00 como puertas de entrada que solo permiten avanzar si la capa anterior es exactamente la aprobada; B01 y C03 para el determinismo; y C01–C02 para `team_match_log`.

---

## 28. Tests automatizados

Además de las validaciones que se ejecutan sobre los datasets generados, el proyecto incluye una suite de tests automatizados en `tests/`. La inspección directa de la suite muestra **104 tests**: 34 en `test_checkpoint_a.py`, 39 en `test_checkpoint_b.py` y 31 en `test_checkpoint_c.py`.

Las validaciones y los tests cumplen funciones complementarias. Las validaciones comprueban que *los datos producidos* cumplen el contrato. Los tests comprueban que *las validaciones y el código* se comportan como deben: que el pipeline real pasa todas las pruebas y que, cuando se introduce deliberadamente un defecto, la prueba correspondiente lo detecta. Un test típico construye una versión defectuosa del dataset, o sustituye una pieza del cálculo por una versión errónea, y verifica que alguna validación falla.

Los errores que la suite busca detectar pueden agruparse así:

- **Leakage temporal:** el propio partido incluido en su historial (eliminar `shift(1)`), tiros a puerta del propio partido filtrados a sus features, un partido futuro que contamina uno anterior y agregados de la temporada completa.
- **Lógica de las features:** ausencia de reinicio por temporada, ventana de seis partidos en lugar de cinco, ventana tomada sin ordenar, tiros a puerta del lado equivocado, puntos mal calculados, local y visitante intercambiados, imputación con cero del primer partido y diferencias mal calculadas.
- **Elegibilidad y targets:** umbral cambiado, indicador invertido y target alterado.
- **Integridad de filas:** filas omitidas o duplicadas, `match_id` duplicado, orden físico incorrecto y emparejamientos duplicados u omitidos.
- **Mercado:** columnas de cuotas adicionales y valores de mercado infiltrados como feature.
- **Esquema y serialización:** columnas de más o de menos, columnas renombradas, decimales con parte entera escritos sin decimal, decimales redondeados, literales `NaN` o `None`, BOM, CRLF y versión incorrecta.
- **Trazabilidad e identidad:** cuotas o estadísticas tomadas de otro partido, `source_row` incorrecto, identificadores intercambiados, confusión día/mes, `match_id` incorrecto y anomalía corregida indebidamente.
- **RAW e INTERIM:** un byte modificado en una copia de RAW, números "arreglados" en silencio, escritura en RAW, valores imputados y árbitro sin `strip()`.
- **`team_match_log`:** filas omitidas o perspectivas que no son espejo.

La amplitud de esta lista importa menos que su lógica: cada tipo de error realista tiene un test que lo provoca y comprueba que no pasa inadvertido.

---

## 29. Determinismo, idempotencia y reproducibilidad

Los tres conceptos están relacionados, pero no son lo mismo:

- **Determinismo:** ejecutar la misma transformación dos veces sobre la misma entrada produce exactamente la misma salida.
- **Idempotencia:** leer un archivo ya generado con los tipos de su esquema y volver a escribirlo produce el mismo archivo. Garantiza que el formato es estable y que la serialización no depende de la ejecución que lo creó.
- **Reproducibilidad:** en un entorno compatible, partiendo de la misma instantánea RAW, el mismo código y la misma configuración, el pipeline puede regenerar los artefactos y contrastarlos mediante sus SHA-256.

La evidencia de cada propiedad es concreta:

| Capa | Evidencia |
|---|---|
| RAW | V01 antes y después de los tres checkpoints: seis SHA-256 sin cambios |
| INTERIM | A11: determinismo e idempotencia byte a byte; SHA-256 sin cambios durante B y C |
| CANONICAL | B01: dos construcciones con el mismo SHA-256; V02: idempotencia; sin cambios durante C |
| team_match_log | C03: dos construcciones con el mismo SHA-256 |
| FEATURES | C03: dos construcciones con el mismo SHA-256; V17: idempotencia |

Varias decisiones del contrato hacen posibles estas propiedades:

- **El orden determinista de las filas**: temporada y `source_row` en INTERIM; `kickoff_datetime` y `match_id` en CANONICAL y FEATURES; equipo y `kickoff_datetime` en `team_match_log`. Sin un orden fijo, dos ejecuciones podrían producir las mismas filas en distinto orden y archivos distintos.
- **La serialización normativa**: codificación, fin de línea, representación de nulos, fechas y booleanos fijados por el contrato.
- **La regla D43**, que elimina la ambigüedad entre `4` y `4.0` para un mismo valor decimal.
- **SHA-256**, que convierte la afirmación "los archivos son iguales" en algo verificable por cualquiera.
---

# Cierre

## 30. Artefactos finales congelados

| Artefacto | Ruta | Dimensiones | SHA-256 |
|---|---|---|---|
| INTERIM | `data/interim/pl_interim_v0.1.csv` | 1,900 × 166 | `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad` |
| CANONICAL | `data/canonical/pl_canonical_v0.1.csv` | 1,900 × 42 | `06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1` |
| team_match_log | `data/interim/team_match_log_v0.1.csv` | 3,800 × 10 | `0032af2965604d556b337a5d8c1f4ce6b5ac95ca931d82b99651a4f00c03ab02` |
| FEATURES | `data/features/pl_features_v0.1.csv` | 1,900 × 30 | `a18c47888a38a80585ae97930f81a4ad6fc4497315af63ef05f284352ca9b356` |

La decisión **D44** del Decision Log aprueba los tres checkpoints y congela estos cuatro artefactos como versión v0.1. Cualquier modificación posterior, ya sea de los datos, de las reglas que los producen o del código que los genera, exige una **nueva versión explícita y registrada**. Los informes de validación de cada checkpoint, en `reports/checkpoint_a/`, `reports/checkpoint_b/` y `reports/checkpoint_c/`, quedan como evidencia del estado en que se aprobaron.

---

## 31. Qué quedó fuera del pipeline

Para delimitar correctamente el estado del proyecto, conviene dejar explícito lo que **todavía no se ha realizado**:

- el análisis exploratorio formal (EDA);
- la selección definitiva de features;
- la decisión final sobre el burn-in;
- la decisión final sobre la redundancia entre las ventanas *season* y *last5*;
- el entrenamiento de cualquier modelo;
- el ajuste de hiperparámetros;
- la calibración de probabilidades;
- la evaluación final sobre la temporada 2025/26;
- la comparación entre modelo y mercado, incluida la conversión de cuotas en probabilidades implícitas;
- el diseño completo del esquema SQL de la base de datos relacional;
- la aplicación en Java.

La partición entre entrenamiento, validación y prueba también sigue siendo provisional (P06).

---

## 32. Riesgos y cuestiones transferidas al EDA

El pipeline deja varias cuestiones abiertas que pasan a la siguiente fase. Este documento solo las registra; no las resuelve.

**M3 — Redundancia entre *season* y *last5*.** Mientras `n_prev_season` ≤ 5, cada feature *last5* es idéntica a su versión de temporada. La correlación entre ambas familias estará inflada en esas filas, y el EDA deberá medirla, por ejemplo con VIF y estratificando por `n_prev_season`.

**M1 — Representación en modelos lineales.** FEATURES conserva `h_x`, `a_x` y `diff_x`. Ningún modelo lineal podrá incluir las tres a la vez por la dependencia lineal perfecta; cada modelo deberá declarar su subconjunto de features.

**Q01 — Impacto de `AST = 9` / `AS = 8`.** El valor imposible del partido Newcastle – West Ham de 2021/22 se propaga a `sot_pg_last5` de West Ham en sus partidos posteriores dentro de la ventana. El EDA deberá evaluar si su impacto justifica algún tratamiento.

**P01 — Burn-in provisional.** El umbral de 3 partidos previos podrá compararse con alternativas a partir de la estabilidad de las features.

**P02 — Ventana *last5* provisional.** Su longitud y su redundancia con la ventana de temporada se evaluarán en el EDA.

**D42 — Disciplina sobre 2025/26.** Cualquier decisión de diseño que surja de los puntos anteriores —features, burn-in, transformaciones, modelos o hiperparámetros— deberá tomarse **únicamente con datos de desarrollo (2021/22–2024/25)**. La temporada 2025/26 solo puede usarse para análisis descriptivos con fines de documentación.

---

## 33. Estado final del pipeline

Al cierre de esta fase:

- el **Checkpoint A** (RAW → INTERIM) fue aprobado;
- el **Checkpoint B** (INTERIM → CANONICAL) fue aprobado;
- el **Checkpoint C** (CANONICAL → team_match_log → FEATURES) fue aprobado;
- las validaciones **V01–V17** están en PASS, junto con los controles propios de cada checkpoint;
- RAW permaneció intacto durante todo el proceso;
- los cuatro artefactos fueron congelados mediante **D44**;
- **no existe todavía ningún modelo entrenado**.

FEATURES constituye la entrada validada para las fases analíticas siguientes: el análisis exploratorio, la regresión lineal de Matemáticas, los modelos de clasificación de Machine Learning y los experimentos de Complejidad Computacional. CANONICAL, por su parte, queda como la fuente de hechos observados para el análisis estadístico y para el futuro diseño de la base de datos.

El estado formal de la fase es:

**SCOPE DATA PIPELINE v0.1 — COMPLETED / FROZEN**

---

## Anexo A — Manifiesto RAW

Rutas relativas a la raíz de `SCOPE/`, según `docs/data_dictionary/raw_manifest_v0.1.csv`. Los seis SHA-256 se verificaron antes y después de cada checkpoint.

| Archivo | Ruta | Bytes | Fin de línea | SHA-256 |
|---|---|---|---|---|
| `PL_2021-2022_raw.csv` | `Premier_League_data_raw_csv/PL_2021-2022_raw.csv` | 175,363 | CRLF | `335afcbabeb2939fa10ab39ba3e8215072d0b577cb8d0705c1e44c56e934e703` |
| `PL_2022-2023_raw.csv` | `Premier_League_data_raw_csv/PL_2022-2023_raw.csv` | 176,180 | CRLF | `8442792d3b614c94ea3cf381bd2736805889cc1713169035368fff19c3d02380` |
| `PL_2023-2024_raw.csv` | `Premier_League_data_raw_csv/PL_2023-2024_raw.csv` | 172,196 | CRLF | `b2e057b0ed959f198b0f63d2391c01239f3608e6de5db68edab3f88e04d07ff3` |
| `PL_2024-2025_raw.csv` | `Premier_League_data_raw_csv/PL_2024-2025_raw.csv` | 197,110 | CRLF | `d0c8ce4a96d886cf60cf101f570f4a3893844226f91c7bd769eb568c49edbfa4` |
| `PL_2025-2026_raw.csv` | `Premier_League_data_raw_csv/PL_2025-2026_raw.csv` | 203,438 | CRLF | `3e3a8352f9ada6789c508d6ca184424421fed56a30400904a4a327c583407e62` |
| `notes.txt` | `Documentacion de datos/notes.txt` | 7,686 | CRLF | `6ecd41a98ad2751372817e7e6f1709bfeb433c53dd9aeda330fd926a5471452d` |
