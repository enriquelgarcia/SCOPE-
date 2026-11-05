"""Tests de M4 (Random Forest, ML-5) y de la regla de ranking de familias de ML-0 §14.1.

Ejecutar desde la raíz de SCOPE/ con el entorno ML:
    ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_rf -v
Datos sintéticos salvo en los tests de alcance, que leen solo TRAIN de FEATURES v0.1 (D44).
"""
from __future__ import annotations

import unittest

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from src.eda import eda_io
from src.ml import metrics as M
from src.ml import random_forest_model as RFM
from src.ml import run_ml1 as R
from src.ml import run_ml2 as R2
from src.ml import run_ml5 as R5


def _synthetic(n=300, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3)) * [1.0, 5.0, 0.5] + [0.0, 30.0, 2.0]
    y = np.where(X[:, 0] > 0.6, "H", np.where(X[:, 0] < -0.6, "A", "D"))
    flip = rng.random(n) < 0.2
    return X, np.where(flip, rng.choice(["H", "D", "A"], size=n), y).tolist()


class TestModelAndGrid(unittest.TestCase):
    def test_grid_is_frozen_and_counts(self):
        self.assertEqual(RFM.DEPTH_GRID, (3, 5, 8))
        self.assertEqual(RFM.LEAF_GRID, (10, 25, 50))
        self.assertEqual(len(RFM.GRID), 9)
        self.assertEqual(len(R5.REPRESENTATIONS) * len(RFM.GRID) * 2, R5.EXPECTED_FITS)
        self.assertEqual(R5.EXPECTED_FITS * RFM.FIXED_PARAMS["n_estimators"], R5.EXPECTED_TREES)
        self.assertEqual(R5.EXPECTED_TREES, 5400)
        for bad in ((None, 25), (6, 25), (5, 100)):
            with self.assertRaises(ValueError):
                RFM.make_model(*bad)

    def test_fixed_params_and_no_scaling(self):
        m = RFM.make_model(5, 25)
        self.assertIsInstance(m, RandomForestClassifier)
        self.assertNotIsInstance(m, Pipeline)
        self.assertEqual((m.n_estimators, m.criterion, m.max_features, m.bootstrap, m.random_state, m.n_jobs,
                          m.class_weight, m.max_depth, m.min_samples_leaf),
                         (150, "gini", "sqrt", True, 42, 1, None, 5, 25))

    def test_fits_exactly_150_trees_and_structure_respects_grid(self):
        X, y = _synthetic()
        m = RFM.make_model(3, 10)
        RFM.fit(m, X, y)
        s = RFM.structure(m)
        self.assertEqual(s["n_trees"], 150)
        self.assertLessEqual(s["tree_depth_max"], 3)
        self.assertGreaterEqual(s["leaf_size_min_over_trees"], 10)

    def test_class_order_and_probability_validity(self):
        X, y = _synthetic(seed=1)
        m = RFM.make_model(5, 10)
        RFM.fit(m, X, y)
        self.assertEqual(list(m.classes_), ["A", "D", "H"])
        P_lib, P = m.predict_proba(X), RFM.predict_proba_hda(m, X)
        for k, c in enumerate(M.CLASS_ORDER):
            np.testing.assert_array_equal(P[:, k], P_lib[:, list(m.classes_).index(c)])
        self.assertTrue(np.isfinite(P).all() and (P >= 0).all() and (P <= 1).all())
        np.testing.assert_allclose(P.sum(axis=1), 1.0, atol=1e-12)
        self.assertGreater(np.corrcoef(X[:, 0], P[:, 0])[0, 1], 0.7)    # x0 alto → H

    def test_reproducible_with_seed(self):
        X, y = _synthetic(seed=2)
        a, b = RFM.make_model(8, 10), RFM.make_model(8, 10)
        RFM.fit(a, X, y); RFM.fit(b, X, y)
        np.testing.assert_array_equal(RFM.predict_proba_hda(a, X), RFM.predict_proba_hda(b, X))

    def test_rejects_missing_values(self):
        X, y = _synthetic()
        X[1, 1] = np.nan
        with self.assertRaises(ValueError):
            RFM.fit(RFM.make_model(3, 10), X, y)

    def test_metrics_through_common_engine(self):
        X, y = _synthetic(seed=3)
        m = RFM.make_model(5, 25)
        RFM.fit(m, X[:200], y[:200])
        P = RFM.predict_proba_hda(m, X[200:])
        r = M.evaluate(y[200:], P)
        self.assertAlmostEqual(r["log_loss"], M.log_loss(y[200:], P)["log_loss"], delta=1e-15)
        self.assertGreater(r["roc_auc_ovr_macro"], 0.5)


class TestSelection(unittest.TestCase):
    def _rows(self, means):
        return [{"max_depth": d, "min_samples_leaf": lf, "fold": f, "log_loss": m + (0.01 if f == "T1" else -0.01)}
                for (d, lf), m in means.items() for f in ("T1", "T2")]

    def test_selects_min_mean_and_reports_edge(self):
        means = {cfg: 1.0 for cfg in RFM.GRID}
        means[(8, 10)] = 0.97
        s = RFM.select_config(self._rows(means))
        self.assertEqual((s["max_depth"], s["min_samples_leaf"], s["tie"]), (8, 10, False))
        self.assertEqual(s["grid_edge_params"], ["max_depth", "min_samples_leaf"])

    def test_tie_prefers_smaller_depth_then_larger_leaf(self):
        means = {cfg: 1.0 for cfg in RFM.GRID}
        for cfg in ((8, 50), (5, 10), (5, 25)):
            means[cfg] = 0.98
        s = RFM.select_config(self._rows(means))
        self.assertEqual((s["max_depth"], s["min_samples_leaf"], s["tie"]), (5, 25, True))
        self.assertEqual(s["grid_edge_params"], [])

    def test_requires_complete_grid(self):
        with self.assertRaises(ValueError):
            RFM.select_config(self._rows({cfg: 1.0 for cfg in RFM.GRID})[:-1])


class TestFamilyRanking(unittest.TestCase):
    def test_best_of_r1_r3_and_simplicity_tie_break(self):
        rank = R5.family_ranking({"M1": {"R1": 0.98, "R3": 0.97}, "M2": {"R1": 0.975, "R3": 0.99},
                                  "M3": {"R1": 0.97, "R3": 1.00}, "M4": {"R1": 0.99, "R3": 0.99}})
        self.assertEqual([r["family"] for r in rank], ["M1", "M3", "M2", "M4"])   # M1 = M3 = 0.97 → M1 primero
        self.assertEqual([r["priority_B_candidate_by_ML0_rule"] for r in rank], [True, True, False, False])
        self.assertEqual(rank[0]["best_representation"], "R3")
        self.assertEqual(rank[0]["tied_with"], "M3")


class TestScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()
        cls.feats = {r: RFM.representation_features(r) for r in R5.REPRESENTATIONS}
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


if __name__ == "__main__":
    unittest.main()
