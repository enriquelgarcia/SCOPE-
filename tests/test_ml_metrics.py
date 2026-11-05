"""Tests del motor de métricas de SCOPE ML (src/ml/metrics.py).

Ejecutar desde la raíz de SCOPE/:  python -m unittest tests.test_ml_metrics -v
Las contrapruebas contra scikit-learn se omiten si no está instalado; `src.ml.run_ml1` exige
que NINGÚN test se omita antes de calcular métricas reales.

Tolerancias: 1e-12 para comparaciones entre implementaciones del mismo cálculo en float64
(diferencias esperadas del orden de 1e-16 por orden de suma); valores exactos con assertEqual.
"""
from __future__ import annotations

import math
import unittest

import numpy as np
import pandas as pd

from src.ml import metrics as M

try:
    import sklearn.metrics as skm
    HAS_SKLEARN = True
except ImportError:          # pragma: no cover
    HAS_SKLEARN = False

TOL = 1e-12
H, D, A = M.CLASS_ORDER


def _random_case(n=400, seed=0, ties=True):
    rng = np.random.default_rng(seed)
    y = rng.choice(list(M.CLASS_ORDER), size=n, p=[0.45, 0.25, 0.30]).tolist()
    P = rng.dirichlet([2, 1, 1.5], size=n)
    if ties:                                            # forzar empates de score (como last5/KNN)
        P = np.round(P, 1)
        P = np.clip(P, 0.0, 1.0)
        P = P / P.sum(axis=1, keepdims=True)
    return y, P


# ---------------------------------------------------------------------------
# ROC-AUC: los cinco tests obligatorios del protocolo (§23)
# ---------------------------------------------------------------------------
class TestRocAucProtocol(unittest.TestCase):
    def test_1_class_mapping(self):
        # Matriz construida a mano (cálculo de AUC por pares en comentarios):
        #   columna H: H = {0.7, 0.6} > resto {0.3, 0.3, 0.2, 0.3}            → AUC_H = 1
        #   columna D: D = {0.05, 0.1} < resto {0.2, 0.3, 0.4, 0.5}           → AUC_D = 0
        #   columna A: A = {0.4, 0.2} frente a {0.1, 0.1, 0.65, 0.6}: 2/4 y 2/4 → AUC_A = 0.5
        y = [H, H, D, D, A, A]
        P = np.array([[0.7, 0.2, 0.1], [0.6, 0.3, 0.1], [0.3, 0.05, 0.65], [0.3, 0.1, 0.6],
                      [0.2, 0.4, 0.4], [0.3, 0.5, 0.2]])
        r = M.roc_auc_ovr(y, P)
        self.assertEqual(r["roc_auc_H"], 1.0)
        self.assertEqual(r["roc_auc_D"], 0.0)
        self.assertEqual(r["roc_auc_A"], 0.5)
        self.assertEqual(r["roc_auc_ovr_macro"], 0.5)
        # La misma matriz expresada en el orden de una librería (A, D, H) se recupera por etiqueta
        lib = P[:, [2, 1, 0]]
        np.testing.assert_array_equal(M.align_proba(lib, ["A", "D", "H"]), P)
        self.assertEqual(M.roc_auc_ovr(y, M.align_proba(lib, ["A", "D", "H"])), r)
        # Columnas intercambiadas sin etiquetas → resultado distinto (el motor exige orden H, D, A)
        self.assertNotEqual(M.roc_auc_ovr(y, lib)["roc_auc_H"], r["roc_auc_H"])

    def test_2_perfect_prediction(self):
        y = [H, D, A, H, A, D, H]
        P = np.array([[1.0 if c == t else 0.0 for c in M.CLASS_ORDER] for t in y])
        r = M.roc_auc_ovr(y, P)
        for c in M.CLASS_ORDER:
            self.assertEqual(r[f"roc_auc_{c}"], 1.0)
        self.assertEqual(r["roc_auc_ovr_macro"], 1.0)

    def test_3_constant_probabilities(self):
        y = [H, D, A, H, H, A, D, A]
        P = np.tile([0.46, 0.23, 0.31], (len(y), 1))
        r = M.roc_auc_ovr(y, P)
        for c in M.CLASS_ORDER:
            self.assertEqual(r[f"roc_auc_{c}"], 0.5)
        self.assertEqual(r["roc_auc_ovr_macro"], 0.5)

    def test_4_absent_class_undefined(self):
        y = [H, A, H, A, A]                               # sin D
        P = np.tile([0.5, 0.2, 0.3], (len(y), 1))
        r = M.roc_auc_ovr(y, P)
        self.assertIsNone(r["roc_auc_D"])
        self.assertIsNone(r["roc_auc_ovr_macro"])
        self.assertIsNotNone(r["roc_auc_H"])
        y_all_h = [H, H, H]                               # una sola clase: H sin negativos
        r2 = M.roc_auc_ovr(y_all_h, np.tile([0.5, 0.2, 0.3], (3, 1)))
        self.assertTrue(all(r2[f"roc_auc_{c}"] is None for c in M.CLASS_ORDER))

    def test_5a_macro_equals_mean_of_per_class(self):
        y, P = _random_case(seed=1)
        r = M.roc_auc_ovr(y, P)
        self.assertAlmostEqual(r["roc_auc_ovr_macro"],
                               np.mean([r["roc_auc_H"], r["roc_auc_D"], r["roc_auc_A"]]), delta=TOL)

    @unittest.skipUnless(HAS_SKLEARN, "scikit-learn no instalado")
    def test_5b_matches_sklearn_crosscheck(self):
        for seed, ties in ((2, True), (3, False), (4, True)):
            y, P = _random_case(seed=seed, ties=ties)
            r = M.roc_auc_ovr(y, P)
            y_arr = np.array(y)
            for k, c in enumerate(M.CLASS_ORDER):           # AUC binario por clase
                self.assertAlmostEqual(r[f"roc_auc_{c}"], skm.roc_auc_score(y_arr == c, P[:, k]), delta=TOL)
            P_adh = P[:, [2, 1, 0]].copy()                  # COPIA reordenada a A, D, H
            sk_macro = skm.roc_auc_score(y_arr, P_adh, multi_class="ovr", average="macro", labels=["A", "D", "H"])
            self.assertAlmostEqual(r["roc_auc_ovr_macro"], sk_macro, delta=TOL)
            np.testing.assert_array_equal(P_adh[:, [2, 1, 0]], P)   # la original no se alteró

    @unittest.skipUnless(HAS_SKLEARN, "scikit-learn no instalado")
    def test_5c_sklearn_rejects_unordered_labels(self):
        # Documenta el motivo de la corrección de ML-0: labels=['H','D','A'] no es aceptado.
        y, P = _random_case(seed=5)
        with self.assertRaises(ValueError):
            skm.roc_auc_score(np.array(y), P, multi_class="ovr", labels=["H", "D", "A"])


# ---------------------------------------------------------------------------
# Log loss y Brier
# ---------------------------------------------------------------------------
class TestProbabilisticMetrics(unittest.TestCase):
    def test_brier_perfect_is_zero(self):
        y = [H, D, A]
        self.assertEqual(M.brier_multiclass(y, np.eye(3)), 0.0)

    def test_brier_completely_wrong_is_two(self):
        y = [H, D, A]
        P = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)
        self.assertEqual(M.brier_multiclass(y, P), 2.0)

    def test_brier_known_value(self):
        # (0.5−1)² + 0.3² + 0.2² = 0.38
        self.assertAlmostEqual(M.brier_multiclass([H], [[0.5, 0.3, 0.2]]), 0.38, delta=TOL)

    def test_log_loss_known(self):
        r = M.log_loss([H, D], [[0.5, 0.3, 0.2], [0.2, 0.4, 0.4]])
        self.assertAlmostEqual(r["log_loss"], -(math.log(0.5) + math.log(0.4)) / 2, delta=TOL)
        self.assertEqual(r["n_clipped"], 0)

    def test_log_loss_clipping_zero_probability(self):
        r = M.log_loss([H], [[0.0, 1.0, 0.0]])
        expected = -math.log(1e-15 / (1 + 2e-15))
        self.assertTrue(math.isfinite(r["log_loss"]))
        self.assertAlmostEqual(r["log_loss"], expected, delta=1e-9)
        self.assertEqual(r["n_clipped"], 1)

    @unittest.skipUnless(HAS_SKLEARN, "scikit-learn no instalado")
    def test_log_loss_matches_sklearn_without_clipping(self):
        y, P = _random_case(seed=6, ties=False)
        sk = skm.log_loss(np.array(y), P[:, [2, 1, 0]], labels=["A", "D", "H"])
        self.assertAlmostEqual(M.log_loss(y, P)["log_loss"], sk, delta=TOL)

    def test_brier_matches_explicit_loop(self):
        y, P = _random_case(seed=7)
        loop = np.mean([sum((P[i, k] - (1.0 if y[i] == c else 0.0)) ** 2 for k, c in enumerate(M.CLASS_ORDER))
                        for i in range(len(y))])
        self.assertAlmostEqual(M.brier_multiclass(y, P), loop, delta=TOL)

    def test_calibration_in_the_large(self):
        y = [H, H, D, A]
        P = np.tile([0.5, 0.25, 0.25], (4, 1))
        r = M.calibration_in_the_large(y, P)
        for c in M.CLASS_ORDER:
            self.assertAlmostEqual(r[f"citl_{c}"], 0.0, delta=TOL)

    def test_ece_constant_and_known(self):
        y = [H, H, D, A]
        self.assertTrue(all(abs(v) < TOL for v in M.ece_per_class(y, np.tile([0.5, 0.25, 0.25], (4, 1))).values()))
        # Dos grupos de p_H (0.2 y 0.8), cada uno con frecuencia observada 0.5 → ECE_H = 0.3
        y2 = [H, A, H, A]
        P2 = np.array([[0.2, 0.3, 0.5], [0.2, 0.3, 0.5], [0.8, 0.1, 0.1], [0.8, 0.1, 0.1]])
        self.assertAlmostEqual(M.ece_per_class(y2, P2)["ece_H"], 0.3, delta=TOL)
        rel = M.reliability_table(y2, P2)
        self.assertEqual(sum(r["n"] for r in rel if r["class"] == "H"), 4)


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------
class TestClassificationMetrics(unittest.TestCase):
    def test_confusion_matrix_order_hda(self):
        y = [H, H, D, A, A, A]
        P = np.array([[1, 0, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 1]], dtype=float)
        cm = M.confusion_matrix(y, P)
        np.testing.assert_array_equal(cm, [[1, 0, 1], [1, 0, 0], [0, 1, 2]])

    def test_argmax_tie_break_h_over_d_over_a(self):
        self.assertEqual(M.predicted_labels([[0.4, 0.4, 0.2], [0.3, 0.35, 0.35], [1 / 3, 1 / 3, 1 / 3]]),
                         [H, D, H])

    def test_model_never_predicting_draw(self):
        y = [H, D, A, D, H]
        P = np.array([[0.6, 0.3, 0.1], [0.5, 0.3, 0.2], [0.2, 0.3, 0.5], [0.45, 0.35, 0.2], [0.7, 0.2, 0.1]])
        m = M.classification_metrics(y, P)
        self.assertEqual(m["n_predicted_D"], 0)
        self.assertEqual((m["precision_D"], m["recall_D"], m["f1_D"]), (0.0, 0.0, 0.0))
        self.assertEqual(m["support_D"], 2)

    @unittest.skipUnless(HAS_SKLEARN, "scikit-learn no instalado")
    def test_classification_matches_sklearn(self):
        y, P = _random_case(seed=8)
        yhat = M.predicted_labels(P)
        m = M.classification_metrics(y, P)
        labels = list(M.CLASS_ORDER)
        p, r, f, s = skm.precision_recall_fscore_support(y, yhat, labels=labels, zero_division=0)
        for k, c in enumerate(labels):
            self.assertAlmostEqual(m[f"precision_{c}"], p[k], delta=TOL)
            self.assertAlmostEqual(m[f"recall_{c}"], r[k], delta=TOL)
            self.assertAlmostEqual(m[f"f1_{c}"], f[k], delta=TOL)
        self.assertAlmostEqual(m["accuracy"], skm.accuracy_score(y, yhat), delta=TOL)
        self.assertAlmostEqual(m["f1_macro"], skm.f1_score(y, yhat, labels=labels, average="macro",
                                                           zero_division=0), delta=TOL)
        self.assertAlmostEqual(m["f1_weighted"], skm.f1_score(y, yhat, labels=labels, average="weighted",
                                                              zero_division=0), delta=TOL)
        np.testing.assert_array_equal(M.confusion_matrix(y, P), skm.confusion_matrix(y, yhat, labels=labels))


# ---------------------------------------------------------------------------
# Validación de entradas
# ---------------------------------------------------------------------------
class TestInputValidation(unittest.TestCase):
    OK = [[0.5, 0.3, 0.2]]

    def test_rejects_negative_nan_and_bad_sums(self):
        for bad in ([[-0.1, 0.6, 0.5]], [[np.nan, 0.5, 0.5]], [[0.5, 0.3, 0.3]], [[np.inf, 0, 0]], [[1.2, -0.1, -0.1]]):
            with self.assertRaises(M.MetricsInputError):
                M.evaluate([H], bad)

    def test_rejects_wrong_shape_and_misalignment(self):
        with self.assertRaises(M.MetricsInputError):
            M.evaluate([H], [[0.5, 0.5]])
        with self.assertRaises(M.MetricsInputError):
            M.evaluate([H, D], self.OK)
        with self.assertRaises(M.MetricsInputError):
            M.evaluate([], np.zeros((0, 3)))

    def test_rejects_unknown_labels(self):
        with self.assertRaises(M.MetricsInputError):
            M.evaluate(["X"], self.OK)
        with self.assertRaises(M.MetricsInputError):
            M.evaluate(["h"], self.OK)                    # mayúsculas exactas

    def test_rejects_duplicate_ids_and_set_mismatch(self):
        with self.assertRaises(M.MetricsInputError):
            M.evaluate([H, D], [[0.5, 0.3, 0.2]] * 2, ids=["m1", "m1"])
        with self.assertRaises(M.MetricsInputError):
            M.align_labels(["m1", "m2"], {"m1": H, "m3": D})
        with self.assertRaises(M.MetricsInputError):
            M.align_labels(["m1", "m1"], {"m1": H})
        self.assertEqual(M.align_labels(["m2", "m1"], {"m1": H, "m2": D}), [D, H])

    def test_align_proba_rejects_incompatible_classes(self):
        with self.assertRaises(M.MetricsInputError):
            M.align_proba([[0.2, 0.3, 0.5]], ["H", "D", "X"])
        with self.assertRaises(M.MetricsInputError):
            M.align_proba([[0.2, 0.3, 0.5]], ["H", "H", "A"])

    def test_proba_from_frame_requires_named_columns(self):
        ok = pd.DataFrame({"match_id": ["m1"], "p_A": [0.2], "p_H": [0.5], "p_D": [0.3]})
        ids, P = M.proba_from_frame(ok)
        np.testing.assert_array_equal(P, [[0.5, 0.3, 0.2]])            # reordenado por nombre
        with self.assertRaises(M.MetricsInputError):
            M.proba_from_frame(pd.DataFrame({"match_id": ["m1"], "p0": [0.5], "p1": [0.3], "p2": [0.2]}))

    def test_evaluate_returns_all_protocol_metrics(self):
        y, P = _random_case(seed=9)
        m = M.evaluate(y, P)
        for k in ("log_loss", "brier", "roc_auc_ovr_macro", "accuracy", "precision_macro", "recall_macro",
                  "f1_macro", "f1_weighted", "recall_D", "f1_D", "citl_D", "ece_D", "n_clipped"):
            self.assertIn(k, m)


if __name__ == "__main__":
    unittest.main()
