"""Tests de ML-6 (Prioridad B: P02/P04 con LR y RF).

Ejecutar desde la raíz de SCOPE/ con el entorno ML:
    ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_priority_b -v
Datos sintéticos salvo en los tests de alcance/referencias, que leen solo TRAIN de FEATURES v0.1 (D44)
y los outputs verificados de ML-2/ML-5. No reentrena R1/R3.
"""
from __future__ import annotations

import csv
import unittest

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.eda import eda_io
from src.ml import logistic_model as LM
from src.ml import metrics as M
from src.ml import random_forest_model as RFM
from src.ml import run_ml1 as R
from src.ml import run_ml2 as R2
from src.ml import run_ml6 as R6

# Contrato §12 (texto literal): d = 5 y d = 10 (h_/a_ de las mismas cinco métricas)
CONTRACT_D5 = ("diff_ppg_season", "diff_gf_pg_season", "diff_ga_pg_season", "diff_ppg_last5", "diff_sot_pg_last5")


def _synthetic(n=240, seed=0, d=4):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)) * 3.0 + 10.0
    y = np.where(X[:, 0] > 11.5, "H", np.where(X[:, 0] < 8.5, "A", "D"))
    flip = rng.random(n) < 0.2
    return X, np.where(flip, rng.choice(["H", "D", "A"], size=n), y).tolist()


class TestRepresentations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feats = {r: LM.representation_features(r) for r in R6.TABLE_ORDER}   # aborta si no cumple D46

    def test_six_new_representations_and_dimensions(self):
        self.assertEqual(R6.NEW_REPS, ("R5", "R2", "R6", "R4", "P04-D5", "P04-D10"))
        self.assertEqual(R6.BASE_REPS, ("R1", "R3"))
        self.assertEqual({r: len(self.feats[r]) for r in R6.NEW_REPS},
                         {"R5": 6, "R2": 7, "R6": 12, "R4": 14, "P04-D5": 5, "P04-D10": 10})
        self.assertFalse({"R7", "R8"} & set(R6.TABLE_ORDER))

    def test_features_match_formal_csv_and_exclude_forbidden(self):
        with open(LM.REPRESENTATIONS_CSV, newline="", encoding="utf-8") as fh:
            rows = {r["representation_id"]: r for r in csv.DictReader(fh)}
        for rep in R6.TABLE_ORDER:
            self.assertEqual(self.feats[rep], tuple(rows[rep]["features"].split("|")))
            self.assertEqual(rows[rep]["D46_compliant"], "True")
            self.assertEqual(rows[rep]["family"], R6.REP_FAMILY[rep])
            for f in self.feats[rep]:
                self.assertTrue(f.endswith(("_season", "_last5")), f)
                self.assertFalse(f.startswith(("mkt_", "odds_", "post_")), f)
            prefixes = {f.split("_")[0] for f in self.feats[rep]}
            self.assertTrue(prefixes in ({"diff"}, {"h", "a"}), f"{rep}: mezcla diff con h/a (D46)")

    def test_p04_lists_are_literal_contract(self):
        self.assertEqual(self.feats["P04-D5"], CONTRACT_D5)
        d10 = {f"{side}_{f[len('diff_'):]}" for f in CONTRACT_D5 for side in ("h", "a")}
        self.assertEqual(set(self.feats["P04-D10"]), d10)

    def test_nesting_relations(self):
        nest = R6.nesting(self.feats)
        self.assertTrue(all(n["strict_subset"] for n in nest))
        by = {(n["reference"], n["new"]): n for n in nest}
        self.assertEqual(by[("R1", "R5")]["added"], ["diff_ga_pg_last5", "diff_gf_pg_last5", "diff_ppg_last5"])
        self.assertEqual(by[("R5", "R2")]["added"], ["diff_sot_pg_last5"])
        self.assertEqual(by[("R6", "R4")]["added"], ["a_sot_pg_last5", "h_sot_pg_last5"])
        self.assertEqual(by[("R1", "P04-D5")]["added"], ["diff_ppg_last5", "diff_sot_pg_last5"])
        # P04-D5 y R5 no están anidadas: no sirven para aislar la ventana ni SOT
        self.assertFalse(set(self.feats["P04-D5"]) <= set(self.feats["R5"]))
        self.assertFalse(set(self.feats["R5"]) <= set(self.feats["P04-D5"]))


class TestBudgetAndEstimators(unittest.TestCase):
    def test_budget_168(self):
        self.assertEqual(R6.FAMILIES, ("M4", "M1"))
        self.assertEqual(len(R6.GRID_POINTS["M1"]), 5)
        self.assertEqual(len(R6.GRID_POINTS["M4"]), 9)
        self.assertEqual(R6.EXPECTED_FITS, {"M1": 60, "M4": 108})
        self.assertEqual(sum(R6.EXPECTED_FITS.values()), R6.EXPECTED_TOTAL_FITS)
        self.assertEqual(R6.EXPECTED_TREES, 16200)

    def test_preprocessing_by_family(self):
        lr, rf = R6.make_estimator("M1", (1.0,)), R6.make_estimator("M4", (5, 25))
        self.assertIsInstance(lr, Pipeline)
        self.assertIsInstance(lr.steps[0][1], StandardScaler)
        self.assertEqual(lr.named_steps["logreg"].get_params()["C"], 1.0)
        self.assertIsInstance(rf, RandomForestClassifier)
        self.assertNotIsInstance(rf, Pipeline)
        for bad in (("M1", (3.0,)), ("M4", (4, 25)), ("M2", (21,))):
            with self.assertRaises(ValueError):
                R6.make_estimator(*bad)

    def test_scaler_fitted_on_train_only(self):
        X, y = _synthetic()
        Xtr, Xev = X[:160], X[160:] + 100.0                # evaluación desplazada: no debe afectar al scaler
        est, Pev, _, info, _ = R6.fit_predict("M1", (1.0,), Xtr, y[:160], Xev)
        self.assertTrue(R6.scaler_fit_on_train_only(est, Xtr))
        self.assertFalse(R6.scaler_fit_on_train_only(est, X))
        self.assertTrue(info["converged"])

    def test_hda_order_and_reproducibility(self):
        X, y = _synthetic(seed=3)
        for fam, hp in (("M1", (0.1,)), ("M4", (3, 10))):
            est, P1, _, _, _ = R6.fit_predict(fam, hp, X[:160], y[:160], X[160:])
            _, P2, _, _, _ = R6.fit_predict(fam, hp, X[:160], y[:160], X[160:])
            np.testing.assert_array_equal(P1, P2)
            lib = est.predict_proba(X[160:])
            classes = list(est.classes_)
            self.assertEqual(classes, ["A", "D", "H"])
            for k, c in enumerate(M.CLASS_ORDER):
                np.testing.assert_array_equal(P1[:, k], lib[:, classes.index(c)])


class TestSelectionAndComparisons(unittest.TestCase):
    def test_selection_dispatch_uses_family_rules(self):
        lr = [{"C": c, "fold": f, "log_loss": (0.97 if c in (0.1, 1.0) else 1.0)} for c in LM.C_GRID for f in ("T1", "T2")]
        s = R6.select("M1", lr)
        self.assertEqual((s["hp"], s["tie"], s["grid_edge_params"]), ((0.1,), True, []))
        rf = [{"max_depth": d, "min_samples_leaf": lf, "fold": f, "log_loss": (0.96 if (d, lf) == (8, 50) else 1.0)}
              for d, lf in RFM.GRID for f in ("T1", "T2")]
        s = R6.select("M4", rf)
        self.assertEqual((s["hp"], s["grid_edge_params"]), ((8, 50), ["max_depth", "min_samples_leaf"]))

    def test_delta_is_new_minus_reference(self):
        def res(src, l1, l2, hp=(1.0,)):
            fold = lambda v: {**{k: 0.5 for k in R6.COMPARE_KEYS}, "log_loss": v}       # noqa: E731
            return {"source": src, "hp": hp, "folds": {"T1": fold(l1), "T2": fold(l2)}}
        results = {("M1", rep): res("X", 1.0, 1.0) for rep in R6.TABLE_ORDER}
        results.update({("M4", rep): res("X", 1.0, 1.0, (3, 10)) for rep in R6.TABLE_ORDER})
        results[("M1", "R5")] = res("ML-6", 0.98, 1.01)
        feats = {r: LM.representation_features(r) for r in R6.TABLE_ORDER}
        rows = R6.comparison_rows(results, feats)
        self.assertEqual(len(rows), len(R6.FAMILIES) * len(R6.COMPARISONS) * 3)
        r = {x["validation_scope"]: x for x in rows if x["model"] == "M1" and x["comparison"] == "R1->R5"}
        self.assertAlmostEqual(r["CV_T1"]["delta_log_loss"], -0.02, places=12)
        self.assertAlmostEqual(r["CV_T2"]["delta_log_loss"], 0.01, places=12)
        self.assertAlmostEqual(r["CV_MEAN"]["delta_log_loss"], -0.005, places=12)
        self.assertEqual(r["CV_MEAN"]["log_loss_direction_across_folds"], "mixed_across_folds")
        self.assertEqual(r["CV_T1"]["features_removed"], "none")
        q = {x["comparison"]: x["question"] for x in rows}
        self.assertEqual(q["R5->R2"], "P02-B_sot")
        self.assertEqual(q["R1->R2"], "P02-C_full_block")
        self.assertEqual(q["P04-D10->R4"], "P04_subset")

    def test_prediction_season_guard(self):
        R6.check_prediction_seasons({"2022-2023", "2023-2024"})
        for bad in ("2024-2025", "2025-2026"):
            with self.assertRaises(R6.ML6Abort):
                R6.check_prediction_seasons({"2022-2023", bad})


class TestScopeAndReferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()
        cls.refs = R6.load_reference_results()
        feats = {r: LM.representation_features(r) for r in R6.TABLE_ORDER}
        cls.rows = R2.load_train_with_features(sorted({c for f in feats.values() for c in f}))
        cls.folds = R.build_folds(cls.rows)

    def test_families_from_ml5_ranking(self):
        fams = R6.load_selected_families()
        self.assertEqual([f["family"] for f in fams], ["M4", "M1"])
        self.assertEqual([f["best_representation"] for f in fams], ["R1", "R3"])

    def test_references_reused_not_retrained(self):
        with open(R6.ML2_DIR / "ml2_logreg_selected_configs.csv", newline="", encoding="utf-8") as fh:
            lr = {r["representation"]: r for r in csv.DictReader(fh)}
        with open(R6.ML5_DIR / "ml5_rf_selected_configs.csv", newline="", encoding="utf-8") as fh:
            rf = {r["representation"]: r for r in csv.DictReader(fh)}
        for rep in ("R1", "R3"):
            for fold in ("T1", "T2"):
                self.assertEqual(self.refs[("M1", rep)]["folds"][fold]["log_loss"], float(lr[rep][f"log_loss_{fold}"]))
                self.assertEqual(self.refs[("M4", rep)]["folds"][fold]["log_loss"], float(rf[rep][f"log_loss_{fold}"]))
            self.assertEqual(self.refs[("M1", rep)]["source"], "ML-2")
            self.assertEqual(self.refs[("M4", rep)]["source"], "ML-5")
        self.assertEqual(self.refs[("M4", "R1")]["hp"], (5, 50))

    def test_same_observations_and_train_only(self):
        self.assertEqual(len(self.rows), 1049)
        self.assertEqual({r["season"] for r in self.rows}, set(eda_io.SEASONS_TRAIN_DESIGN))
        self.assertEqual([(f["fold"], len(f["train"]), len(f["eval"])) for f in self.folds],
                         [("T1", 350, 350), ("T2", 700, 349)])
        for f in self.folds:
            self.assertFalse({r["season"] for r in f["train"] + f["eval"]}
                             & {eda_io.SEASON_VALIDATION, eda_io.SEASON_FINAL_TEST})
            ids = [r["match_id"] for r in f["eval"]]
            for key, res in self.refs.items():
                self.assertEqual(res["folds"][f["fold"]]["match_ids"], ids, key)


if __name__ == "__main__":
    unittest.main()
