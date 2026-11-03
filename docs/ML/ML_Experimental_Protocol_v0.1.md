# SCOPE — Protocolo experimental de Machine Learning v0.1 (ML-0)

**Proyecto:** SCOPE — Sports Computational Outcome Prediction Engine
**Etapa:** ML-0 — diseño y congelamiento del protocolo experimental, **antes de observar cualquier resultado de modelos**
**Fecha:** 2026-11-03
**Estado:** **DEFINIDO — PENDIENTE DE REVISIÓN (ML-0 review)**. Ningún modelo entrenado; ningún resultado ML producido; FINAL TEST bloqueado.
**Entradas congeladas:** FEATURES v0.1 (D44) `data/features/pl_features_v0.1.csv` (SHA-256 `a18c4788…b356`) y, solo para el benchmark, el bloque MARKET de CANONICAL v0.1 (`06bcacae…4ee1`).
**Artefactos ejecutables del protocolo:** `src/ml/ml_protocol.py` (valida y materializa) · `reports/ml/ml_experiment_matrix_v0.1.csv` · `reports/ml/ml_feature_representations_v0.1.csv` · `reports/ml/ml_metrics_spec_v0.1.csv` · `reports/ml/ml_split_protocol_v0.1.csv` · `reports/ml/ml0_protocol_manifest.json`.

> **Jerarquía normativa.** Este documento no crea decisiones `Dxx`, no modifica decisiones aprobadas y no cierra P02, P04 ni P06. Si algo de aquí pareciera contradecir el Decision Log o el contrato, **prevalecen** el Decision Log y el contrato.
>
> **Convención de origen** (igual que el Decision Log): **[R]** requisito de rúbrica · **[D/Dxx]** decisión aprobada del equipo · **[P0x]** provisional vigente · **[C0x]** pendiente docente · **[RD]** requisito docente comunicado sin respaldo documental todavía · **[ML-0]** regla nueva de este protocolo (propuesta del asesor, sujeta a la revisión ML-0).

---

## 1. Objetivo

Definir, **antes de entrenar nada**, cómo se entrenarán, compararán, seleccionarán y evaluarán los modelos de SCOPE v0.1, de modo que:

- la selección de modelo, representación e hiperparámetros dependa solo de TRAIN y VALIDATION;
- P02 (valor incremental de last5) y P04 (subconjuntos d = 5 / d = 10) se resuelvan con comparaciones fijadas de antemano;
- FINAL TEST (2025/26) se use **una sola vez**, con la configuración congelada;
- las métricas y sus convenciones (en particular Brier y clipping) queden fijadas antes de ver ningún número.

## 2. Estado heredado del pipeline y EDA

| Elemento | Estado | Consecuencia para ML |
|---|---|---|
| D44 | Pipeline/data v0.1 **congelado** | ML solo lee FEATURES/CANONICAL; nunca los reconstruye |
| D46 | HADIFF con dependencia lineal exacta (rango 14/21) | Ninguna representación ML-0 contiene `h_x + a_x + diff_x` de una misma métrica |
| D47 | season = last5 mientras la ventana contiene todo el historial | Explica la correlación alta season/last5; no decide P02 |
| D48 | Burn-in `k = 3` | Población de modelado = `is_modeling_eligible = true` |
| D49 | Q01: valores fuente + flag, sin reparación | La configuración principal usa los valores preservados |
| D12/D13/D39 | Estrategia C; mercado = benchmark externo; normalización proporcional | MARKET nunca en X |
| D22/D23 | d = 5 vs d = 10 no equivalentes; KNN/LR manuales del estudiante sin IA [R] | Ver §10 y §21 |
| D35/D42 | 2025/26 test final **no completamente ciego** | Ninguna decisión puede usar 2025/26 |
| P02 | **Abierta** | Experimento predefinido en §9 |
| P03 | `goal_difference` solo para la regresión de Matemáticas | Fuera del objetivo ML; nunca predictor |
| P04 | **Provisional** | Experimento predefinido en §10 |
| P06 | **Provisional** (protocolo operativo vigente) | §5; no se promueve aquí |
| P07 | Abierta | Sin impacto en v0.1 (fuente única) |
| C01–C06 | Pendientes docentes | C04, C05 y C06 afectan a ML/Complejidad (§22) |
| [RD] | Al menos 4 modelos de ML | Se planifican 4 modelos reales + 2 baselines (§13) |

## 3. Target

- **Problema:** clasificación multiclase `result ∈ {H, D, A}` (H = victoria local, D = empate, A = victoria visitante) [contrato §11].
- **Salida principal:** un vector de probabilidades `(P(H), P(D), P(A))` por partido, con `P(H) + P(D) + P(A) = 1`.
- **Orden de clases [ML-0]:** **siempre `H, D, A`** en columnas de probabilidad, matrices de confusión y tablas. Las librerías que ordenan alfabéticamente (`A, D, H`) se reordenan explícitamente por etiqueta, con aserción.
- **Clase predicha [ML-0]:** `argmax(P(H), P(D), P(A))`; desempate determinista en el orden `H > D > A`. **No** se ajustan thresholds ni reglas de decisión para favorecer D en v0.1 (requeriría una decisión posterior).
- **Control de integridad [ML-0]:** antes de cualquier métrica, cada fila debe cumplir `0 ≤ p_k ≤ 1` y `|ΣP − 1| ≤ 1e-9` (misma tolerancia que D39); si falla, se aborta.
- El objetivo de SCOPE no es solo acertar la clase, sino **producir probabilidades útiles**; de ahí la métrica primaria (§15).

## 4. Población

Población del experimento principal: filas con `is_modeling_eligible = true`, es decir `min(h_n_prev_season, a_n_prev_season) ≥ 3` (D48). El script recalcula la regla y aborta si no coincide.

Tamaños verificados en FEATURES v0.1 (conteo, sin leer targets):

| Conjunto | Temporadas | Elegibles | Esperado |
|---|---|---|---|
| TRAIN | 2021/22–2023/24 | **1,049** (350 + 350 + 349) | 1,049 ✓ |
| VALIDATION | 2024/25 | **350** | 350 ✓ |
| FINAL TEST | 2025/26 | **350** | 350 ✓ |

Las 151 filas no elegibles (50 sin historia + 101 con 1–2 partidos previos de algún equipo) **no** entran en el protocolo principal. Pueden usarse en análisis aparte, que no forman parte de v0.1.

**Missingness:** 0 celdas vacías en las 21 rate features de las filas elegibles en las cinco temporadas (verificación predictor-only, compatible con D42). Coincide con E1. Si apareciera missingness, el script aborta esa representación; **no se imputa**.

## 5. Split temporal (P06 operativo, provisional)

`TRAIN = 2021/22, 2022/23, 2023/24` · `VALIDATION = 2024/25` · `FINAL TEST = 2025/26`.

P06 **sigue provisional**: este protocolo lo usa como protocolo operativo vigente, sin promoverlo a `Dxx`.

| Conjunto | Permite | Prohíbe |
|---|---|---|
| **TRAIN** | ajuste de modelos y preprocessing; búsqueda de hiperparámetros (vía CV interno, §6); comparación interna | — |
| **VALIDATION** | confirmar representaciones; aportar la evidencia que resuelva P02 y P04; seleccionar la configuración/modelo final; estimar la generalización temporal antes de TEST | ajustar scaler o modelos durante el CV; iteraciones ilimitadas (§17) |
| **FINAL TEST** | una única evaluación final (ML-9) | selección, hiperparámetros, features, P02, P04, escalado, thresholds, calibración, elección de modelo, tratamiento de anomalías (D35, D42) |

El conocimiento descriptivo previo de 2025/26 (D42, E10) **no puede influir** en ninguna decisión de este protocolo. Ninguna regla de ML-0 se ha definido mirando 2025/26.

**Modelo estático por evaluación [ML-0]:** dentro de VALIDATION o TEST el modelo **no** se reentrena partido a partido. Las features sí se actualizan cronológicamente con partidos ya jugados, porque así están precomputadas en FEATURES (D34, contrato §6.2). El reentrenamiento intra-temporada queda como evolución futura.

## 6. Temporal CV interno (dentro de TRAIN)

Expanding window, dos folds:

| Fold | Train | Validate | n train / n validate |
|---|---|---|---|
| **T1** | 2021/22 | 2022/23 | 350 / 350 |
| **T2** | 2021/22 + 2022/23 | 2023/24 | 700 / 349 |

Reglas:
- No se usa random K-fold como estrategia principal (contrato T8).
- Ningún partido futuro entra en el train de un fold. El script verifica que el train de cada fold sea estrictamente anterior a su validación, que no se solapen, que T2 sea expanding de T1 y que ni 2024/25 ni 2025/26 aparezcan en el CV.
- Todas las transformaciones se ajustan **solo** con el train del fold (§11).
- El CV sirve para: hiperparámetros, robustez y comparación preliminar de representaciones.
- VALIDATION 2024/25 es una confirmación temporal **externa** al TRAIN.

**Limitación conocida:** los hiperparámetros se eligen con n = 350/700 y luego se reajustan con n = 1,049 (o 1,399 en un posible refit final). Los que dependen de n, sobre todo `n_neighbors` de KNN, pueden no transferirse exactamente. Se documentará, sin corregirlo con TEST.

## 7. Features permitidas / prohibidas

**Permitidas como predictores (21 rate features de FEATURES v0.1, D20):**
- `h_`/`a_`/`diff_` × {`ppg_season`, `gf_pg_season`, `ga_pg_season`, `ppg_last5`, `gf_pg_last5`, `ga_pg_last5`, `sot_pg_last5`}.
- Solo en combinaciones declaradas en una representación (§8, D19/M4).

**Prohibidas como predictores (el script aborta si aparecen en una representación):**

| Categoría | Columnas | Motivo |
|---|---|---|
| Targets | `result`, `goal_difference` | Target / target auxiliar (P03) |
| POST del mismo partido | `home_goals`, `away_goals`, `ht_*`, tiros, tiros a puerta, córners, faltas, tarjetas (CANONICAL) | T4: información producida durante el partido |
| MARKET | `mkt_avg_pre_*`, `mkt_avg_close_*` | D12, T7: solo benchmark |
| Keys | `match_id`, `season`, `kickoff_datetime` | Solo trazabilidad; ni fecha como número arbitrario ni season como proxy categórico |
| Control | `is_modeling_eligible`, `feature_version`, `h_n_prev_season`, `a_n_prev_season` | Control/elegibilidad (contrato §5.1: uso "control, elegibilidad, estabilidad"), no predictor en v0.1 |
| IDs nominales y metadatos | `home_team_id`, `away_team_id`, nombres, `referee`, `match_seq_season`, `match_date`, `kickoff_time`, `source_row`, `dq_flags` | Identidades nominales y metadatos; solo con decisión futura explícita |

Las keys se conservan en los artefactos futuros únicamente para trazabilidad (unión con MARKET por `match_id`, registro en PREDICTIONS).

## 8. Representaciones

Matriz pequeña y preestablecida (`reports/ml/ml_feature_representations_v0.1.csv`). Las listas exactas proceden del esquema real (contrato §5.4) y del contrato §12; ninguna contiene HADIFF.

**Hecho del esquema que condiciona el diseño:** en v0.1 **no existe `sot_pg_season`**. SOT solo existe en last5 (D20). Por tanto, añadir last5 a season añade **dos cosas a la vez**: una ventana distinta para PPG/GF/GA y una métrica nueva (SOT).

| ID | Nombre | Prioridad | d | Features exactas |
|---|---|---|---|---|
| **R1** | DIFF / SEASON | CORE | 3 | `diff_ppg_season`, `diff_gf_pg_season`, `diff_ga_pg_season` |
| **R2** | DIFF / SEASON + LAST5 | CORE | 7 | R1 + `diff_ppg_last5`, `diff_gf_pg_last5`, `diff_ga_pg_last5`, `diff_sot_pg_last5` (= DIFF completa de D46) |
| **R3** | HA / SEASON | CORE | 6 | `h_`/`a_` × {`ppg_season`, `gf_pg_season`, `ga_pg_season`} |
| **R4** | HA / SEASON + LAST5 | CORE | 14 | R3 + `h_`/`a_` × {`ppg_last5`, `gf_pg_last5`, `ga_pg_last5`, `sot_pg_last5`} (= HA completa de D46) |
| **P04-D5** | Subconjunto d = 5 (contrato §12) | CORE | 5 | `diff_ppg_season`, `diff_gf_pg_season`, `diff_ga_pg_season`, `diff_ppg_last5`, `diff_sot_pg_last5` |
| **P04-D10** | Subconjunto d = 10 (contrato §12) | CORE | 10 | `h_`/`a_` × {`ppg_season`, `gf_pg_season`, `ga_pg_season`, `ppg_last5`, `sot_pg_last5`} |
| **R5** | DIFF / SEASON + LAST5 (mismas métricas) | DIAGNOSTIC | 6 | R1 + `diff_ppg_last5`, `diff_gf_pg_last5`, `diff_ga_pg_last5` |
| **R6** | HA / SEASON + LAST5 (mismas métricas) | DIAGNOSTIC | 12 | R3 + `h_`/`a_` × {`ppg_last5`, `gf_pg_last5`, `ga_pg_last5`} |
| **R7** | DIFF / LAST5 sola | OPTIONAL | 4 | `diff_` × {`ppg_last5`, `gf_pg_last5`, `ga_pg_last5`, `sot_pg_last5`} |
| **R8** | HA / LAST5 sola | OPTIONAL | 8 | `h_`/`a_` × {las 4 last5} |

- **CORE:** son candidatas a la selección final.
- **DIAGNOSTIC (R5, R6):** sirven para separar, dentro de P02, el efecto "ventana last5" del efecto "SOT" [ML-0]. Coinciden con los conjuntos de 6 y 12 columnas cuyo rango estudió E6. **No** son candidatas a la selección final.
- **OPTIONAL (R7, R8):** "last5 sola", el diagnóstico opcional que P02 prevé. Solo con regresión logística; nunca candidatas.

**HA vs DIFF.** Se comparan dentro del mismo modelo y la misma ventana (R1 vs R3, R2 vs R4, P04-D5 vs P04-D10). Por D22/D46 son representaciones **distintas y no equivalentes**: DIFF pierde los niveles absolutos. Una diferencia de rendimiento entre ellas no se atribuye solo a la dimensionalidad.

## 9. P02 — valor incremental de last5

**Pregunta:** ¿last5 aporta valor incremental una vez que season ya está disponible?

**Comparaciones principales (dentro de la misma familia, mismo modelo, mismas filas, cada representación con su propio tuning por CV):**
- **DIFF:** R1 (season) vs R2 (season + last5)
- **HA:** R3 (season) vs R4 (season + last5)

**Comparaciones de diagnóstico [ML-0]:** ventana `R1→R5`, `R3→R6`; SOT `R5→R2`, `R6→R4`. Opcional: R7/R8 (last5 sola, solo LR).

**No válido para atribuir el cambio a last5:** comparar entre familias (p. ej. R1 vs R4) o usar P04-D5/P04-D10, que mezclan season y last5.

**Criterio futuro (principio, sin threshold numérico post hoc).** last5 se considerará evidencia de valor incremental si:
1. la mejora aparece de forma consistente en **ambos** folds del CV temporal de TRAIN (T1 y T2);
2. se confirma en VALIDATION;
3. mejora la métrica primaria (log loss) o produce un trade-off claramente favorable en las secundarias (Brier, calibración);
4. no depende únicamente de una mejora marginal en accuracy;
5. no proviene de TEST.

La evidencia se lee **por familia** (DIFF, HA) y **por modelo**; no se cuentan "votos" automáticamente.
- Si la evidencia es contradictoria entre folds, entre familias o entre modelos, P02 permanece abierta o se resuelve posteriormente por parsimonia (la opción parsimoniosa es season sola).
- Los diagnósticos R5/R6 indicarán si una mejora de R2/R4 se debe a la ventana o sobre todo a SOT. Esto importa porque SOT no tiene versión season.
- **P02 no se cierra en ML-0.** Su cierre requerirá una decisión posterior en el Decision Log (ML-7).

## 10. P04 — subconjuntos d = 5 / d = 10

**Contenido literal** (contrato §12, ligado a D22; el Decision Log P04 solo los nombra):
- **`d = 5`:** `diff_ppg_season`, `diff_gf_pg_season`, `diff_ga_pg_season`, `diff_ppg_last5`, `diff_sot_pg_last5`. Representación comprimida basada en diferencias.
- **`d = 10`:** versiones `h_*` y `a_*` de esas mismas cinco métricas. Conserva los niveles absolutos.

Se incorporan **sin modificar** como experimentos `P04-D5` y `P04-D10` para los 4 modelos núcleo (y M5 si se ejecuta).

**Estructura anidada (permite interpretar):** `R1 ⊂ P04-D5 ⊂ R2` y `R3 ⊂ P04-D10 ⊂ R4`.

**Comparaciones predefinidas:** P04-D5 vs P04-D10; R1 vs P04-D5 vs R2; R3 vs P04-D10 vs R4.

**Advertencias:**
- **D22 sigue aplicando:** la diferencia D5 vs D10 no puede atribuirse solo a la dimensionalidad, porque las representaciones contienen información distinta.
- Ambos subconjuntos incluyen features last5 (`ppg_last5`, `sot_pg_last5`), así que su lectura depende de P02.
- `diff_sot_pg_last5` / `*_sot_pg_last5` contienen las 3 filas TRAIN afectadas por Q01 (D49).
- El propósito original de estos subconjuntos es el estudio de coste computacional en función de `d` (Complejidad, D22/D23). Ese uso es válido con independencia del rendimiento predictivo. ML aporta evidencia predictiva, **no** redefine por sí solo los subconjuntos de Complejidad.

**P04 no se cierra en ML-0.**

## 11. Preprocessing

Todas las features candidatas son numéricas y sin missingness en la población elegible: no hay encoding ni imputación.

| Familia de modelo | Preprocessing | Regla |
|---|---|---|
| Sensibles a escala: **M1** (LR), **M2** (KNN) | `StandardScaler` dentro de un `Pipeline` | `fit` **solo** con el train del fold; `transform` del train y la validación del fold |
| Árboles: **M3** (DT), **M4** (RF), **M5** (HGB) | Ninguno | Pipeline separado; no se estandariza salvo razón específica |
| Baselines **B0**, **B1** | Ninguno | Solo usan las etiquetas del train correspondiente |

Ciclo por fold: `fit scaler → fold train` y `transform → fold train + fold validation`. Para VALIDATION: `fit → TRAIN_FULL`. Para el refit final, si se aprueba: `fit → TRAIN+VALIDATION`.

**Nunca** se ajusta el scaler con la VALIDATION externa durante el CV, con TEST, ni con el dataset completo antes del CV (contrato T8).

**Orden de filas [ML-0]:** se conserva el orden del archivo, `(kickoff_datetime, match_id)` (D30); no se baraja. Esto hace reproducibles los desempates de KNN y de los árboles. La granularidad de last5 (E3) produce muchos empates de distancia y de corte.

## 12. Baselines

| ID | Definición | Uso |
|---|---|---|
| **B0 — Majority class** | Predice siempre la clase más frecuente del train correspondiente (por fold / TRAIN_FULL / refit) | Referencia para métricas hard-class y Brier. Su log loss es degenerado (probabilidad 1 a una clase) y se reporta como "no informativo" |
| **B1 — Class prior** | Asigna a todos los partidos evaluados `(P̂(H), P̂(D), P̂(A))`, las frecuencias del train correspondiente | **Baseline probabilístico principal** (log loss, Brier, calibración) |

Las frecuencias se recalculan **dentro de cada fit**, nunca con el dataset completo. ML-0 **no** calcula estas frecuencias: hacerlo es ajustar el baseline, que corresponde a ML-1.

## 13. Modelos

Al menos cuatro modelos reales además de los baselines. Así se cumple el [RD] (≥ 4 modelos), tanto si C06 confirma que una baseline cuenta como si no.

| ID | Modelo | Implementación (librería) | Escalado | Representaciones | Notas |
|---|---|---|---|---|---|
| **M1** | Multinomial Logistic Regression | `sklearn.linear_model.LogisticRegression` (lbfgs, softmax multinomial) | Sí | CORE + R5/R6 + R7/R8 | Probabilístico e interpretable. D46 respetada: ninguna representación contiene HADIFF |
| **M2** | K-Nearest Neighbors | `sklearn.neighbors.KNeighborsClassifier` | Sí | CORE + R5/R6 | Sensible a escala y a `d`. Con `k` pequeño sus probabilidades son discretas y pueden valer 0, lo que la log loss penaliza fuertemente tras el clipping: es esperado, no un error |
| **M3** | Decision Tree | `sklearn.tree.DecisionTreeClassifier` | No | CORE + R5/R6 | Profundidad y hojas mínimas controladas contra el sobreajuste; probabilidades = frecuencias en hoja |
| **M4** | Random Forest | `sklearn.ensemble.RandomForestClassifier` | No | CORE + R5/R6 | Ensamble; probabilidades promediadas |
| *M5 (opcional)* | HistGradientBoosting | `sklearn.ensemble.HistGradientBoostingClassifier` | No | CORE | Solo si se justifica en ML-6. Incluido en scikit-learn, sin dependencias nuevas. `early_stopping=False`, para evitar una partición interna aleatoria |

**Dependencia:** scikit-learn **no está instalado** actualmente en el entorno del proyecto (Python 3.10.12, pandas 2.3.3, NumPy 2.2.6). Habrá que instalarlo y registrar su versión al inicio de ML-1. ML-0 no lo importa.

Las implementaciones de librería del experimento ML están **separadas** de las implementaciones manuales de Complejidad (§21).

## 14. Hiperparámetros candidatos (espacio fijado; no ejecutado)

Grids pequeños e interpretables. El ganador no se fija aquí y no se ejecuta ninguna búsqueda.

| Modelo | Fijos | Grid | Puntos |
|---|---|---|---|
| B0 / B1 | `strategy = most_frequent` / `prior` | — | 1 |
| M1 | `solver = lbfgs`, multinomial, `max_iter = 5000`, `class_weight = None` | `C ∈ {0.01, 0.1, 1, 10, 100}`; `penalty = l2` | 5 |
| M2 | `algorithm = auto` | `n_neighbors ∈ {5, 11, 21, 51, 101}`; `weights ∈ {uniform, distance}`; `metric ∈ {euclidean, manhattan}` | 20 |
| M3 | `random_state = 42`, `class_weight = None` | `max_depth ∈ {2, 3, 4, 6, 8}`; `min_samples_leaf ∈ {10, 25, 50, 100}`; `criterion ∈ {gini, log_loss}` | 40 |
| M4 | `n_estimators = 500`, `bootstrap = True`, `random_state = 42`, `n_jobs = 1` | `max_depth ∈ {3, 5, 8, None}`; `min_samples_leaf ∈ {10, 25, 50}`; `max_features ∈ {sqrt, 0.5, 1.0}` | 36 |
| M5 (opc.) | `random_state = 42`, `early_stopping = False`, `loss = log_loss` | `learning_rate ∈ {0.03, 0.1}`; `max_iter ∈ {100, 300}`; `max_leaf_nodes ∈ {7, 15}`; `min_samples_leaf ∈ {20, 50}` | 16 |

Justificaciones:
- **M1:** solo L2. Cubre desde regularización fuerte (cerca del prior) hasta casi sin regularizar. La LR sin penalización no hace falta para respetar D46, porque ninguna representación es singular.
- **M2:** `k` ≤ 101 para que sea válido con el train más pequeño (350).
- **M4:** `n_estimators` se fija en 500 en vez de buscarse, porque más árboles no sobreajustan y solo cuestan tiempo.
- **Clases:** `class_weight = None` en todos los modelos para no optimizar D a costa de la calibración. Cualquier reponderación requerirá una decisión posterior.

**Regla de selección de hiperparámetros [ML-0]** (solo TRAIN CV):
1. Para cada `modelo × representación × punto del grid`, ajustar en T1_TRAIN → puntuar T1_VAL y ajustar en T2_TRAIN → puntuar T2_VAL. Se guardan **todas** las métricas por fold.
2. Se elige el punto con **menor log loss media** (T1, T2). Se reportan la media y **ambos** valores individuales.
3. Si dos puntos empatan (diferencia < 1e-12), se elige el más simple según un orden fijado de antemano: M1 menor `C`; M2 mayor `k`, luego `uniform`, luego `euclidean`; M3 menor `max_depth`, luego mayor `min_samples_leaf`, luego `gini`; M4 menor `max_depth` (`None` = máximo), luego mayor `min_samples_leaf`, luego `sqrt`; M5 menor `max_iter`, luego menor `max_leaf_nodes`.
4. **Estabilidad:** si el orden de los candidatos se invierte entre T1 y T2, o un fold domina la media, se marca como *inestable* y se interpreta con cautela. No se selecciona solo por la media si la inestabilidad es extrema; ese caso se documenta, sin threshold numérico predefinido.
5. Ningún hiperparámetro se elige con VALIDATION ni con TEST.

## 15. Métricas (convenciones congeladas)

Detalle en `reports/ml/ml_metrics_spec_v0.1.csv`.

**Primaria — Multiclass log loss** (menor es mejor):
`LL = −(1/N) Σ_i ln p_{i, y_i}`
- logaritmo natural;
- probabilidades recortadas a `[1e-15, 1]` y renormalizadas por fila (convención de clipping que D39 delegó a ML);
- se reporta cuántas filas requirieron clipping.

Se elige como primaria porque usa toda la distribución, penaliza la confianza incorrecta y está alineada con el objetivo probabilístico.

**Secundarias probabilísticas:**
- **Brier multiclase:** `BS = (1/N) Σ_i Σ_{k∈{H,D,A}} (p_ik − y_ik)²`, con `y` one-hot. **No** se divide por K = 3; rango [0, 2]. Esta convención es **única en todo SCOPE**. Se calcula con una función propia y verificada, sin depender de la convención de ninguna librería.
- **Calibración:**
  - curvas de fiabilidad one-vs-rest por clase (H, D, A), con 10 bins por cuantiles de `p_k`;
  - *calibration-in-the-large* por clase: `mean(p_k) − mean(y_k)`;
  - ECE por clase con los mismos bins, solo descriptivo y sin agregarlo en un score.
- **No** se aplica calibración post-hoc (Platt, isotónica, temperatura…). Cualquier calibración requiere una decisión posterior.

**Clasificación** (clase = argmax con desempate H > D > A; `zero_division = 0`):
- accuracy;
- macro precision, macro recall y **macro F1**;
- weighted F1;
- matriz de confusión (filas = real, columnas = predicha, orden H, D, A);
- precision, recall y F1 por clase.

**Atención especial a `recall_D` y `F1_D`.** Por E2/E4 (D minoritaria, ≈ 22.5 % en TRAIN, con solapamiento univariado amplio) y E2m (el mercado nunca tiene a D como favorito), es previsible que argmax casi nunca prediga D. Se reporta tal cual. **No** se optimiza D en exclusiva.

Accuracy **nunca** es criterio único.

## 16. Regla de selección

Jerarquía predefinida, sin score compuesto ni pesos inventados:
1. **Primario:** menor log loss.
2. **Secundario:** Brier y calibración.
3. **Clasificación:** macro F1, con atención a D (recall_D, F1_D).
4. **Parsimonia:** si dos configuraciones son prácticamente equivalentes, se prefiere menos features, el modelo más simple, menor complejidad y mayor estabilidad temporal.

No se fija ahora una diferencia mínima numérica arbitraria. Como apoyo **descriptivo** para juzgar la equivalencia práctica en VALIDATION se reportará el intervalo bootstrap pareado (B = 2,000, semilla 42, remuestreo por partido) de la diferencia de log loss por partido entre configuraciones [ML-0]. Es evidencia para la interpretación, no una regla automática. Su limitación: los partidos no son independientes (equipos repetidos).

Universo de candidatos a la selección final: modelos M1–M4 (y M5 si se ejecutó) × representaciones **CORE**. Los baselines y las representaciones DIAGNOSTIC/OPTIONAL no son candidatos.

## 17. Validation (2024/25)

1. Para cada fila de la matriz (`modelo × representación`) se toma la configuración elegida por CV (§14), se reajusta en **TRAIN_FULL** (2021/22–2023/24), con scaler reajustado allí, y se puntúa **una vez** en VALIDATION.
2. Con esos resultados, ML-7 decide la configuración y el modelo final, la representación final, y la evidencia para P02 y P04 (con las reglas de §9, §10 y §16).
3. Se registran **todas** las comparaciones predefinidas, incluidas las desfavorables.
4. Se evitan iteraciones ilimitadas sobre VALIDATION: el número de configuraciones que la tocan está fijado por la matriz.
5. Si después de observar VALIDATION surge una hipótesis nueva (otra representación, otro grid, un ajuste para D…), se marca como **EXPLORATORIA**. No se incorpora en silencio al protocolo, y su evaluación no puede reemplazar la selección preregistrada sin una revisión explícita.
6. **Benchmark en VALIDATION:** las métricas del mercado en 2024/25 se calculan **después** de registrar la selección de ML-7, solo como contexto.

**Advertencia de optimismo:** el mejor de ~24 candidatos sobre 350 partidos tendrá un desempeño en VALIDATION optimista (sesgo de selección). La estimación no sesgada de la configuración congelada es la de TEST.

## 18. Final Test Policy (2025/26)

Antes de abrir TEST deben estar **congelados** y registrados:
- representación y features;
- preprocessing;
- hiperparámetros;
- modelo;
- criterio de predicción (argmax H > D > A);
- métricas y convenciones;
- tratamiento de Q01 (valores fuente, D49);
- decisiones sobre P02 y P04;
- calibración: ninguna, salvo decisión posterior aprobada antes del freeze;
- política de refit.

Después:
- se ejecuta **una sola evaluación final principal** sobre los 350 partidos elegibles de 2025/26, más el benchmark de mercado sobre exactamente los mismos partidos;
- **no se vuelve atrás** a modificar el modelo si TEST sale mal;
- cualquier análisis adicional sobre TEST se etiqueta como post hoc y no altera la configuración;
- el resultado se interpreta teniendo en cuenta el drift descrito en E10 (D42), sin cambiar el protocolo.

**Refit final (propuesta pendiente de aprobación) [ML-0]:**
- Tras elegir la configuración con TRAIN/VALIDATION, la configuración queda congelada.
- Antes de TEST, el modelo final **puede** reentrenarse con TRAIN + VALIDATION (2021/22–2024/25; 1,399 filas), reajustando todas las transformaciones solo con esos datos. TEST permanece completamente fuera del fit.
- Esta política **debe aprobarse explícitamente en ML-8, antes de abrir TEST**. Mientras no se apruebe, la alternativa por defecto es evaluar el modelo ajustado en TRAIN_FULL.
- Riesgo a sopesar: los hiperparámetros dependientes de n (k de KNN) se eligieron con n menor.
- Queda como propuesta por su relación con P06 (provisional). **No se ejecuta en ML-0.**

## 19. Benchmark de mercado

- MARKET permanece **fuera de X** (D12, T7).
- **Pre-match (`mkt_avg_pre_*`, AvgH/AvgD/AvgA):** benchmark externo **principal**.
- **Closing (`mkt_avg_close_*`, AvgCH/AvgCD/AvgCA):** benchmark externo **secundario**. No se supone que tenga la misma información temporal que SCOPE (D39).
- Probabilidades: `q_i = 1/o_i`, `p_i = q_i / Σ_j q_j`, con `ΣP = 1 ± 1e-9` (D39/E2m). Columnas en orden H, D, A.
- Se une a FEATURES por `match_id` desde CANONICAL y se evalúa sobre **exactamente** las mismas filas elegibles que el modelo, con las mismas métricas y convenciones.
- No se usa para entrenar, seleccionar features, decidir hiperparámetros, elegir modelo ni calibrar.
- "Ganar al mercado" **no** es condición de validez académica del modelo. La pregunta guía es qué tan cerca está un modelo puramente deportivo del consenso del mercado (contrato §10).

## 20. Reproducibilidad

- `RANDOM_SEED = 42` para todo algoritmo estocástico (DT, RF, HGB, bootstrap). `n_jobs = 1` para que los resultados sean deterministas.
- Orden de filas fijo, sin barajar (§11).
- Cada etapa ML registrará en su manifiesto:
  - versión de Python, pandas, NumPy y scikit-learn;
  - plataforma y semilla;
  - SHA-256 de las entradas (D44);
  - lista exacta de features, grid e hiperparámetros elegidos;
  - SHA-256 de cada output.
- ML-0 registra su estado en `reports/ml/ml0_protocol_manifest.json`.
- `python -m src.ml.ml_protocol` regenera las cuatro tablas de forma determinista. `--self-test` ejecuta los controles negativos.

## 21. Restricciones de Complejidad Computacional

- **[R] (lineamientos de Complejidad, D23):** los programas de KNN y regresión logística "hechos a mano, sin consulta de IA" los escribe el estudiante en Jupyter.
- El asesor **no** escribe esas implementaciones ni pseudocódigo evaluable equivalente. El formato del reporte de Complejidad pide el pseudocódigo de cada algoritmo, y también es tarea del estudiante.
- El asesor **sí** puede, más adelante: explicar teoría, revisar código escrito por el estudiante, señalar errores, analizar complejidad y comparar conceptualmente con las implementaciones de librería.
- Este protocolo usa **implementaciones de librería** (scikit-learn) para el experimento principal de ML. `src/ml/` **no** contiene ni contendrá implementaciones manuales. El notebook del estudiante debe vivir en una ubicación separada, que el estudiante elige y crea.
- Pendientes que afectan a Complejidad: **C04** (LR manual binaria H vs no-H o multinomial) y **C05** (submuestras de n para la medición de tiempos). P04-D5/P04-D10 siguen siendo los subconjuntos propuestos para estudiar el coste en función de `d`.

## 22. Preguntas abiertas

| Tema | Estado | Se resuelve en |
|---|---|---|
| P02 — valor incremental de last5 | Abierta | ML-7 (TRAIN CV + VALIDATION) |
| P04 — subconjuntos d = 5 / d = 10 | Provisional | ML-7; coordinación con Complejidad (C04/C05) |
| P06 — split temporal | Provisional (operativo vigente) | Revisión tras ML-7 / ML-8 |
| Refit final con TRAIN + VALIDATION | Propuesta | Aprobación explícita en ML-8 |
| Calibración post-hoc | No prevista en v0.1 | Solo con decisión posterior, antes del freeze |
| Inclusión de M5 (boosting) | Opcional | ML-6, con justificación metodológica |
| Sensibilidad burn-in k = 4 / 5 (nota D48) | Opcional | TRAIN/VAL; nunca TEST; no reabre D48 |
| Sensibilidad Q01: excluir las 3 filas elegibles afectadas (nota D49) | Opcional; no automática | Solo TRAIN (las filas afectadas son de 2021/22); nunca reinterpreta TEST |
| Ranked Probability Score (RPS), métrica ordinal habitual en fútbol | **Recomendación del asesor, no adoptada** | Revisión ML-0: si se adopta, solo como métrica informativa |
| Instalación de scikit-learn y fijación de versión | Pendiente | Inicio de ML-1 |
| C04, C05, C06 (rúbrica de ML; si una baseline cuenta como "modelo") | Pendientes docentes | Profesores |

## 23. Secuencia experimental futura

Numeración de trabajo ML (no son decisiones `Dxx`):

| Etapa | Contenido | Toca VALIDATION | Toca TEST |
|---|---|---|---|
| **ML-1** | Infraestructura mínima (carga verificada, métricas propias con tests, registro) + baselines B0/B1 en T1/T2 | No (solo CV) | No |
| **ML-2** | M1 Logistic Regression: grid en T1/T2 para CORE + R5/R6 + R7/R8 | No | No |
| **ML-3** | M2 KNN | No | No |
| **ML-4** | M3 Decision Tree | No | No |
| **ML-5** | M4 Random Forest | No | No |
| **ML-6** | M5 boosting (opcional, si se justifica) | No | No |
| **ML-7** | Refit en TRAIN_FULL de las configuraciones elegidas → VALIDATION; comparación consolidada; evidencia P02/P04; selección; después, benchmark de mercado en VALIDATION | **Sí (una vez por configuración)** | No |
| **ML-8** | Freeze final (configuración, refit policy, métricas) y registro | No | No |
| **ML-9** | FINAL TEST (una vez) + benchmark de mercado pre/close + análisis final | — | **Sí (una vez)** |

**Checks anti-leakage (dónde se aplican):**

| # | Check | ML-0 | ML-1+ |
|---|---|---|---|
| 1 | Targets nunca en X | `validate_representations` aborta | Aserción de columnas de X en cada fit |
| 2 | POST nunca en X | Ídem (lista POST + allowlist de 21 features) | Ídem |
| 3 | MARKET nunca en X | Ídem (`mkt_*`) | MARKET solo en el módulo de benchmark |
| 4 | Scaler ajustado solo en train | Regla §11 | Scaler dentro del `Pipeline` del fold |
| 5 | Hiperparámetros solo con TRAIN CV | Regla §14 | Registro por fold; VALIDATION sin grid |
| 6 | VALIDATION fuera de fit durante el CV | `validate_splits` aborta | Aserción de temporadas por fit |
| 7 | TEST fuera hasta el freeze | `validate_splits` aborta; split `LOCKED` | Carga de 2025/26 solo en ML-9 |
| 8 | Ventanas rolling ya precomputadas temporalmente | Heredado (T1–T10, V14/V15, D44) | No se recalculan features en ML |
| 9 | Sin reordenamientos que permitan leakage | Orden fijo D30, sin shuffle | Folds por temporada, nunca por fila aleatoria |
