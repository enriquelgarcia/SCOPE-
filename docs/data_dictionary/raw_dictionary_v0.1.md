# Diccionario RAW — Football-Data (Premier League) v0.1

> Documento de referencia de SCOPE Data Contract v0.1. La versión legible por máquina es `raw_dictionary_v0.1.csv` (misma carpeta). Se generó leyendo los cinco CSV RAW (solo lectura) y `Documentacion de datos/notes.txt`.

## 1. Alcance

- Fuente: football-data.co.uk, división `E0`. Cinco temporadas: 2021-2022, 2022-2023, 2023-2024, 2024-2025, 2025-2026.
- Columnas distintas (unión): **162**. Presentes en las cinco temporadas: **88**.

| Temporada | Filas | Columnas | BOM |
|---|---|---|---|
| 2021-2022 | 380 | 106 | sí |
| 2022-2023 | 380 | 106 | no |
| 2023-2024 | 380 | 106 | no |
| 2024-2025 | 380 | 120 | sí |
| 2025-2026 | 380 | 132 | sí |

## 2. Estados de documentación (`doc_status`)

| Estado | Significado | Columnas |
|---|---|---|
| `documented` | Abreviatura y significado figuran explícitamente en `notes.txt`. | 89 |
| `documented_by_rule` | Cuota de cierre de 1X2: `notes.txt` indica que se obtiene añadiendo una `C` tras la abreviatura del bookmaker/Max/Avg (ejemplo del propio archivo: `B365CH`). | 48 |
| `inferred_by_rule_extension` | Cierre de O/U 2.5 o de Asian handicap de un mercado documentado. La regla de la `C` se enuncia en la sección de cuotas 1X2; aplicarla a O/U y AH es una **extensión inferida**. | 16 |
| `inferred_not_documented` | **No documentada en `notes.txt`.** El significado se deduce solo por el patrón del nombre y debe tratarse como hipótesis. | 9 |

### Columnas inferidas y no documentadas (marca explícita)

`AHCh`, `BFE>2.5`, `BFE<2.5`, `BFEAHH`, `BFEAHA`, `BFEC>2.5`, `BFEC<2.5`, `BFECAHH`, `BFECAHA`

Ninguna de ellas se usa en CANONICAL v0.1. Quedan solo en INTERIM.

### Columnas con regla extendida (inferidas)

`B365C>2.5`, `B365C<2.5`, `PC>2.5`, `PC<2.5`, `MaxC>2.5`, `MaxC<2.5`, `AvgC>2.5`, `AvgC<2.5`, `B365CAHH`, `B365CAHA`, `PCAHH`, `PCAHA`, `MaxCAHH`, `MaxCAHA`, `AvgCAHH`, `AvgCAHA`

## 3. Discrepancias entre `notes.txt` y los archivos

1. **Formato de fecha:** `notes.txt` dice `dd/mm/yy`; los cinco archivos usan `dd/mm/yyyy` (10 caracteres). Se parsea con `%d/%m/%Y`.
2. **Zona horaria de `Time`:** no está documentada. Se conserva como hora local sin zona.
3. **Alias:** `notes.txt` menciona `HG`, `AG`, `Res`, `PH`, `PD`, `PA` como alias; ninguno aparece en los archivos (solo `FTHG`, `FTAG`, `FTR`, `PSH`, `PSD`, `PSA`).
4. **BOM UTF-8:** presente en 2021-22, 2024-25 y 2025-26; ausente en 2022-23 y 2023-24 (ver manifiesto).

## 4. Columnas por familia

| Familia | Columnas | En las 5 temporadas | Parciales |
|---|---|---|---|
| `identification` | 1 | 1 | 0 |
| `datetime` | 2 | 2 | 0 |
| `participants` | 2 | 2 | 0 |
| `result_full_time` | 3 | 3 | 0 |
| `result_half_time` | 3 | 3 | 0 |
| `referee` | 1 | 1 | 0 |
| `match_statistics` | 12 | 12 | 0 |
| `odds_1x2_pre` | 48 | 15 | 33 |
| `odds_ou25_pre` | 10 | 8 | 2 |
| `odds_ah_pre` | 11 | 9 | 2 |
| `odds_1x2_close` | 48 | 15 | 33 |
| `odds_ou25_close` | 10 | 8 | 2 |
| `odds_ah_close` | 11 | 9 | 2 |

## 5. Cuotas por bookmaker: presencia por temporada

Se resume por prefijo (cuota 1X2 pre-closing) para ver cuándo aparece o desaparece cada bookmaker. El detalle completo está en el CSV.

| Prefijo | 2021-2022 | 2022-2023 | 2023-2024 | 2024-2025 | 2025-2026 |
|---|---|---|---|---|---|
| `1XB` | — | — | — | ✓ | — |
| `B365` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `BF` | — | — | — | ✓ | — |
| `BFD` | — | — | — | — | ✓ |
| `BMGM` | — | — | — | — | ✓ |
| `BV` | — | — | — | — | ✓ |
| `BW` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `CL` | — | — | — | — | ✓ |
| `IW` | ✓ | ✓ | ✓ | — | — |
| `LB` | — | — | — | — | ✓ |
| `PS` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `VC` | ✓ | ✓ | ✓ | — | — |
| `WH` | ✓ | ✓ | ✓ | ✓ | — |
| `BFE` | — | — | — | ✓ | ✓ |
| `Max` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `Avg` | ✓ | ✓ | ✓ | ✓ | ✓ |

Verificado: en las cinco temporadas tienen **cero nulos** las cuotas 1X2 de `B365`, `Max` y `Avg` (pre-closing y cierre), mientras que `BW`, `PS` y `P` (O/U, AH) presentan nulos (p. ej. `PS*` vacío en 170 filas de 2025-26). `Avg*` es el agregado elegido para CANONICAL v0.1 por ser el consenso de mercado (no por ser el único completo); `B365*` y `Max*` permanecen en INTERIM.

## 6. Documentadas en `notes.txt` pero ausentes de las cinco temporadas

`Attendance`, `HHW`, `AHW`, `HFKC`, `AFKC`, `HO`, `AO`, `HBP`, `ABP`, `HG`, `AG`, `Res`, `PH`, `PD`, `PA`, bookmakers `BS`, `GB`, `PP`, `SK`, `SO`, `SB`, `SJ`, `SY`, familia `Bb*` (BetBrain) y columnas `GB*`, `LBAH*`, `GBAH*`, `B365AH` (tamaño de handicap).

_(Verificado: ninguna de estas columnas existe en los CSV.)_

## 7. Mapeo a CANONICAL v0.1

Solo los campos con destino CANONICAL; el resto permanece únicamente en INTERIM.

| Columna RAW | Campo(s) CANONICAL |
|---|---|
| `Div` | `source_div; competition_code` |
| `Date` | `match_date; kickoff_datetime` |
| `Time` | `kickoff_time; kickoff_datetime` |
| `HomeTeam` | `home_team_id; home_team_name` |
| `AwayTeam` | `away_team_id; away_team_name` |
| `FTHG` | `home_goals` |
| `FTAG` | `away_goals` |
| `FTR` | `result` |
| `HTHG` | `ht_home_goals` |
| `HTAG` | `ht_away_goals` |
| `HTR` | `ht_result` |
| `Referee` | `referee` |
| `HS` | `home_shots` |
| `AS` | `away_shots` |
| `HST` | `home_shots_on_target` |
| `AST` | `away_shots_on_target` |
| `HF` | `home_fouls` |
| `AF` | `away_fouls` |
| `HC` | `home_corners` |
| `AC` | `away_corners` |
| `HY` | `home_yellow_cards` |
| `AY` | `away_yellow_cards` |
| `HR` | `home_red_cards` |
| `AR` | `away_red_cards` |
| `AvgH` | `mkt_avg_pre_home` |
| `AvgD` | `mkt_avg_pre_draw` |
| `AvgA` | `mkt_avg_pre_away` |
| `AvgCH` | `mkt_avg_close_home` |
| `AvgCD` | `mkt_avg_close_draw` |
| `AvgCA` | `mkt_avg_close_away` |
