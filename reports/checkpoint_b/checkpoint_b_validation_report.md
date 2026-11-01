# CHECKPOINT B — INTERIM → CANONICAL: informe de validación

Contrato: SCOPE Data Contract v0.1 (FROZEN FOR IMPLEMENTATION)

- INTERIM aprobado: `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad`
- INTERIM antes / después: `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad` / `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad`
- CANONICAL: `data/canonical/pl_canonical_v0.1.csv` — SHA-256 `06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1`

## Resultado por prueba

| ID | Estado | Prueba |
|---|---|---|
| V01 | **PASS** | Integridad RAW por SHA-256 (antes) |
| B00 | **PASS** | Entrada: INTERIM existe y su SHA-256 es el aprobado en CHECKPOINT A |
| B01 | **PASS** | Determinismo: dos construcciones desde el mismo INTERIM dan los mismos bytes |
| V02 | **PASS** | CANONICAL: esquema normativo (4.9), serialización (4.0) e idempotencia |
| V03 | **PASS** | Trazabilidad completa: comparación campo por campo con RAW re-leído |
| V04 | **PASS** | Unicidad de match_id y de la clave natural; regla de construcción |
| V05 | **PASS** | Conteos y calendario (380/temporada, 20 equipos, 19+19, parejas únicas) |
| V06 | **PASS** | Fechas y orden temporal (formato ISO, RAW estricto, ventana, seq, hipótesis 6.1) |
| V07 | **PASS** | Equipos: (fuente, alias RAW) -> team_id -> display_name exactos |
| V08 | **PASS** | Rangos: enteros ≥ 0, HT ≤ FT, cuotas > 1.0, ht_result coherente |
| V09 | **PASS** | Targets: goal_difference = home − away; result = sign(goal_difference) |
| V10 | **PASS** | dq_flags: conjunto exacto por fila, catálogo, orden; conteos y localizaciones |
| V01 | **PASS** | Integridad RAW por SHA-256 (después) |

**Resultado global: PASS**

## Detalle

### V01 — Integridad RAW por SHA-256 (antes) — PASS
- PL_2021-2022_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=True, CRLF, 2021-08-13..2022-05-22
- PL_2022-2023_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2022-08-05..2023-05-28
- PL_2023-2024_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2023-08-11..2024-05-19
- PL_2024-2025_raw.csv: sha256 OK=True, filas=380, columnas=120, BOM=True, CRLF, 2024-08-16..2025-05-25
- PL_2025-2026_raw.csv: sha256 OK=True, filas=380, columnas=132, BOM=True, CRLF, 2025-08-15..2026-05-24

### B00 — Entrada: INTERIM existe y su SHA-256 es el aprobado en CHECKPOINT A — PASS
- A01–A11 sobre INTERIM: A01 PASS, A02 PASS, A03 PASS, A04 PASS, A05 PASS, A06 PASS, A07 PASS, A08 PASS, A09 PASS, A10 PASS, A11 PASS

### B01 — Determinismo: dos construcciones desde el mismo INTERIM dan los mismos bytes — PASS
- SHA-256 construcción 1 = 06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1
- SHA-256 construcción 2 = 06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1

### V02 — CANONICAL: esquema normativo (4.9), serialización (4.0) e idempotencia — PASS
- 1900 filas × 42 columnas

### V03 — Trazabilidad completa: comparación campo por campo con RAW re-leído — PASS
- Filas comparadas: 1900; campos por fila trasladados desde RAW: 34

### V04 — Unicidad de match_id y de la clave natural; regla de construcción — PASS

### V05 — Conteos y calendario (380/temporada, 20 equipos, 19+19, parejas únicas) — PASS
- 2021-2022: 380 partidos, 20 equipos, 380 parejas
- 2022-2023: 380 partidos, 20 equipos, 380 parejas
- 2023-2024: 380 partidos, 20 equipos, 380 parejas
- 2024-2025: 380 partidos, 20 equipos, 380 parejas
- 2025-2026: 380 partidos, 20 equipos, 380 parejas

### V06 — Fechas y orden temporal (formato ISO, RAW estricto, ventana, seq, hipótesis 6.1) — PASS
- 2021-2022: partidos con kickoff compartido con otro partido: 213
- 2022-2023: partidos con kickoff compartido con otro partido: 208
- 2023-2024: partidos con kickoff compartido con otro partido: 204
- 2024-2025: partidos con kickoff compartido con otro partido: 227
- 2025-2026: partidos con kickoff compartido con otro partido: 218

### V07 — Equipos: (fuente, alias RAW) -> team_id -> display_name exactos — PASS
- team_id distintos en CANONICAL: 27

### V08 — Rangos: enteros ≥ 0, HT ≤ FT, cuotas > 1.0, ht_result coherente — PASS

### V09 — Targets: goal_difference = home − away; result = sign(goal_difference) — PASS
- Distribución de result: {'A': 607, 'D': 454, 'H': 839}

### V10 — dq_flags: conjunto exacto por fila, catálogo, orden; conteos y localizaciones — PASS
- Conteos: {'HST_GT_HS': 0, 'AST_GT_AS': 1, 'GOALS_GT_SOT': 12}

### V01 — Integridad RAW por SHA-256 (después) — PASS
- PL_2021-2022_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=True, CRLF, 2021-08-13..2022-05-22
- PL_2022-2023_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2022-08-05..2023-05-28
- PL_2023-2024_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2023-08-11..2024-05-19
- PL_2024-2025_raw.csv: sha256 OK=True, filas=380, columnas=120, BOM=True, CRLF, 2024-08-16..2025-05-25
- PL_2025-2026_raw.csv: sha256 OK=True, filas=380, columnas=132, BOM=True, CRLF, 2025-08-15..2026-05-24

## SHA-256 RAW antes / después

| relative_path | antes | después | igual |
|---|---|---|---|
| `Documentacion de datos/notes.txt` | `6ecd41a98ad2751372817e7e6f1709bfeb433c53dd9aeda330fd926a5471452d` | `6ecd41a98ad2751372817e7e6f1709bfeb433c53dd9aeda330fd926a5471452d` | sí |
| `Premier_League_data_raw_csv/PL_2021-2022_raw.csv` | `335afcbabeb2939fa10ab39ba3e8215072d0b577cb8d0705c1e44c56e934e703` | `335afcbabeb2939fa10ab39ba3e8215072d0b577cb8d0705c1e44c56e934e703` | sí |
| `Premier_League_data_raw_csv/PL_2022-2023_raw.csv` | `8442792d3b614c94ea3cf381bd2736805889cc1713169035368fff19c3d02380` | `8442792d3b614c94ea3cf381bd2736805889cc1713169035368fff19c3d02380` | sí |
| `Premier_League_data_raw_csv/PL_2023-2024_raw.csv` | `b2e057b0ed959f198b0f63d2391c01239f3608e6de5db68edab3f88e04d07ff3` | `b2e057b0ed959f198b0f63d2391c01239f3608e6de5db68edab3f88e04d07ff3` | sí |
| `Premier_League_data_raw_csv/PL_2024-2025_raw.csv` | `d0c8ce4a96d886cf60cf101f570f4a3893844226f91c7bd769eb568c49edbfa4` | `d0c8ce4a96d886cf60cf101f570f4a3893844226f91c7bd769eb568c49edbfa4` | sí |
| `Premier_League_data_raw_csv/PL_2025-2026_raw.csv` | `3e3a8352f9ada6789c508d6ca184424421fed56a30400904a4a327c583407e62` | `3e3a8352f9ada6789c508d6ca184424421fed56a30400904a4a327c583407e62` | sí |
