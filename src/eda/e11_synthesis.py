"""E11 — Síntesis final del EDA v0.1 (ensamblaje y verificación; sin análisis nuevos).

No recalcula estadísticas. Verifica la consistencia estructural de lo ya aprobado y ensambla tres
tablas de síntesis (matriz de fases, estado de decisiones y requisitos de handoff a modelado):
  - hashes D44 y RAW (contra docs/data_dictionary/raw_manifest_v0.1.csv);
  - manifiesto EDA: fases E1–E10 presentes y todos sus outputs existentes con el SHA-256 registrado;
  - Decision Log: D46–D49 presentes, ninguna D50+; P01/P05/P08 cerradas (tachadas) y P02, P03, P04,
    P06, P07 vigentes (no tachadas); P02 sigue marcada PROVISIONAL tras E8.
Falla explícitamente (AssertionError) si falta una fase o una decisión o si P02/P04 cambian de estado.
El contenido textual de las tablas resume el reporte acumulativo y el Decision Log; no crea criterios.
Sin targets, sin aleatoriedad (seed = null).
"""
from __future__ import annotations

import hashlib
import json
import re

import pandas as pd

from src.config import settings
from src.eda import eda_io as io
from src.eda.e09_q01_anomaly import verify_raw

PHASE = "E11"
SCOPES = ["ALL_DESCRIPTIVE"]
SEED = None
NOTES = ("E11 síntesis final: verificación estructural (D44, RAW, manifiesto E1–E10, Decision Log D46–D49 y "
         "provisionales) y tablas de síntesis (fases, decisiones, handoff). Sin análisis nuevos, sin targets, "
         "sin modelado; TEST sin decisiones")
DECISION_LOG = settings.PROJECT_ROOT / "docs" / "DECISION_LOG.md"
EXPECTED_PHASES = ["E1", "E2", "E2m", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]
CLOSED_D = ["D46", "D47", "D48", "D49"]
CLOSED_P = ["P01", "P05", "P08"]
OPEN_P = ["P02", "P03", "P04", "P06", "P07"]


# ---------------------------------------------------------------------------
def verify_manifest() -> dict:
    m = json.loads(io.MANIFEST_FILE.read_text(encoding="utf-8"))
    missing = [p for p in EXPECTED_PHASES if p not in m["phases"]]
    assert not missing, f"Faltan fases en el manifiesto: {missing}"
    for ph in EXPECTED_PHASES:
        for o in m["phases"][ph]["outputs"]:
            p = settings.PROJECT_ROOT / o["path"]
            assert p.exists(), f"{ph}: falta {o['path']}"
            if not o["path"].endswith("eda_report_v0.1.md"):      # el reporte se actualiza en E11
                assert hashlib.sha256(p.read_bytes()).hexdigest() == o["sha256"], f"{ph}: hash distinto en {o['path']}"
    return m


def decision_rows() -> dict[str, str]:
    rows = {}
    for line in DECISION_LOG.read_text(encoding="utf-8").splitlines():
        mt = re.match(r"^\| (D\d{2}|P\d{2}|C\d{2}) \|(.*)$", line)
        if mt:
            rows[mt.group(1)] = mt.group(2)
    return rows


def verify_decisions(rows: dict[str, str]) -> None:
    for d in CLOSED_D:
        assert d in rows, f"Falta {d} en el Decision Log"
    extra = sorted(k for k in rows if k.startswith("D") and int(k[1:]) > 49)
    assert not extra, f"Decisiones inesperadas posteriores a D49: {extra}"
    for p in CLOSED_P:
        assert rows[p].lstrip().startswith("~~"), f"{p} debería estar cerrada (tachada)"
    for p in OPEN_P:
        assert p in rows and not rows[p].lstrip().startswith("~~"), f"{p} debería seguir vigente"
    assert "sigue PROVISIONAL" in rows["P02"], "P02 cambió de estado"
    assert "Cerrada" not in rows["P04"], "P04 cambió de estado"


# ---------------------------------------------------------------------------
PHASE_SUMMARY = [
    ("E0", "¿Cómo se organiza el EDA sin violar la temporalidad ni D42?", "Plan E1–E11; scopes ALL/DEVX/TRAIN/VAL/TEST; eda_io con verificación D44 y output guard (whitelist); 20 tests EDA",
     "Infraestructura reproducible y separación estricta de scopes", "—", "infraestructura", "Todas las fases leen datos congelados y escriben solo en reports/eda/", "—"),
    ("E1", "¿Estructura, missingness y elegibilidad coinciden con el contrato?", "1,900 × 42 / 30 / 3,800; 21 features con 50 nulos estructurales (n_prev = 0); 1,749 elegibles (350/350/349/350/350); 13 dq_flags",
     "Sin missingness inesperado; elegibilidad reproduce la regla; last5 muy discreta", "—", "descriptivo", "Dataset elegible sin nulos: no requiere imputación con k = 3", "ALL"),
    ("E2", "¿Cómo se distribuyen los targets?", "TRAIN H 45.8 % / D 22.5 % / A 31.7 %; GD entera, mediana 0, DE 1.99; ventaja local descriptiva en todos los bloques",
     "Clases no uniformes (D minoritaria); GD discreta, no normal por construcción", "P03 (abierta)", "descriptivo", "Métricas multiclase sensibles a D; diagnóstico de residuos OLS en Matemáticas", "ALL / TRAIN"),
    ("E2m", "¿Qué describe el benchmark de mercado?", "Normalización D39 con Σp = 1; overround medio 4.52 % pre / 4.32 % close, mayor en 2024/25 y 2025/26; p_D concentrada (≤ 0.323); D nunca favorito; L1/2 mediano ≈ 1.8 pp",
     "Mercado completo y coherente; benchmark externo, no predictor", "D12, D13, D39", "descriptivo", "Comparación SCOPE vs mercado sobre los mismos partidos elegibles; atención a la clase D", "ALL"),
    ("E3", "¿Cómo se comportan las features individualmente?", "0 violaciones de dominio bajo las reglas evaluadas (Q01 se trata en E9); 311 extremos legítimos concentrados con poco historial; DE season 1.6–1.8× mayor con n 3–5; diff centradas en 0; last5 13–19× menos valores únicos",
     "Features regulares; ruido temprano y discreción de last5 son las propiedades clave", "—", "descriptivo", "Escalado relevante para KNN/lineales (ajustado solo en train); empates en distancias/cortes", "DEVX"),
    ("E4", "¿Qué relaciones hay entre features y con el target?", "h/a casi incorrelacionadas; ±0.7 con diff algebraico; PPG↔GF +0.82; season↔last5 0.73–0.78; TRAIN |r| con GD 0.17–0.41 (diff > h ≥ a; season > last5); fuerte solapamiento H/D/A",
     "Asociaciones univariadas moderadas; D sin separación univariada clara", "—", "descriptivo", "Correlación no es selección; dificultad de D a evaluar multivariadamente", "DEVX / TRAIN"),
    ("E5", "¿HADIFF tiene dependencia lineal exacta?", "Rango 14/21, nullity 7 con/sin intercepto y estandarización; R² auxiliar = 1; VIF finitos en HA y DIFF (máx ≈ 11.5 en ppg_season)",
     "M1 cerrada estructuralmente", "D46", "cerrado", "No usar HADIFF completo en lineales no regularizados; HA y DIFF candidatas distintas", "DEVX"),
    ("E6", "¿Qué relación estructural hay entre season y last5?", "Identidad exacta en n_prev ≤ 5 (diff: max(h_n, a_n) ≤ 5); fuera de ella Pearson ≈ 0.64–0.75 y MAE creciente; rango completo season+last5",
     "M3 cerrada estructuralmente; distintas fuera de la zona inicial", "D47", "cerrado", "No hay dependencia exacta; la utilidad de last5 queda para P02", "DEVX"),
    ("E7", "¿Qué burn-in equilibra estabilidad y observaciones?", "Coste 40 DEVX / 30 TRAIN por paso desde 2→3; MAE PPG frente a referencia 1.17 / 0.73 / 0.58 / 0.52 / 0.48; 2→3 último paso con mejora respaldada en la mayoría de métricas",
     "k = 3 por parsimonia y rendimientos decrecientes; no es un óptimo", "D48", "cerrado", "Sensibilidad k = 4/5 opcional en modelado (TRAIN/VAL, nunca TEST)", "DEVX / TRAIN"),
    ("E8", "¿last5 aporta forma reciente plausible?", "≈ 3.7–4.3× más responsiva; Spearman con el desempeño del partido menor que season en PPG y GF (IC de la diferencia < 0); delta last5 − season sin persistencia clara (indicio débil en GA)",
     "last5 distinta y responsiva, sin señal reciente propia univariada; ni confirmada ni descartada", "P02 (abierta)", "abierto", "Comparación incremental season vs season + last5 en modelado (TRAIN/VAL)", "DEVX / TRAIN"),
    ("E9", "¿Qué es Q01 y cuánto se propaga?", "1 fila AST > AS (AS = 8, AST = 9) presente en RAW; 0 HST > HS; 5 partidos posteriores de West Ham afectados (3 elegibles, TRAIN) solo en sot_pg_last5 y su diff",
     "Inconsistencia de fuente; campo erróneo desconocido", "D49", "cerrado", "v0.1 conserva valores fuente + flag; sin reparación ni exclusión automática", "ALL"),
    ("E10", "¿Cuánto cambian las features entre temporadas y bloques?", "Pico 2023/24 en GF/GA/SOT (SMD +0.27 a +0.41), persistente en equipos comunes; TRAIN→VAL |SMD| ≤ 0.030 con cambios de forma en GF season; TEST más bajo y menos disperso (SOT ≈ −0.29); diff estables",
     "Cambios de nivel/distribución observados entre temporadas (compatibles con variación de la liga y composición; sin demostración causal); sin indicio técnico de pipeline; TEST solo descriptivo", "—", "descriptivo", "Interpretar el desempeño final teniendo en cuenta la diferencia de TEST; TRAIN heterogéneo", "ALL / DEVX / TEST"),
]

DECISIONS = [
    ("M1 — representación h/a/diff", "D46", "CERRADA", "E5: rango 14/21, nullity 7", "No usar HADIFF completo en lineales no regularizados; HA y DIFF siguen candidatas"),
    ("M3 — season vs last5", "D47", "CERRADA", "E6: identidad exacta en n_prev ≤ 5 (diff: max ≤ 5); distintas fuera", "Estructura resuelta; utilidad predictiva en P02"),
    ("Burn-in (P01)", "D48", "CERRADA", "E7: rendimientos decrecientes desde 2→3 a coste constante", "k = 3; sensibilidad k = 4/5 opcional en TRAIN/VAL"),
    ("Q01 — AS/AST", "D49", "CERRADA", "E9: inconsistencia de fuente; propagación localizada", "Conservar valores fuente + flag; reparación futura solo con decisión y versionado"),
    ("Ventana last5", "P02", "ABIERTA (PROVISIONAL)", "E6 + E8: distinta y responsiva; menor asociación univariada que season; sin persistencia clara", "Comparación incremental season vs season + last5 en modelado (TRAIN/VAL)"),
    ("goal_difference como respuesta OLS", "P03", "ABIERTA (PROVISIONAL)", "E2: GD entera, discreta, colas algo pesadas", "Validación por residuos en la fase de Matemáticas (R)"),
    ("Subconjuntos d = 5 / d = 10", "P04", "ABIERTA (PROVISIONAL)", "E5 (VIF, rango), E8 (last5 en d = 5), E9 (diff_sot_pg_last5), E10 (diff más estables)", "Resolver en modelado con TRAIN/VAL; D22 y D23 (Complejidad) vigentes"),
    ("Split temporal", "P06", "ABIERTA (PROVISIONAL)", "Propuesta vigente Train 2021/22–2023/24, Val 2024/25, Test 2025/26 (D35, D42)", "Confirmar al iniciar el modelado; 2025/26 reservado como test final"),
    ("Zona horaria de kickoff_datetime", "P07", "ABIERTA (PROVISIONAL)", "Una sola liga y fuente en v0.1", "Definir al incorporar otras fuentes o ligas"),
    ("Web scraping en R (fuente complementaria)", "C01", "PENDIENTE DOCENTE", "Decision Log §3", "Confirmar con el profesor (Matemáticas)"),
    ("Mínimo de 200 observaciones", "C02", "PENDIENTE DOCENTE", "Decision Log §3", "Confirmar con el profesor (Matemáticas)"),
    ("Limpieza inicial durante el scraping", "C03", "PENDIENTE DOCENTE", "Decision Log §3", "Confirmar con el profesor (Matemáticas)"),
    ("Regresión logística manual: binaria o multinomial", "C04", "PENDIENTE DOCENTE", "Decision Log §3", "Confirmar con el profesor (Complejidad)"),
    ("Medición de tiempos con n ≈ 1,749", "C05", "PENDIENTE DOCENTE", "Decision Log §3", "Confirmar con el profesor (Complejidad)"),
    ("Rúbricas no disponibles (ML, PyE, Java; BD parcial)", "C06", "PENDIENTE DOCENTE", "Decision Log §3", "Revisar el contrato cuando lleguen"),
]

HANDOFF = [
    ("TRAIN = 2021/22–2023/24, VALIDATION = 2024/25, FINAL TEST = 2025/26", "P06 (abierta, provisional); D35, D42", "Protocolo operativo temporal vigente; no es una decisión formal cerrada", "TRAIN/VAL/TEST", "PROTOCOLO OPERATIVO VIGENTE (PROVISIONAL, P06 ABIERTA)"),
    ("TEST nunca se usa para selección, umbrales, escalado, calibración ni tratamiento de anomalías", "D35, D42", "2025/26 no es completamente ciego (descriptivos agregados ya vistos); solo evaluación final", "TEST", "OBLIGATORIO"),
    ("Burn-in k = 3: is_modeling_eligible = min(h_n_prev, a_n_prev) ≥ 3", "D48", "Parsimonia y rendimientos decrecientes (E7)", "TRAIN/VAL/TEST", "OBLIGATORIO"),
    ("Sensibilidad opcional con k = 4 / k = 5", "D48 (nota)", "Comprobar si el desempeño cambia materialmente; no reabre D48", "TRAIN/VAL", "OPCIONAL"),
    ("No usar HADIFF completo (h + a + diff) en modelos lineales no regularizados", "D46, D19", "Dependencia lineal exacta: rango 14/21", "TRAIN/VAL", "OBLIGATORIO"),
    ("Tratar HA y DIFF como representaciones distintas, no equivalentes", "D46, D22", "DIFF pierde niveles absolutos; comparación por desempeño pendiente", "TRAIN/VAL", "OBLIGATORIO"),
    ("Evaluar el valor incremental de last5: season frente a season + last5 (last5 sola solo como diagnóstico)", "P02", "E8 no confirma ni descarta last5", "TRAIN/VAL", "PENDIENTE"),
    ("Resolver P04 (subconjuntos d = 5 / d = 10)", "P04, D22, D23", "Depende de representación y de P02", "TRAIN/VAL", "PENDIENTE"),
    ("Cada modelo declara su feature subset explícito", "D19", "Reglas M1–M4 del contrato", "TRAIN/VAL", "OBLIGATORIO"),
    ("Escalado, si se usa, ajustado solo con train", "Contrato T8", "Escalas distintas (SOT ≈ 4.5 frente a PPG ≈ 1.4); KNN sensible", "TRAIN", "OBLIGATORIO"),
    ("Baseline obligatoria en la comparación", "Instrucciones del proyecto", "Referencia mínima frente a la que medir cualquier modelo", "TRAIN/VAL", "DECISIÓN DEL EQUIPO"),
    ("Al menos 4 modelos (iniciales considerados: baseline, regresión logística multinomial, KNN, árbol de decisión, Random Forest)", "Requisito docente comunicado; respaldo documental/rúbrica pendiente (C06)", "Algoritmos más complejos solo con justificación metodológica", "TRAIN/VAL", "REQUISITO DOCENTE COMUNICADO (RESPALDO DOCUMENTAL PENDIENTE, C06)"),
    ("KNN y regresión logística de Complejidad implementados a mano por el estudiante, sin IA", "D23 [R]", "Requisito de rúbrica", "—", "OBLIGATORIO (RÚBRICA)"),
    ("Métricas multiclase: matriz de confusión, precision/recall/F1 por clase, además de accuracy", "Instrucciones del proyecto; E2 (D minoritaria)", "Un clasificador que nunca predice D puede parecer aceptable en accuracy", "VAL/TEST", "DECISIÓN DEL EQUIPO"),
    ("Métricas probabilísticas: log loss, Brier multiclase y calibración", "Contrato §10 y §12 (convención exacta a definir en ML)", "El objetivo son probabilidades P(H), P(D), P(A)", "VAL/TEST", "OBLIGATORIO"),
    ("Mercado solo como benchmark externo (pre principal, close secundario), sobre los mismos partidos elegibles", "D12, D13, D39", "MARKET no es predictor en v0.1", "VAL/TEST", "OBLIGATORIO"),
    ("Q01 no se corrige en v0.1; exclusión solo como sensibilidad opcional", "D49", "Campo erróneo desconocido", "TRAIN", "OBLIGATORIO"),
    ("Interpretar el desempeño en TEST teniendo en cuenta su diferencia de distribución (E10)", "D42; E10", "TEST más bajo y menos disperso en GF/GA/SOT; no modifica el protocolo", "TEST", "DESCRIPTIVO"),
]


def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    verify_raw()
    verify_manifest()
    rows = decision_rows()
    verify_decisions(rows)
    phases = pd.DataFrame(PHASE_SUMMARY, columns=["phase", "question", "main_evidence", "conclusion", "decision_id",
                                                  "status", "downstream_implication", "scope"])
    assert list(phases["phase"]) == ["E0"] + EXPECTED_PHASES
    dec = pd.DataFrame(DECISIONS, columns=["topic", "id", "status", "evidence", "decision_or_next_step"])
    for i in dec["id"]:
        assert i in rows, f"{i} no está en el Decision Log"
    hand = pd.DataFrame(HANDOFF, columns=["requirement", "source_decision", "rationale", "scope", "status"])
    tables = {"e11_eda_phase_summary": phases, "e11_decision_status": dec, "e11_modeling_handoff": hand}
    outputs = [io.write_table(t, name, phase=PHASE, scope=io.ALL_DESCRIPTIVE, out_root=out_root) for name, t in tables.items()]
    assert io.verify_frozen_inputs() == input_hashes
    return outputs, input_hashes, tables
