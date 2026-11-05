"""Tests de M1 (regresión logística multinomial, ML-2).

Ejecutar desde la raíz de SCOPE/ con el entorno ML:
    ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_logreg -v
Usa datos sintéticos salvo en los tests de alcance, que leen solo TRAIN de FEATURES v0.1 (D44).
"""
from __future__ import annotations

import unittest

import numpy as np

from src.eda import eda_io
from src.ml import logistic_model as LM
from src.ml import metrics as M
from src.ml import run_ml1 as R
from src.ml import run_ml2 as R2


def _synthetic(n=300, d=3, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)) * [1.0, 5.0, 0.2][:d] + [0.0, 10.0, -3.0][:d]
    logits = np.column_stack([X[:, 0], np.zeros(n), -X[:, 0]])
    p = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    y = [M.CLASS_ORDER[rng.choice(3, p=pi)] for pi in p]
    return X, y


class TestPipeline(unittest.TestCase):
    def test_pipeline_structure_and_frozen_params(self):
        pipe = LM.make_pipeline(1.0)
        self.assertEqual([n for n, _ in pipe.steps], ["scaler", "logreg"])
        lr = pipe.named_steps["logreg"]
        self.assertEqual((lr.solver, lr.penalty, lr.class_weight, lr.max_iter, lr.fit_intercept, lr.C),
                         ("lbfgs", "l2", None, 5000, True, 1.0))
        self.assertEqual(lr.multi_class, "deprecated")              # no se especifica el parámetro obsoleto

    def test_grid_is_frozen(self):
        self.assertEqual(LM.C_GRID, (0.01, 0.1, 1.0, 10.0, 100.0))
        with self.assertRaises(ValueError):
            LM.make_pipeline(1000.0)

    def test_scaler_fitted_only_on_train(self):
        X, y = _synthetic()
        Xtr, ytr, Xev = X[:200], y[:200], X[200:] + 100.0            # evaluación desplazada
        pipe = LM.make_pipeline(1.0)
        LM.fit(pipe, Xtr, ytr)
        np.testing.assert_allclose(pipe.named_steps["scaler"].mean_, Xtr.mean(axis=0))
        np.testing.assert_allclose(pipe.named_steps["scaler"].scale_, Xtr.std(axis=0))
        before = pipe.named_steps["scaler"].mean_.copy()
        LM.predict_proba_hda(pipe, Xev)                               # predecir no reajusta nada
        np.testing.assert_array_equal(pipe.named_steps["scaler"].mean_, before)

    def test_probability_mapping_by_label(self):
        X, y = _synthetic(seed=1)
        pipe = LM.make_pipeline(1.0)
        LM.fit(pipe, X, y)
        self.assertEqual(list(pipe.classes_), ["A", "D", "H"])       # orden de la librería
        P_lib = pipe.predict_proba(X)
        P = LM.predict_proba_hda(pipe, X)
        idx = {c: list(pipe.classes_).index(c) for c in M.CLASS_ORDER}
        for k, c in enumerate(M.CLASS_ORDER):
            np.testing.assert_array_equal(P[:, k], P_lib[:, idx[c]])
        # x0 alto favorece H en los datos sintéticos → P(H) debe crecer con x0
        self.assertGreater(np.corrcoef(X[:, 0], P[:, 0])[0, 1], 0.9)

    def test_reproducible(self):
        X, y = _synthetic(seed=2)
        a, b = LM.make_pipeline(0.1), LM.make_pipeline(0.1)
        LM.fit(a, X, y); LM.fit(b, X, y)
        np.testing.assert_array_equal(LM.predict_proba_hda(a, X), LM.predict_proba_hda(b, X))

    def test_rejects_missing_values(self):
        X, y = _synthetic()
        X[3, 1] = np.nan
        with self.assertRaises(ValueError):
            LM.fit(LM.make_pipeline(1.0), X, y)

    def test_convergence_recorded(self):
        X, y = _synthetic(seed=3)
        info = LM.fit(LM.make_pipeline(100.0), X, y)
        self.assertTrue(info["converged"])
        self.assertGreater(info["n_iter"], 0)
        self.assertEqual(info["warnings"], [])

    def test_coefficients_in_hda_order(self):
        X, y = _synthetic(seed=4)
        pipe = LM.make_pipeline(1.0)
        LM.fit(pipe, X, y)
        rows = LM.coefficients(pipe, ["f0", "f1", "f2"])
        self.assertEqual([r["class"] for r in rows if r["term"] == "intercept"], list(M.CLASS_ORDER))
        h0 = next(r["coef"] for r in rows if r["class"] == "H" and r["term"] == "f0")
        a0 = next(r["coef"] for r in rows if r["class"] == "A" and r["term"] == "f0")
        self.assertGreater(h0, a0)                                    # x0 favorece H frente a A


class TestSelection(unittest.TestCase):
    def _rows(self, means):
        return [{"C": c, "fold": f, "log_loss": m + (0.01 if f == "T1" else -0.01)}
                for c, m in means.items() for f in ("T1", "T2")]

    def test_selects_min_mean(self):
        s = LM.select_C(self._rows({0.01: 1.06, 0.1: 1.04, 1.0: 1.03, 10.0: 1.035, 100.0: 1.036}))
        self.assertEqual(s["C"], 1.0)
        self.assertFalse(s["tie"])

    def test_tie_prefers_smaller_C(self):
        s = LM.select_C(self._rows({0.01: 1.06, 0.1: 1.03, 1.0: 1.03, 10.0: 1.05, 100.0: 1.05}))
        self.assertEqual(s["C"], 0.1)
        self.assertTrue(s["tie"])

    def test_requires_complete_grid(self):
        rows = self._rows({0.01: 1.0, 0.1: 1.0, 1.0: 1.0, 10.0: 1.0, 100.0: 1.0})[:-1]
        with self.assertRaises(ValueError):
            LM.select_C(rows)


class TestScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()
        cls.feats = {r: LM.representation_features(r) for r in R2.REPRESENTATIONS}
        cls.rows = R2.load_train_with_features(sorted({c for f in cls.feats.values() for c in f}))

    def test_representations_from_formal_source(self):
        self.assertEqual(self.feats["R1"], ("diff_ppg_season", "diff_gf_pg_season", "diff_ga_pg_season"))
        self.assertEqual(set(self.feats["R3"]), {f"{s}_{m}" for s in ("h", "a")
                                                 for m in ("ppg_season", "gf_pg_season", "ga_pg_season")})
        for f in self.feats.values():
            self.assertFalse(any("last5" in c or "sot" in c for c in f))

    def test_only_train_and_no_missing(self):
        self.assertEqual(len(self.rows), 1049)
        self.assertEqual({r["season"] for r in self.rows}, set(eda_io.SEASONS_TRAIN_DESIGN))
        for r in self.rows:
            self.assertTrue(all(np.isfinite(v) for v in r["x"].values()))

    def test_folds_reuse_ml1_guards_and_grid_cardinality(self):
        folds = R.build_folds(self.rows)
        self.assertEqual([(f["fold"], len(f["train"]), len(f["eval"])) for f in folds],
                         [("T1", 350, 350), ("T2", 700, 349)])
        for f in folds:
            self.assertFalse({r["season"] for r in f["train"] + f["eval"]}
                             & {eda_io.SEASON_VALIDATION, eda_io.SEASON_FINAL_TEST})
        self.assertEqual(len(R2.REPRESENTATIONS) * len(LM.C_GRID) * len(folds), R2.EXPECTED_FITS)


if __name__ == "__main__":
    unittest.main()
