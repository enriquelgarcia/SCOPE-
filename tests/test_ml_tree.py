"""Tests de M3 (Decision Tree, ML-4).

Ejecutar desde la raíz de SCOPE/ con el entorno ML:
    ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_tree -v
Datos sintéticos salvo en los tests de alcance, que leen solo TRAIN de FEATURES v0.1 (D44).
"""
from __future__ import annotations

import math
import unittest

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from src.eda import eda_io
from src.ml import metrics as M
from src.ml import run_ml1 as R
from src.ml import run_ml2 as R2
from src.ml import run_ml4 as R4
from src.ml import tree_model as TM


def _synthetic(n=400, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3)) * [1.0, 5.0, 0.5] + [0.0, 30.0, 2.0]
    y = np.where(X[:, 0] > 0.6, "H", np.where(X[:, 0] < -0.6, "A", "D"))
    flip = rng.random(n) < 0.15
    y = np.where(flip, rng.choice(["H", "D", "A"], size=n), y).tolist()
    return X, y


class TestModelAndGrid(unittest.TestCase):
    def test_grid_is_frozen_and_has_48_fits(self):
        self.assertEqual(TM.DEPTH_GRID, (2, 3, 4, 6))
        self.assertEqual(TM.LEAF_GRID, (25, 50, 100))
        self.assertEqual(len(TM.GRID), 12)
        self.assertEqual(len(R4.REPRESENTATIONS) * len(TM.GRID) * 2, R4.EXPECTED_FITS)
        for bad in ((None, 25), (8, 25), (3, 10)):
            with self.assertRaises(ValueError):
                TM.make_model(*bad)

    def test_tree_configuration_and_no_scaling(self):
        m = TM.make_model(4, 50)
        self.assertIsInstance(m, DecisionTreeClassifier)
        self.assertNotIsInstance(m, Pipeline)                       # sin StandardScaler
        self.assertEqual((m.criterion, m.splitter, m.random_state, m.class_weight, m.max_depth, m.min_samples_leaf),
                         ("gini", "best", 42, None, 4, 50))

    def test_invariant_to_monotone_rescaling(self):
        # justificación de no escalar: un reescalado afín positivo no cambia las predicciones del árbol
        X, y = _synthetic()
        a, b = TM.make_model(3, 25), TM.make_model(3, 25)
        TM.fit(a, X, y); TM.fit(b, X * [10.0, 0.01, 3.0] + [5.0, -2.0, 1.0], y)
        np.testing.assert_array_equal(TM.predict_proba_hda(a, X),
                                      TM.predict_proba_hda(b, X * [10.0, 0.01, 3.0] + [5.0, -2.0, 1.0]))

    def test_class_order_and_probability_validity(self):
        X, y = _synthetic(seed=1)
        m = TM.make_model(4, 25)
        TM.fit(m, X, y)
        self.assertEqual(list(m.classes_), ["A", "D", "H"])
        P_lib, P = m.predict_proba(X), TM.predict_proba_hda(m, X)
        for k, c in enumerate(M.CLASS_ORDER):
            np.testing.assert_array_equal(P[:, k], P_lib[:, list(m.classes_).index(c)])
        np.testing.assert_allclose(P.sum(axis=1), 1.0, atol=1e-12)
        self.assertGreater(np.corrcoef(X[:, 0], P[:, 0])[0, 1], 0.7)    # x0 alto → H

    def test_reproducible(self):
        X, y = _synthetic(seed=2)
        a, b = TM.make_model(6, 25), TM.make_model(6, 25)
        TM.fit(a, X, y); TM.fit(b, X, y)
        np.testing.assert_array_equal(TM.predict_proba_hda(a, X), TM.predict_proba_hda(b, X))
        self.assertEqual(TM.rules_text(a, ["f0", "f1", "f2"]), TM.rules_text(b, ["f0", "f1", "f2"]))

    def test_rejects_missing_values(self):
        X, y = _synthetic()
        X[5, 2] = np.inf
        with self.assertRaises(ValueError):
            TM.fit(TM.make_model(2, 25), X, y)


class TestStructure(unittest.TestCase):
    def test_depth_leaves_and_leaf_size_respect_grid(self):
        X, y = _synthetic(seed=3)
        for depth, leaf in TM.GRID:
            m = TM.make_model(depth, leaf)
            TM.fit(m, X, y)
            s = TM.structure(m)
            self.assertLessEqual(s["effective_depth"], depth)
            self.assertGreaterEqual(s["leaf_size_min"], leaf)
            self.assertLessEqual(s["n_leaves"], 2 ** depth)
            self.assertEqual(s["node_count"], 2 * s["n_leaves"] - 1)      # árbol binario
            self.assertLessEqual(s["n_distinct_leaf_distributions"], s["n_leaves"])

    def test_importances_sum_to_one(self):
        X, y = _synthetic(seed=4)
        m = TM.make_model(3, 25)
        TM.fit(m, X, y)
        imp = TM.importances(m, ["f0", "f1", "f2"])
        self.assertAlmostEqual(sum(imp.values()), 1.0, delta=1e-12)
        self.assertEqual(max(imp, key=imp.get), "f0")


class TestZeroProbabilities(unittest.TestCase):
    def test_pure_leaf_gives_zero_probability_and_is_clipped(self):
        # Hoja pura de H (x > 0) → P(D) = P(A) = 0; un partido A en esa región recibe probabilidad 0
        X = np.array([[1.0], [2.0], [3.0], [4.0], [-1.0], [-2.0], [-3.0], [-4.0]] * 4)
        y = (["H"] * 4 + ["A", "D", "A", "D"]) * 4
        m = DecisionTreeClassifier(max_depth=1, random_state=42).fit(X, y)
        P = M.align_proba(m.predict_proba(np.array([[2.5], [-2.5]])), m.classes_)
        z = TM.zero_probability_stats(["A", "D"], P)
        self.assertEqual(z["n_true_class_prob_zero"], 1)
        self.assertEqual(z["n_rows_any_prob_zero"], 2)
        ll = M.log_loss(["A", "D"], P)
        self.assertEqual(ll["n_clipped"], 2)
        self.assertTrue(math.isfinite(ll["log_loss"]) and ll["log_loss"] > 17.0)


class TestSelection(unittest.TestCase):
    def _rows(self, means):
        return [{"max_depth": d, "min_samples_leaf": lf, "fold": f, "log_loss": m + (0.01 if f == "T1" else -0.01)}
                for (d, lf), m in means.items() for f in ("T1", "T2")]

    def test_selects_min_mean(self):
        means = {cfg: 1.0 for cfg in TM.GRID}
        means[(4, 50)] = 0.99
        s = TM.select_config(self._rows(means))
        self.assertEqual((s["max_depth"], s["min_samples_leaf"], s["tie"]), (4, 50, False))

    def test_tie_prefers_smaller_depth_then_larger_leaf(self):
        means = {cfg: 1.0 for cfg in TM.GRID}
        for cfg in ((6, 100), (3, 25), (3, 100), (4, 50)):
            means[cfg] = 0.98
        s = TM.select_config(self._rows(means))
        self.assertEqual((s["max_depth"], s["min_samples_leaf"], s["tie"]), (3, 100, True))

    def test_requires_complete_grid(self):
        with self.assertRaises(ValueError):
            TM.select_config(self._rows({cfg: 1.0 for cfg in TM.GRID})[:-1])


class TestScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()
        cls.feats = {r: TM.representation_features(r) for r in R4.REPRESENTATIONS}
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
            self.assertLess(max(r["kickoff_datetime"] for r in f["train"]),
                            min(r["kickoff_datetime"] for r in f["eval"]))


if __name__ == "__main__":
    unittest.main()
