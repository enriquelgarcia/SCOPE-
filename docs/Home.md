---

# SCOPE

**Sports Computational Outcome Prediction Engine**

Sistema de análisis y predicción de resultados deportivos basado en datos históricos.  
La versión v0.1 trabaja con partidos de la Premier League y utiliza una arquitectura temporal diseñada para evitar _data leakage_.

---

## Estado actual

**Data Pipeline v0.1:** ✅ COMPLETED / FROZEN  
**Documentación de arquitectura:** ✅ APPROVED  
**Documentación del pipeline:** ✅ APPROVED  
**Fase actual:** 🟡 Preparación de EDA  
**Modelos entrenados:** No todavía

Flujo actual:

`RAW → INTERIM → CANONICAL → team_match_log → FEATURES → EDA → MODELS → PREDICTIONS`

Los artefactos hasta FEATURES están congelados mediante D44.

---

## Documentación principal

### Arquitectura

- [[Documentacion del proyecto/01_arquitectura_y_data_contract|01 — Arquitectura y Data Contract]]
    
- [[contract/SCOPE_Data_Contract_v0.1|SCOPE Data Contract v0.1]]
    

### Pipeline

- [[Documentacion del proyecto/02_data_pipeline_v0.1|02 — Data Pipeline v0.1]]
    
- [[validation/validation_spec_v0.1|Validation Spec v0.1]]
    
- [[quality/data_quality_register_v0.1|Data Quality Register v0.1]]
    

### Decisiones

- [[DECISION_LOG|Decision Log]]
    

---

## Datos y diccionarios

- [[data_dictionary/raw_manifest_v0.1|RAW Manifest]]
    
- [[data_dictionary/raw_dictionary_v0.1|RAW Dictionary]]
    
- [[data_dictionary/team_mapping_v0.1|Team Mapping]]
    

### Snapshot v0.1

- 5 temporadas completas
    
- 2021/22 → 2025/26
    
- 1,900 partidos
    
- 27 equipos distintos
    
- Fuente principal: Football-Data.co.uk
    

---

## Arquitectura de datos

### RAW

Datos originales e inmutables.

### INTERIM

Unificación técnica de las temporadas manteniendo trazabilidad y fidelidad con RAW.

### CANONICAL

Representación oficial de un partido dentro de SCOPE.

### team_match_log

Representación de cada partido desde la perspectiva individual de cada equipo.

### FEATURES

Variables históricas disponibles antes de cada partido.

---

## Artefactos congelados

|Capa|Dimensiones|
|---|---|
|INTERIM|1,900 × 166|
|CANONICAL|1,900 × 42|
|team_match_log|3,800 × 10|
|FEATURES|1,900 × 30|

Partidos actualmente elegibles para modelado:

**1,749**

Regla provisional:

`min(h_n_prev_season, a_n_prev_season) ≥ 3`

---

## Decisiones clave

### D42 — Disciplina sobre 2025/26

La temporada 2025/26 es el test final de v0.1.

Puede utilizarse para análisis descriptivo y documentación, pero **no debe influir en decisiones de diseño**, incluyendo:

- selección de features;
    
- burn-in;
    
- transformaciones;
    
- modelos;
    
- hiperparámetros;
    
- calibración.
    

Las decisiones de desarrollo deben utilizar únicamente:

**2021/22–2024/25**

---

### D44 — Freeze del Data Pipeline v0.1

Checkpoints A, B y C aprobados.

Los artefactos:

- INTERIM
    
- CANONICAL
    
- team_match_log
    
- FEATURES
    

quedan congelados para v0.1.

---

### D45 — Alineación documental de V14

La especificación del test de perturbación V14 fue alineada con la implementación efectivamente validada.

Es una corrección exclusivamente documental y no modifica el pipeline ni sus artefactos.

---

## Validación temporal

Las principales defensas contra _data leakage_ son:

- **V14 — Test de perturbación**
    
- **V15 — Oráculo independiente**
    

Principio temporal central:

`kickoff_datetime(m') < kickoff_datetime(t)`

Un partido solo puede utilizar información de encuentros que comenzaron estrictamente antes que él.

---

## Cuestiones abiertas para EDA

### P01 — Burn-in

Umbral actual:

`n_prev_season ≥ 3`

Sigue siendo provisional.

---

### P02 — Ventana last5

La ventana de cinco partidos sigue siendo provisional y deberá evaluarse durante EDA.

---

### M1 — Representación h / a / diff

Para una misma métrica:

`diff_x = h_x - a_x`

En modelos lineales no deben introducirse simultáneamente:

`h_x + a_x + diff_x`

por dependencia lineal perfecta.

---

### M3 — season vs last5

Mientras `n_prev_season ≤ 5`, las métricas de temporada y las métricas `last5` coinciden.

El EDA deberá estudiar:

- correlación;
    
- redundancia;
    
- VIF;
    
- comportamiento según cantidad de historial disponible.
    

---

### Q01 — AST > AS

Existe una anomalía conocida en Newcastle – West Ham 2021/22:

`AS = 8`  
`AST = 9`

El valor se conserva sin corregir.

Su posible efecto sobre `sot_pg_last5` deberá evaluarse durante EDA.

---

## Próxima fase — EDA

Objetivos principales:

- comprender la estructura de FEATURES;
    
- estudiar distribuciones;
    
- estudiar targets;
    
- analizar missingness y elegibilidad;
    
- evaluar redundancias;
    
- estudiar relaciones entre features;
    
- analizar posibles outliers;
    
- evaluar P01 y P02 exclusivamente con datos de desarrollo;
    
- preparar subconjuntos razonables para modelado.
    

**No entrenar modelos todavía.**

---

## Áreas del proyecto

### Ciencia de Datos / Machine Learning

EDA, feature analysis, clasificación H/D/A y evaluación probabilística.

### Matemáticas Aplicadas

EDA, correlaciones y regresión lineal múltiple sobre:

`goal_difference`

### Probabilidad y Estadística

Distribuciones, probabilidades, evaluación e interpretación estadística.

### Complejidad Computacional

KNN y regresión logística manuales, análisis de coste y comparación de representaciones.

### Bases de Datos

Modelo relacional, integridad, consultas y persistencia.

### Programación

Aplicación Java y consumo de datos/resultados de SCOPE.

---

## Navegación rápida

**Arquitectura**  
→ [[Documentacion del proyecto/01_arquitectura_y_data_contract|Documento 01]]

**Pipeline**  
→ [[Documentacion del proyecto/02_data_pipeline_v0.1|Documento 02]]

**Contrato**  
→ [[contract/SCOPE_Data_Contract_v0.1|Data Contract]]

**Decisiones**  
→ [[DECISION_LOG|Decision Log]]

**Validaciones**  
→ [[validation/validation_spec_v0.1|Validation Spec]]

**Calidad de datos**  
→ [[quality/data_quality_register_v0.1|Data Quality Register]]

---

## Estado

**SCOPE Data Pipeline v0.1 — COMPLETED / FROZEN**

**Current focus → EDA**