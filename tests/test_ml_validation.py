"""Tests de ML-7 (VALIDATION 2024/25: refit de la shortlist en TRAIN_FULL).

Ejecutar desde la raíz de SCOPE/ con el entorno ML:
    ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_validation -v
Los tests de alcance leen FEATURES v0.1 (D44) solo como predictores: ninguna etiqueta de VALIDATION se lee
con el archivo real (el loader de etiquetas se prueba con un CSV sintético). FINAL TEST nunca se carga.
"""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from src.config import settings
from src.eda import eda_io
from src.ml import metrics as M
from src.ml import run_ml7 as R7


def _write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _row(mid, season, kick, result, elig=True, n=5):
    return {"match_id": mid, "season": season, "kickoff_datetime": kick, "h_n_prev_season": str(n if elig else 1),
            "a_n_prev_season": str(n), "diff_ppg_season": "0.5", "result": result,
            "is_modeling_eligible": "true" if elig else "false"}


class TestRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = R7.build_registry()

    def test_twenty_candidates_exact(self):
        self.assertEqual(len(self.reg), 20)
        got = {(c["model"], c["representation"]) for c in self.reg}
        exp = ({("M1", r) for r in R7.REP_ORDER} | {("M4", r) for r in R7.REP_ORDER}
               | {(f, r) for f in ("M2", "M3") for r in ("R1", "R3")})
        self.assertEqual(got, exp)
        self.assertFalse({"R7", "R8"} & {c["representation"] for c in self.reg})
        self.assertEqual(R7.BASELINES, ("B0", "B1"))

    def test_hyperparameters_frozen_from_train_cv(self):
        hp = {c["candidate_id"]: c["hyperparams"] for c in self.reg}
        self.assertEqual(hp["M1-R1"], "C=0.1")                         # ML-2
        self.assertEqual(hp["M1-P04-D10"], "C=0.1")                    # ML-6
        self.assertEqual(hp["M1-R4"], "C=0.01")
        self.assertEqual(hp["M2-R1"], "n_neighbors=101|weights=uniform")    # ML-3
        self.assertEqual(hp["M2-R3"], "n_neighbors=101|weights=distance")
        self.assertEqual(hp["M3-R1"], "max_depth=3|min_samples_leaf=50")    # ML-4
        self.assertEqual(hp["M4-R1"], "max_depth=5|min_samples_leaf=50")    # ML-5
        self.assertEqual(hp["M4-P04-D5"], "max_depth=5|min_samples_leaf=50")  # ML-6
        self.assertEqual(hp["M4-P04-D10"], "max_depth=3|min_samples_leaf=10")
        cv = {c["candidate_id"]: c["train_cv_log_loss_CV_MEAN"] for c in self.reg}
        self.assertAlmostEqual(cv["M1-P04-D10"], 0.96753, places=5)
        self.assertAlmostEqual(cv["M4-P04-D5"], 0.96903, places=5)

    def test_estimators_and_preprocessing_by_family(self):
        by = {c["model"]: c for c in self.reg}
        for fam in ("M1", "M2"):
            est = R7.make_estimator(fam, by[fam]["hp"])
            self.assertIsInstance(est, Pipeline)
            self.assertEqual(est.steps[0][0], "scaler")
        self.assertIsInstance(R7.make_estimator("M3", by["M3"]["hp"]), DecisionTreeClassifier)
        rf = R7.make_estimator("M4", by["M4"]["hp"])
        self.assertIsInstance(rf, RandomForestClassifier)
        self.assertEqual((rf.n_estimators, rf.random_state), (150, 42))
        for bad in (("M1", (5.0,)), ("M2", (7, "uniform")), ("M3", (10, 5)), ("M4", (4, 10)), ("M5", (1,))):
            with self.assertRaises(ValueError):
                R7.make_estimator(*bad)


class TestScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()
        cls.train, cls.val = R7.load_dev_rows(["diff_ppg_season", "h_sot_pg_last5"])

    def test_sizes_and_seasons(self):
        self.assertEqual((len(self.train), len(self.val)), (1049, 350))
        self.assertEqual({r["season"] for r in self.train}, set(eda_io.SEASONS_TRAIN_DESIGN))
        self.assertEqual({r["season"] for r in self.val}, {eda_io.SEASON_VALIDATION})
        self.assertNotIn(eda_io.SEASON_FINAL_TEST, {r["season"] for r in self.train + self.val})

    def test_validation_rows_carry_no_label(self):
        self.assertTrue(all("result" not in r for r in self.val))
        self.assertTrue(all(r["result"] in M.CLASS_ORDER for r in self.train))
        self.assertLess(max(r["kickoff_datetime"] for r in self.train), min(r["kickoff_datetime"] for r in self.val))


class TestLoadersSynthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "features.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def test_test_season_skipped_and_label_loader(self):
        rows = [_row("a", "2021-2022", "2021-09-01", "H"), _row("b", "2022-2023", "2022-09-01", "D"),
                _row("c", "2023-2024", "2023-09-01", "A"), _row("x", "2023-2024", "2023-08-12", "H", elig=False),
                _row("v1", "2024-2025", "2024-09-01", "A"), _row("v2", "2024-2025", "2024-09-08", "D"),
                _row("t1", "2025-2026", "2025-09-01", "H")]
        _write_csv(rows, self.path)
        tr, va = R7.load_dev_rows(["diff_ppg_season"], self.path)
        self.assertEqual([r["match_id"] for r in tr], ["a", "b", "c"])
        self.assertEqual([r["match_id"] for r in va], ["v1", "v2"])
        self.assertEqual(R7.load_validation_labels(["v1", "v2"], self.path), {"v1": "A", "v2": "D"})
        with self.assertRaises(R7.ML7Abort):
            R7.load_validation_labels(["v1"], self.path)

    def test_eligibility_rule_is_asserted(self):
        bad = _row("a", "2021-2022", "2021-09-01", "H")
        bad["h_n_prev_season"] = "1"                                   # flag true pero regla D48 falsa
        _write_csv([bad, _row("v1", "2024-2025", "2024-09-01", "A")], self.path)
        with self.assertRaises(R7.ML7Abort):
            R7.load_dev_rows(["diff_ppg_season"], self.path)


class TestFitAndMetrics(unittest.TestCase):
    def _data(self, n=300, seed=0):
        rng = np.random.default_rng(seed)
        x = rng.normal(size=n)
        y = np.where(x > 0.5, "H", np.where(x < -0.5, "A", "D"))
        rows = [{"match_id": f"m{i}", "x": {"f": float(v), "g": float(v * 3 + 50)}, "result": str(c)}
                for i, (v, c) in enumerate(zip(x, y))]
        return rows[:200], rows[200:]

    def test_scaler_fit_only_on_train_full_and_hda_order(self):
        tr, va = self._data()
        for r in va:
            r["x"]["g"] += 1000.0                                       # desplazamiento: no debe entrar al scaler
        for fam, hp in (("M1", (1.0,)), ("M2", (11, "uniform")), ("M3", (3, 25)), ("M4", (3, 10))):
            cand = {"model": fam, "hp": hp, "features": "f|g", "run_id": f"t-{fam}"}
            out = R7.fit_candidate(cand, tr, va)
            Pm = out["P_val"]
            self.assertEqual(Pm.shape, (100, 3))
            np.testing.assert_allclose(Pm.sum(axis=1), 1.0, atol=1e-12)
            self.assertEqual(out["diag"]["scaler_fit_on_train_only"], True if fam in ("M1", "M2") else "NA")
            again = R7.fit_candidate(cand, tr, va)["P_val"]
            np.testing.assert_array_equal(Pm, again)                    # reproducible

    def test_baselines_use_train_full_only(self):
        tr, _ = self._data()
        out = R7.fit_baseline("B1", tr, 5)
        prior = np.array([sum(r["result"] == c for r in tr) / len(tr) for c in M.CLASS_ORDER])
        np.testing.assert_allclose(out["P_val"][0], prior)
        self.assertEqual(R7.fit_baseline("B0", tr, 5)["P_val"][0].max(), 1.0)

    def test_per_match_loss_and_bootstrap(self):
        y = ["H", "D", "A", "H"]
        Pm = np.array([[0.5, 0.3, 0.2], [0.2, 0.5, 0.3], [0.1, 0.2, 0.7], [1.0, 0.0, 0.0]])
        loss = R7.per_match_log_loss(y, Pm)
        self.assertAlmostEqual(loss.mean(), M.log_loss(y, Pm)["log_loss"], places=12)
        idx = R7.bootstrap_indices(4)
        np.testing.assert_array_equal(idx, R7.bootstrap_indices(4))     # semilla 42 fija
        self.assertEqual(idx.shape, (2000, 4))
        b = R7.paired_bootstrap(loss, loss, idx)
        self.assertEqual((b["delta_log_loss"], b["boot_ci_2_5"], b["boot_ci_97_5"]), (0.0, 0.0, 0.0))
        b = R7.paired_bootstrap(loss - 0.1, loss, idx)
        self.assertAlmostEqual(b["delta_log_loss"], -0.1)
        self.assertFalse(b["ci_contains_zero"])
        self.assertEqual(b["boot_share_new_lower"], 1.0)


class TestSelectionRule(unittest.TestCase):
    def test_primary_log_loss_then_parsimony_tie_break(self):
        rows = [{"candidate_id": "M4-R2", "model": "M4", "representation": "R2", "dimension": 7, "log_loss": 0.95},
                {"candidate_id": "M1-R1", "model": "M1", "representation": "R1", "dimension": 3, "log_loss": 0.95},
                {"candidate_id": "M4-R1", "model": "M4", "representation": "R1", "dimension": 3, "log_loss": 0.95},
                {"candidate_id": "M2-R3", "model": "M2", "representation": "R3", "dimension": 6, "log_loss": 0.94},
                {"candidate_id": "M3-R1", "model": "M3", "representation": "R1", "dimension": 3, "log_loss": 0.99}]
        rk = R7.rank_candidates(rows)
        self.assertEqual([r["candidate_id"] for r in rk], ["M2-R3", "M1-R1", "M4-R1", "M4-R2", "M3-R1"])
        self.assertEqual({r["candidate_id"]: r["rank_within_family"] for r in rk}["M4-R2"], 2)
        self.assertFalse(rk[1]["tied_with_best"])


if __name__ == "__main__":
    unittest.main()
