"""Tests de M2 (KNN, ML-3).

Ejecutar desde la raíz de SCOPE/ con el entorno ML:
    ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_knn -v
Datos sintéticos salvo en los tests de alcance, que leen solo TRAIN de FEATURES v0.1 (D44).
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from src.eda import eda_io
from src.ml import knn_model as KM
from src.ml import metrics as M
from src.ml import run_ml1 as R
from src.ml import run_ml2 as R2
from src.ml import run_ml3 as R3


def _synthetic(n=240, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3)) * [1.0, 4.0, 0.3] + [0.0, 20.0, -2.0]
    y = np.where(X[:, 0] > 0.5, "H", np.where(X[:, 0] < -0.5, "A", "D")).tolist()
    return X, y


class TestPipelineAndGrid(unittest.TestCase):
    def test_grid_is_frozen_and_has_32_fits(self):
        self.assertEqual(KM.K_GRID, (11, 21, 51, 101))
        self.assertEqual(KM.WEIGHTS_GRID, ("uniform", "distance"))
        self.assertEqual(len(KM.GRID), 8)
        self.assertEqual(len(R3.REPRESENTATIONS) * len(KM.GRID) * 2, R3.EXPECTED_FITS)
        with self.assertRaises(ValueError):
            KM.make_pipeline(5, "uniform")
        with self.assertRaises(ValueError):
            KM.make_pipeline(11, "manhattan")

    def test_pipeline_structure(self):
        pipe = KM.make_pipeline(21, "distance")
        self.assertEqual([n for n, _ in pipe.steps], ["scaler", "knn"])
        knn = pipe.named_steps["knn"]
        self.assertEqual((knn.n_neighbors, knn.weights, knn.metric, knn.algorithm), (21, "distance", "euclidean", "auto"))

    def test_scaler_fitted_only_on_train(self):
        X, y = _synthetic()
        Xtr, ytr, Xev = X[:150], y[:150], X[150:] * 3 + 50
        pipe = KM.make_pipeline(11, "uniform")
        KM.fit(pipe, Xtr, ytr)
        np.testing.assert_allclose(pipe.named_steps["scaler"].mean_, Xtr.mean(axis=0))
        np.testing.assert_allclose(pipe.named_steps["scaler"].scale_, Xtr.std(axis=0))
        before = pipe.named_steps["scaler"].mean_.copy()
        KM.predict_proba_hda(pipe, Xev)
        np.testing.assert_array_equal(pipe.named_steps["scaler"].mean_, before)

    def test_class_order_and_probability_validity(self):
        X, y = _synthetic(seed=1)
        pipe = KM.make_pipeline(11, "uniform")
        KM.fit(pipe, X, y)
        self.assertEqual(list(pipe.classes_), ["A", "D", "H"])
        P_lib, P = pipe.predict_proba(X), KM.predict_proba_hda(pipe, X)
        for k, c in enumerate(M.CLASS_ORDER):
            np.testing.assert_array_equal(P[:, k], P_lib[:, list(pipe.classes_).index(c)])
        self.assertTrue(np.isfinite(P).all() and (P >= 0).all() and (P <= 1).all())
        np.testing.assert_allclose(P.sum(axis=1), 1.0, atol=1e-12)
        # uniform con k = 11: probabilidades múltiplos de 1/11
        np.testing.assert_allclose(P * 11, np.round(P * 11), atol=1e-9)
        self.assertGreater(np.corrcoef(X[:, 0], P[:, 0])[0, 1], 0.8)    # x0 alto → H

    def test_reproducible(self):
        X, y = _synthetic(seed=2)
        a, b = KM.make_pipeline(21, "distance"), KM.make_pipeline(21, "distance")
        KM.fit(a, X, y); KM.fit(b, X, y)
        np.testing.assert_array_equal(KM.predict_proba_hda(a, X), KM.predict_proba_hda(b, X))

    def test_rejects_missing_values(self):
        X, y = _synthetic()
        X[0, 0] = np.nan
        with self.assertRaises(ValueError):
            KM.fit(KM.make_pipeline(11, "uniform"), X, y)


class TestProbabilityEdgeCases(unittest.TestCase):
    def test_probabilistic_ties_resolved_h_over_d_over_a(self):
        # Empate exacto de probabilidades → la regla de SCOPE (argmax H > D > A), no un desempate interno
        P = np.array([[4 / 11, 4 / 11, 3 / 11], [3 / 11, 4 / 11, 4 / 11], [5 / 11, 1 / 11, 5 / 11]])
        P = P / P.sum(axis=1, keepdims=True)
        self.assertEqual(M.predicted_labels(P), ["H", "D", "H"])

    def test_zero_probability_counted_and_clipped(self):
        y = ["H", "D", "A"]
        P = np.array([[0.0, 6 / 11, 5 / 11], [0.5, 0.5, 0.0], [0.2, 0.3, 0.5]])
        z = KM.zero_probability_stats(y, P)
        self.assertEqual(z["n_true_class_prob_zero"], 1)                 # H recibió 0
        self.assertEqual(z["n_rows_any_prob_zero"], 2)
        self.assertEqual(z["n_prob_entries_zero"], 2)
        ll = M.log_loss(y, P)
        self.assertEqual(ll["n_clipped"], 2)
        self.assertTrue(math.isfinite(ll["log_loss"]))
        self.assertGreater(ll["log_loss"], 34.0 / 3)                      # ≈ −ln(1e-15)/3 domina

    def test_distance_weights_memorize_training_points(self):
        # in-sample con weights='distance': cada punto es su propio vecino a distancia 0 → P = one-hot
        X, y = _synthetic(seed=3)
        pipe = KM.make_pipeline(11, "distance")
        KM.fit(pipe, X, y)
        P = KM.predict_proba_hda(pipe, X)
        self.assertEqual(KM.zero_distance_neighbors(pipe, X), len(X))
        self.assertAlmostEqual(M.log_loss(y, P)["log_loss"], 0.0, delta=1e-9)


class TestSelection(unittest.TestCase):
    def _rows(self, means):
        return [{"n_neighbors": k, "weights": w, "fold": f, "log_loss": m + (0.02 if f == "T1" else -0.02)}
                for (k, w), m in means.items() for f in ("T1", "T2")]

    def test_selects_min_mean(self):
        means = {cfg: 1.0 for cfg in KM.GRID}
        means[(51, "distance")] = 0.98
        s = KM.select_config(self._rows(means))
        self.assertEqual((s["n_neighbors"], s["weights"], s["tie"]), (51, "distance", False))

    def test_tie_prefers_larger_k_then_uniform(self):
        means = {cfg: 1.0 for cfg in KM.GRID}
        for cfg in ((21, "distance"), (51, "distance"), (51, "uniform")):
            means[cfg] = 0.97
        s = KM.select_config(self._rows(means))
        self.assertEqual((s["n_neighbors"], s["weights"], s["tie"]), (51, "uniform", True))

    def test_requires_complete_grid(self):
        rows = self._rows({cfg: 1.0 for cfg in KM.GRID})[:-1]
        with self.assertRaises(ValueError):
            KM.select_config(rows)


class TestScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()
        cls.feats = {r: KM.representation_features(r) for r in R3.REPRESENTATIONS}
        cls.rows = R2.load_train_with_features(sorted({c for f in cls.feats.values() for c in f}))

    def test_representations_and_train_only(self):
        self.assertEqual(self.feats["R1"], ("diff_ppg_season", "diff_gf_pg_season", "diff_ga_pg_season"))
        self.assertEqual(len(self.feats["R3"]), 6)
        self.assertEqual(len(self.rows), 1049)
        self.assertEqual({r["season"] for r in self.rows}, set(eda_io.SEASONS_TRAIN_DESIGN))

    def test_folds_exclude_validation_and_test(self):
        folds = R.build_folds(self.rows)
        self.assertEqual([(f["fold"], len(f["train"]), len(f["eval"])) for f in folds],
                         [("T1", 350, 350), ("T2", 700, 349)])
        for f in folds:
            self.assertFalse({r["season"] for r in f["train"] + f["eval"]}
                             & {eda_io.SEASON_VALIDATION, eda_io.SEASON_FINAL_TEST})
            self.assertLessEqual(max(KM.K_GRID), len(f["train"]))      # k = 101 ≤ 350


if __name__ == "__main__":
    unittest.main()
