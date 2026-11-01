# CHECKPOINT A — RAW → INTERIM: informe de validación

Contrato: SCOPE Data Contract v0.1 (FROZEN FOR IMPLEMENTATION)

Salida: `data/interim/pl_interim_v0.1.csv` — 1140220 bytes — SHA-256 `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad`

## Resultado por prueba

| ID | Estado | Prueba |
|---|---|---|
| V01 | **PASS** | Integridad RAW por SHA-256 (antes) |
| A01 | **PASS** | Formato de archivo INTERIM (UTF-8 sin BOM, LF, sin literales nulos) |
| A02 | **PASS** | Esquema: 4 columnas de trazabilidad + unión de 162 columnas RAW |
| A03 | **PASS** | Conteos: 5 temporadas, 380 filas por temporada, 1,900 en total |
| A04 | **PASS** | Trazabilidad 1:1 (season, source_name, source_file, source_row) |
| A05 | **PASS** | Fidelidad celda a celda con RAW (re-lectura independiente) |
| A06 | **PASS** | Limpieza superficial: solo strip() en las celdas documentadas (Q02) |
| A07 | **PASS** | Nulos por temporada y columna: INTERIM == RAW; ausentes = 100 % vacíos |
| A08 | **PASS** | Anomalías conocidas conservadas sin corregir (Q01 y conteos de dq_flags) |
| A09 | **PASS** | Sin filas duplicadas por el proceso |
| A10 | **PASS** | Tipado y serialización estable de cada celda |
| A11 | **PASS** | Determinismo e idempotencia byte a byte |
| V01 | **PASS** | Integridad RAW por SHA-256 (después) |

**Resultado global: PASS**

## Detalle

### V01 — Integridad RAW por SHA-256 (antes) — PASS
- PL_2021-2022_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=True, CRLF, 2021-08-13..2022-05-22
- PL_2022-2023_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2022-08-05..2023-05-28
- PL_2023-2024_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2023-08-11..2024-05-19
- PL_2024-2025_raw.csv: sha256 OK=True, filas=380, columnas=120, BOM=True, CRLF, 2024-08-16..2025-05-25
- PL_2025-2026_raw.csv: sha256 OK=True, filas=380, columnas=132, BOM=True, CRLF, 2025-08-15..2026-05-24

### A01 — Formato de archivo INTERIM (UTF-8 sin BOM, LF, sin literales nulos) — PASS

### A02 — Esquema: 4 columnas de trazabilidad + unión de 162 columnas RAW — PASS
- 2021-2022: 106 columnas RAW
- 2022-2023: 106 columnas RAW
- 2023-2024: 106 columnas RAW
- 2024-2025: 120 columnas RAW
- 2025-2026: 132 columnas RAW
- INTERIM: 166 columnas = 4 trazabilidad + 162 RAW; comunes a 5 temporadas: 88

### A03 — Conteos: 5 temporadas, 380 filas por temporada, 1,900 en total — PASS
- 2021-2022: 380 filas
- 2022-2023: 380 filas
- 2023-2024: 380 filas
- 2024-2025: 380 filas
- 2025-2026: 380 filas
- Total: 1900 filas

### A04 — Trazabilidad 1:1 (season, source_name, source_file, source_row) — PASS

### A05 — Fidelidad celda a celda con RAW (re-lectura independiente) — PASS
- Celdas RAW comparadas: 216600

### A06 — Limpieza superficial: solo strip() en las celdas documentadas (Q02) — PASS
- PL_2023-2024_raw.csv source_row=357 Referee: 'J Gillett ' -> 'J Gillett'

### A07 — Nulos por temporada y columna: INTERIM == RAW; ausentes = 100 % vacíos — PASS
- Pares (temporada, columna) ausentes representados como vacío: 240

### A08 — Anomalías conocidas conservadas sin corregir (Q01 y conteos de dq_flags) — PASS
- Conteos recalculados sobre INTERIM: {'HST_GT_HS': 0, 'AST_GT_AS': 1, 'GOALS_GT_SOT': 12}

### A09 — Sin filas duplicadas por el proceso — PASS

### A10 — Tipado y serialización estable de cada celda — PASS

### A11 — Determinismo e idempotencia byte a byte — PASS

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

## Limpieza superficial aplicada (strip)

- `PL_2023-2024_raw.csv` source_row=357 `Referee`: 'J Gillett ' → 'J Gillett'
