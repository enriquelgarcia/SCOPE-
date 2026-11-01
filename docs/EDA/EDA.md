---
project: SCOPE
phase: EDA
status: complete
version: "0.1"
---

# SCOPE — EDA

## Estado

**Fase actual:** EDA v0.1 COMPLETO (E0–E11). Siguiente macrofase: modelado.

**Pipeline:** COMPLETED / FROZEN

---

## Objetivo

Comprender los datos generados por SCOPE antes de entrenar modelos y obtener evidencia para resolver decisiones pendientes sobre:

- P01 — burn-in
- P02 — ventana last5
- M1 — h/a/diff
- M3 — season vs last5
- Q01 — anomalía AST > AS

---

## Fuentes principales

- [[Documentacion del proyecto/02_data_pipeline_v0.1|Data Pipeline v0.1]]
- [[contract/SCOPE_Data_Contract_v0.1|Data Contract]]
- [[DECISION_LOG|Decision Log]]
- [[validation/validation_spec_v0.1|Validation Spec]]
- [[quality/data_quality_register_v0.1|Data Quality Register]]

---

## Regla D42

### Development

2021/22–2024/25

Puede utilizarse para tomar decisiones.

### Test final

2025/26

Solo análisis descriptivo.

No utilizar para seleccionar:

- features;
- burn-in;
- ventanas;
- transformaciones;
- modelos;
- hiperparámetros.

---

## Fases

- [x] E0 — Planificación
- [x] E1 — Estructura y calidad
- [x] E2 — Targets
- [x] E2m — Mercado
- [x] E3 — Univariadas
- [x] E4 — Relaciones
- [x] E5 — M1
- [x] E6 — M3
- [x] E7 — P01 burn-in
- [x] E8 — P02 last5
- [x] E9 — Q01
- [x] E10 — Drift
- [x] E11 — Síntesis

---

## Hallazgos

**E1 — Estructura y calidad** (completada; scope `ALL_DESCRIPTIVE`). Reporte: `reports/eda/eda_report_v0.1.md`.

- Entradas íntegras (hashes D44); dimensiones y esquema según el contrato.
- Nulos de FEATURES 100 % estructurales: 50 partidos inaugurales × 21 features (`n_prev_season = 0`).
- 1,749 elegibles; los 151 excluidos son mínimo de historial 0–2. 2023/24 = 349 por el desfase temprano de Burnley y Luton.
- 13 `dq_flags` (1 `AST_GT_AS` = Q01, 12 `GOALS_GT_SOT`), sin combinaciones ni anomalías nuevas.
- P01, P02, M1 y M3 siguen abiertas.

**E2 — Targets** (completada; scopes `ALL_DESCRIPTIVE` y `TRAIN_TARGET`, descriptivo).

- TRAIN (2021/22–2023/24): H 45.8 % · D 22.5 % · A 31.7 %. ALL (5 temporadas, solo descriptivo): H 44.2 % · D 23.9 % · A 31.9 %. Clases no uniformes; D es la minoritaria.
- `goal_difference` (TRAIN): entera, mediana 0, media +0.32, DE 1.99, rango [−8, +9], 80 % con |GD| ≤ 2. No normal por construcción.
- Goles (TRAIN): var/media ≈ 1.15 local y visitante (sobredispersión aparente), ≈ 0.97 total; covarianza local–visitante negativa. Sin conclusión sobre Poisson.
- Ventaja local descriptiva presente en ALL, TRAIN, VAL y TEST. VAL y TEST no se usan para decisiones.
- Variación entre temporadas descrita, no interpretada como drift (corresponde a E10). Sin decisiones de modelado.

**E2m — Mercado** (completada; `ALL_DESCRIPTIVE`; **benchmark externo, nunca predictor**).

- 6 cuotas `Avg` completas (1,900 × 6, todas > 1). La normalización D39 cumple Σp = 1.
- Overround medio: pre 4.52 %, close 4.32 % (close < pre en todas las temporadas). ≈ 4.1 % en 2021/22–2023/24, más alto en 2024/25 y 2025/26 (solo descriptivo).
- p_pre media: H 0.441 · D 0.237 · A 0.323. El empate nunca es favorito del mercado.
- Movimiento pre → close pequeño (mediana L1 0.036). El favorito cambia en el 3.8 % de los partidos.
- Sin accuracy, log loss, Brier, calibración ni comparación SCOPE vs mercado.

**E3 — Univariadas** (completada; `DEV_PREDICTORS`, 1,399 filas elegibles 2021/22–2024/25; sin targets).

- 0 errores de dominio. 311 valores extremos legítimos, concentrados con poco historial (3.75 % en 3–5 frente a < 1 % con ≥ 11).
- DE de las features season 1.6–1.8 veces mayor con 3–5 partidos previos que con 21–37. La de last5 se estabiliza desde 6–10. Sin decisión de burn-in (P01, E7).
- Distribuciones marginales de `h_*` y `a_*` muy similares (rendimiento global previo, no localía; no son columnas intercambiables). Las 7 `diff_*` centradas en 0 y casi simétricas.
- last5 muy discreta: 27–39 valores únicos frente a 477–552 en season. Redundancia pendiente para E6.
- Ninguna feature eliminada, transformada, winsorizada ni escalada.

**E4 — Relaciones** (completada). **E4A** predictor ↔ predictor en `DEVX` (1,399 filas, sin targets). **E4B** predictor ↔ target solo en `TRAIN` (1,049 filas); VAL y TEST excluidos.

- DEVX: `h_x` y `a_x` casi incorrelacionadas (|r| ≤ 0.08). Su ≈ ±0.7 con `diff_x` es en gran parte algebraico. M1 abierta (E5).
- DEVX: PPG ↔ GF/PG +0.82 y PPG ↔ GA/PG −0.78 (season). season ↔ last5 0.73–0.78, inflado en parte por `n_prev ≤ 5`. M3 abierta (E6).
- DEVX: Pearson ≈ Spearman (|Δ| ≤ 0.031). Heatmap de Spearman omitido.
- TRAIN: correlaciones con GD de magnitud baja a moderada (|r| 0.17–0.41), signos esperables. No es importancia ni selección.
- TRAIN: las `diff_*` se desplazan entre H, D y A según la semántica de cada métrica (invertida en `diff_ga_*`), con solapamiento considerable. D se sitúa entre H y A en varias `diff_*`; su separabilidad multivariable no se evalúa en E4.

**E5 — M1** (completada; `DEV_PREDICTORS`, 1,399 filas elegibles; sin targets).

- `diff = h − a` se verifica en las 7 ternas (error ≤ 8.9e-16, redondeo de coma flotante). Cada terna tiene rango 2 de 3.
- HA rango 14/14 y DIFF 7/7. **HADIFF rango 14/21, nullity 7**, con o sin intercepto y con o sin estandarización.
- HADIFF: VIF = ∞ en las 21 columnas (R² auxiliar = 1). El condition number numérico enorme es singularidad, no "multicolinealidad alta".
- HA y DIFF: multicolinealidad no exacta (VIF máximo ≈ 11.5 en `ppg_season`; mínimo ≈ 2.2 en SOT). Sin umbrales ni eliminación.
- **E5 aprobado. M1 estructuralmente cerrado (D46):** HADIFF no se usará en modelos lineales no regularizados. HA y DIFF siguen como candidatas distintas.

**E6 — M3** (completada; `DEV_PREDICTORS`; sin targets).

- season = last5 al 100 % mientras la ventana contiene todo el historial (`n_prev ≤ 5`). En diff, solo si ambos lados cumplen `max(h_n, a_n) ≤ 5`; hay 2 partidos en zona mixta (2023/24), sin identidad.
- Fuera de identidad: r ≈ 0.69–0.75 (frente a 0.73–0.78 global, inflado). Por tramo: 1 → 0.83–0.91 (6–10) → estable ≈ 0.64–0.75 desde 11 partidos.
- Divergencia creciente: MAE h/a 0.23 (6–10) → 0.41 (21–37). GA/PG es la métrica menos correlacionada fuera de identidad.
- VIF season+last5: rango completo. Excluir la identidad baja los VIF last5 un ≈ 9–19 %; persiste colinealidad no exacta (VIF ≈ 12, condition number ≈ 10), sin umbrales.
- **E6 aprobado. M3 estructuralmente cerrado (D47).** P02 sigue abierta (E8 y modelado).

**E7 — P01 burn-in** (completada). **E7A** predictor-only en DEVX. **E7B** retrospectivo solo en TRAIN: la referencia de temporada completa usa información futura solo como diagnóstico, nunca como feature.

- Coste prácticamente lineal: 1→2 excluye 41 DEVX / 31 TRAIN (irregularidad de calendario de 2023/24). Desde 2→3, exactamente 40 DEVX / 30 TRAIN por paso. Con k = 3: 1,399 DEVX (92.0 %).
- DEVX: la DE de las features season, relativa a la madura, pasa de 2.74 (n = 1) a 2.20, 1.82, 1.72 y 1.58 (n = 5). Los extremos, de 30 % a 17 %, 10 %, 8 % y 6 %.
- TRAIN: el MAE de PPG frente a la referencia de 38 partidos pasa de 1.17 a 0.73, 0.58, 0.52 y 0.48 (0.27 con n = 10). 2→3 aún mejora de forma material en la mayoría de métricas (IC > 0 en PPG, GF y SOT; no en GA); 3→4 y 4→5 mejoran poco y con IC que incluyen 0 (salvo GA 4→5).
- **E7 aprobado. P01 cerrado y promovido a D48: burn-in v0.1 = 3** (`min(h_n, a_n) ≥ 3`). Es una decisión de parsimonia, no un óptimo. La sensibilidad con k = 4/5 queda solo como posible análisis de modelado (TRAIN/VAL). P02 sigue abierta.

**E8 — P02 last5** (completada). **E8A** predictor-only en DEVX. **E8B** diagnóstico target-aware solo en TRAIN (`n_prev ≥ 6`; outcome = resultado del propio partido, nunca predictor).

- Distinta de season fuera de la zona D47 y ≈ 3.7–4.3× más responsiva partido a partido (memoria de 5 partidos frente a 1/n de season).
- TRAIN: la asociación de last5 con el desempeño del partido es **menor** que la de season (Spearman PPG 0.19 frente a 0.26; GF 0.18 frente a 0.26; IC de la diferencia < 0). GA no es concluyente.
- La desviación reciente (last5 − season) no muestra persistencia distinguible de 0; solo hay un indicio débil en GA.
- **E8 aprobado. P02 permanece abierta (PROVISIONAL); la resolución final pasa al modelado.** last5 se mantiene como candidata en FEATURES v0.1, sin validarse como incremental. El modelado deberá comparar "season" frente a "season + last5" solo con TRAIN/VALIDATION (nunca TEST). En el Decision Log solo se actualizó la trazabilidad de P02 (y una referencia mínima en P04).

**E9 — Q01: AST > AS** (completada). Scope `ALL_DESCRIPTIVE`, sin targets; RAW solo lectura.

- **Localización:** `PL_2021-2022_raw.csv`, `source_row = 9`, Newcastle – West Ham (2021-08-15), `AS = 8`, `AST = 9`, flag `AST_GT_AS`, split TRAIN. Es la única fila con `AST > AS`; no hay ninguna con `HST > HS`.
- **Origen:** inconsistencia del par AS/AST presente en la fuente (categoría A); no se sabe qué campo es erróneo. RAW ya la contiene; INTERIM, CANONICAL y team_match_log la preservan sin alteración, con la orientación home/away correcta. No hay bug de pipeline.
- **Propagación:** solo `sot_pg_last5` de West Ham en sus partidos 2–6 (5 partidos, `n_prev` 1–5) y `diff_sot_pg_last5` en los mismos. Son 3 partidos elegibles (0.17 % de 1,749), todos en TRAIN. El propio partido Q01 no se contamina (`shift(1)`).
- **Sensibilidad condicionada** (en memoria): escenario A (AS correcto, AST 9→8): −1/n_prev, es decir ≤ 0.33 en filas elegibles; escenario B (AST correcto, AS 8→9): delta 0 en todas las features SOT. La magnitud de una corrección es desconocida.
- **E9 aprobado. Q01 cerrada y promovida a D49:** el tratamiento v0.1 es conservar los valores fuente y el flag `AST_GT_AS`, sin reparación, porque no se sabe qué campo es erróneo. RAW es inmutable y cualquier reparación futura irá en una capa derivada versionada, con decisión explícita.

**E10 — Drift temporal** (completada). Predictor-only, filas elegibles (350 / 350 / 349 / 350 / 350); SMD y KS propio, sin umbrales.

- **Pico en 2023/24:** GF/GA/SOT h/a suben (SMD +0.27 a +0.41) y en parte revierten en 2024/25. El pico persiste entre los 17 equipos comunes, así que no es solo efecto de composición (17 compartidos, 3 entrantes y 3 salientes por transición).
- **TRAIN → VAL:** centro prácticamente igual (|SMD| ≤ 0.03), pero GF season más concentrada en VAL (DE × ≈ 0.78, KS ≈ 0.10). TRAIN es internamente heterogéneo.
- **Estabilidad:** `diff_*` muy estables en el centro (|SMD| ≤ 0.05); PPG h/a con desplazamientos de centro pequeños; `n_prev` idéntico. Local y visitante cambian igual. Season no es más estable que last5: desplazamientos de media similares; algunas season tienen KS mayor (forma), sin atribución causal.
- **Pipeline:** no hay indicio técnico de drift por el pipeline (las columnas fuente de las features están completas en las 5 temporadas; los anchos RAW 106 / 106 / 106 / 120 / 132 solo varían en columnas de cuotas, según el diccionario RAW).
- **⚠ FINAL TEST (descriptivo, no decisional):** 2025/26 tiene GF, GA y SOT más bajos (SOT last5 SMD ≈ −0.29) y menos dispersos. Debe tenerse en cuenta al interpretar el desempeño final, pero no modifica el protocolo.
- Sin decisiones ni propuestas nuevas.

**E11 — Síntesis final** (completada). Documento formal: [[03_analisis_exploratorio_eda|03 — Análisis exploratorio (EDA)]]. Tablas: `e11_eda_phase_summary__ALL.csv`, `e11_decision_status__ALL.csv`, `e11_modeling_handoff__ALL.csv`.

- **Cerrado:** D46 (M1), D47 (M3), D48 (burn-in k = 3), D49 (Q01: valores fuente + flag).
- **Abierto:** P02 (last5, incremental en modelado), P04 (subconjuntos d = 5 / d = 10), P03 (GD OLS, Matemáticas), P06 (split, propuesta vigente), P07 (zona horaria); C01–C06 pendientes docentes.
- **Handoff:** decisiones solo con TRAIN/VAL; TEST 2025/26 reservado para la evaluación final.

**Siguiente macrofase:** modelado.

---

## Decisiones

- **D46 — M1, cierre estructural** (desde E5, 2026-11-01): no usar HADIFF (h + a + diff) en modelos lineales no regularizados por dependencia exacta (rango 14/21). HA y DIFF siguen siendo candidatas; rendimiento, subconjuntos (P04), escalado y regularización siguen abiertos. Ver [[DECISION_LOG|Decision Log]].
- **D47 — M3, cierre estructural** (desde E6, 2026-11-01): season = last5 exactamente mientras `n_prev ≤ 5` (h/a) o `max(h_n, a_n) ≤ 5` (diff). Fuera de esa zona están relacionadas pero no son idénticas; no hay dependencia exacta ni se afirma equivalencia predictiva. **P02 sigue abierta.**
- **D48 — Burn-in v0.1, cierre de P01** (desde E7, 2026-11-01): `k = 3`, `min(h_n_prev, a_n_prev) ≥ 3`. No es un óptimo; k = 4/5 no se demuestran peores; sensibilidad posible en el modelado (nunca TEST). Sin cambios de datos.
- **D49 — Q01, inconsistencia AS/AST** (desde E9, 2026-11-01): v0.1 conserva los valores fuente (`AS = 8`, `AST = 9`) y el flag `AST_GT_AS`, sin reparación determinista. El campo erróneo es desconocido; la anomalía es localizada en extensión (5 partidos, 3 elegibles, solo `sot_pg_last5` y su `diff`). Sin cambios de datos.