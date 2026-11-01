# CHECKPOINT C — CANONICAL → team_match_log → FEATURES: informe de validación

Contrato: SCOPE Data Contract v0.1 (FROZEN FOR IMPLEMENTATION)

- INTERIM aprobado / después: `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad` / `cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad`
- CANONICAL aprobado / después: `06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1` / `06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1`
- team_match_log: `data/interim/team_match_log_v0.1.csv` — SHA-256 `0032af2965604d556b337a5d8c1f4ce6b5ac95ca931d82b99651a4f00c03ab02`
- FEATURES: `data/features/pl_features_v0.1.csv` — SHA-256 `a18c47888a38a80585ae97930f81a4ad6fc4497315af63ef05f284352ca9b356`

## Resultado por prueba

| ID | Estado | Prueba |
|---|---|---|
| V01 | **PASS** | Integridad RAW por SHA-256 (antes) |
| C00 | **PASS** | Entrada: INTERIM y CANONICAL aprobados; V02–V10 en modo lectura |
| C03 | **PASS** | Determinismo: dos construcciones dan bytes idénticos (team_match_log y FEATURES) |
| C01 | **PASS** | team_match_log: formato, cabecera, 2 × partidos filas, orden (team_id, kickoff) |
| C02 | **PASS** | team_match_log: espejo local/visitante y valores derivados solo de CANONICAL |
| V11 | **PASS** | Integridad referencial FEATURES ↔ CANONICAL |
| V12 | **PASS** | Reinicio de temporada: n_prev_season 0,1,…,37 por equipo-temporada; vacíos si 0 |
| V13 | **PASS** | Elegibilidad: min(h_n, a_n) ≥ 3; elegibles sin vacíos; conteos |
| V14 | **PASS** | Perturbación coherente: invariantes (negativos) y cambio posterior (positivo) |
| V15 | **PASS** | Oráculo independiente (filtrado explícito kickoff < t) sobre conjunto obligatorio + muestra |
| V16 | **PASS** | diff_x == h_x − a_x (vacío si algún lado vacío); feature_version = '0.1' |
| V17 | **PASS** | FEATURES: esquema normativo (5.4), serialización (4.0, D43) e idempotencia |
| V01 | **PASS** | Integridad RAW por SHA-256 (después) |

**Resultado global: PASS**

## Detalle

### V01 — Integridad RAW por SHA-256 (antes) — PASS
- PL_2021-2022_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=True, CRLF, 2021-08-13..2022-05-22
- PL_2022-2023_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2022-08-05..2023-05-28
- PL_2023-2024_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2023-08-11..2024-05-19
- PL_2024-2025_raw.csv: sha256 OK=True, filas=380, columnas=120, BOM=True, CRLF, 2024-08-16..2025-05-25
- PL_2025-2026_raw.csv: sha256 OK=True, filas=380, columnas=132, BOM=True, CRLF, 2025-08-15..2026-05-24

### C00 — Entrada: INTERIM y CANONICAL aprobados; V02–V10 en modo lectura — PASS
- V02–V10 sobre CANONICAL: V02 PASS, V03 PASS, V04 PASS, V05 PASS, V06 PASS, V07 PASS, V08 PASS, V09 PASS, V10 PASS

### C03 — Determinismo: dos construcciones dan bytes idénticos (team_match_log y FEATURES) — PASS
- team_match_log: 0032af2965604d556b337a5d8c1f4ce6b5ac95ca931d82b99651a4f00c03ab02 = 0032af2965604d556b337a5d8c1f4ce6b5ac95ca931d82b99651a4f00c03ab02
- FEATURES: a18c47888a38a80585ae97930f81a4ad6fc4497315af63ef05f284352ca9b356 = a18c47888a38a80585ae97930f81a4ad6fc4497315af63ef05f284352ca9b356

### C01 — team_match_log: formato, cabecera, 2 × partidos filas, orden (team_id, kickoff) — PASS
- 3800 filas × 10 columnas

### C02 — team_match_log: espejo local/visitante y valores derivados solo de CANONICAL — PASS
- Partidos con 3+0 puntos: 1446; con 1+1: 454

### V11 — Integridad referencial FEATURES ↔ CANONICAL — PASS

### V12 — Reinicio de temporada: n_prev_season 0,1,…,37 por equipo-temporada; vacíos si 0 — PASS
- Equipo-temporadas: 100; partidos por equipo-temporada: [(38, 100)]

### V13 — Elegibilidad: min(h_n, a_n) ≥ 3; elegibles sin vacíos; conteos — PASS
- Elegibles por temporada: {'2021-2022': 350, '2022-2023': 350, '2023-2024': 349, '2024-2025': 350, '2025-2026': 350}; total 1749

### V14 — Perturbación coherente: invariantes (negativos) y cambio posterior (positivo) — PASS
- Partidos perturbados: 113 (100 aleatorios con semilla 42 ∪ anomalías conocidas)
- Comparaciones de control negativo (filas×perturbación) por categoría: {'anteriores_o_simultaneos': 20940, 'propio_t': 113, 'posteriores': 21887, 'posteriores_equipos_no_involucrados': 17661, 'otras_temporadas': 171760}
- Controles positivos aplicables: 218; con cambio detectado: 218; no aplicables (último partido del equipo en la temporada): 8

### V15 — Oráculo independiente (filtrado explícito kickoff < t) sobre conjunto obligatorio + muestra — PASS
- a_primeros_5_por_equipo_temporada: 251 partidos
- b_aplazamientos_y_vecinos: 306 partidos
- c_kickoff_simultaneo: 1070 partidos
- d_anomalias_conocidas: 14 partidos
- e_inicio_y_final_de_temporada: 100 partidos
- random_semilla_42: 100 partidos
- Conjunto obligatorio (unión a–e): 1336; total distinto evaluado: 1436; valores comparados: 34464; tolerancia 1e-09

### V16 — diff_x == h_x − a_x (vacío si algún lado vacío); feature_version = '0.1' — PASS
- Diferencias no vacías verificadas con igualdad exacta del double: 12950

### V17 — FEATURES: esquema normativo (5.4), serialización (4.0, D43) e idempotencia — PASS
- 1900 filas × 30 columnas; valores en notación científica: 0

### V01 — Integridad RAW por SHA-256 (después) — PASS
- PL_2021-2022_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=True, CRLF, 2021-08-13..2022-05-22
- PL_2022-2023_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2022-08-05..2023-05-28
- PL_2023-2024_raw.csv: sha256 OK=True, filas=380, columnas=106, BOM=False, CRLF, 2023-08-11..2024-05-19
- PL_2024-2025_raw.csv: sha256 OK=True, filas=380, columnas=120, BOM=True, CRLF, 2024-08-16..2025-05-25
- PL_2025-2026_raw.csv: sha256 OK=True, filas=380, columnas=132, BOM=True, CRLF, 2025-08-15..2026-05-24
- INTERIM después: cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad; CANONICAL después: 06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1

## SHA-256 RAW antes / después

| relative_path | antes | después | igual |
|---|---|---|---|
| `Documentacion de datos/notes.txt` | `6ecd41a98ad2751372817e7e6f1709bfeb433c53dd9aeda330fd926a5471452d` | `6ecd41a98ad2751372817e7e6f1709bfeb433c53dd9aeda330fd926a5471452d` | sí |
| `Premier_League_data_raw_csv/PL_2021-2022_raw.csv` | `335afcbabeb2939fa10ab39ba3e8215072d0b577cb8d0705c1e44c56e934e703` | `335afcbabeb2939fa10ab39ba3e8215072d0b577cb8d0705c1e44c56e934e703` | sí |
| `Premier_League_data_raw_csv/PL_2022-2023_raw.csv` | `8442792d3b614c94ea3cf381bd2736805889cc1713169035368fff19c3d02380` | `8442792d3b614c94ea3cf381bd2736805889cc1713169035368fff19c3d02380` | sí |
| `Premier_League_data_raw_csv/PL_2023-2024_raw.csv` | `b2e057b0ed959f198b0f63d2391c01239f3608e6de5db68edab3f88e04d07ff3` | `b2e057b0ed959f198b0f63d2391c01239f3608e6de5db68edab3f88e04d07ff3` | sí |
| `Premier_League_data_raw_csv/PL_2024-2025_raw.csv` | `d0c8ce4a96d886cf60cf101f570f4a3893844226f91c7bd769eb568c49edbfa4` | `d0c8ce4a96d886cf60cf101f570f4a3893844226f91c7bd769eb568c49edbfa4` | sí |
| `Premier_League_data_raw_csv/PL_2025-2026_raw.csv` | `3e3a8352f9ada6789c508d6ca184424421fed56a30400904a4a327c583407e62` | `3e3a8352f9ada6789c508d6ca184424421fed56a30400904a4a327c583407e62` | sí |
