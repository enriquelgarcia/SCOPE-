"""Tests de ML-8 (selección por protocolo, freeze, política de refit, benchmark de mercado).

Ejecutar desde la raíz de SCOPE/:  ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_final -v
Los tests que dependen del artefacto o del Decision Log se omiten solo si esos artefactos aún no existen
(antes del primer `freeze`); el gate de `market`/`manifest` exige que existan y no admite omisiones.
FINAL TEST nunca se carga.
"""
from __future__ import annotations

import csv
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.ml import knn_model as KNN
from src.ml import logistic_model as LM
from src.ml import metrics as M
from src.ml import run_ml7 as R7
from src.ml import run_ml8 as R8


def _rows(**ll):
    base = {"M2-R1": ("M2", "R1", 3), "M4-R1": ("M4", "R1", 3), "M1-R3": ("M1", "R3", 6)}
    out = [{"candidate_id": c, "model": m, "representation": r, "dimension": d, "role": "CANDIDATE",
            "log_loss": ll.get(c.replace("-", "_"), 1.1)} for c, (m, r, d) in base.items()]
    out += [{"candidate_id": f"X{i}", "model": "M3", "representation": "R1", "dimension": 3, "role": "CANDIDATE",
             "log_loss": 1.2 + i} for i in range(R7.EXPECTED_CANDIDATES - 3)]
    return out


class TestSelectionRule(unittest.TestCase):
    def test_no_equivalence_tolerance_parameter(self):
        self.assertEqual(list(inspect.signature(R8.select_by_protocol).parameters), ["metric_rows"])

    def test_lowest_log_loss_wins_even_by_small_margin(self):
        s = R8.select_by_protocol(_rows(M2_R1=1.00035, M4_R1=1.00131, M1_R3=1.0069))
        self.assertEqual((s["selected"], s["tied_with_best"]), ("M2-R1", []))
        self.assertTrue(s["decided_at_level"].startswith("1"))
        s = R8.select_by_protocol(_rows(M2_R1=1.00131, M4_R1=1.00035))     # simétrico: no favorece a una familia
        self.assertEqual(s["selected"], "M4-R1")

    def test_exact_tie_uses_predefined_parsimony(self):
        s = R8.select_by_protocol(_rows(M2_R1=1.0, M4_R1=1.0, M1_R3=1.0))
        self.assertEqual(s["selected"], "M2-R1")                           # menos features (3 < 6), luego M2 < M4
        self.assertEqual(s["tied_with_best"], ["M4-R1", "M1-R3"])

    def test_real_ml7_results_select_knn_r1(self):
        rows = R8.ml7_rows("ml7_validation_metrics.csv")
        for r in rows:
            r["log_loss"], r["dimension"] = float(r["log_loss"]), int(r["dimension"])
        s = R8.select_by_protocol(rows)
        self.assertEqual(s["selected"], "M2-R1")
        self.assertEqual(s["tied_with_best"], [])
        by = {r["candidate_id"]: r for r in rows}
        self.assertGreater(by["M4-R1"]["log_loss"] - by["M2-R1"]["log_loss"], 1e-12)
        self.assertLess(float(by["M4-R1"]["brier"]), float(by["M2-R1"]["brier"]))   # el secundario no se usa


class TestMarket(unittest.TestCase):
    def test_implied_probabilities(self):
        P = R8.implied_probabilities([[2.0, 3.5, 4.0], [1.5, 4.0, 7.0]])
        q = 1 / np.array([2.0, 3.5, 4.0])
        np.testing.assert_allclose(P[0], q / q.sum())
        np.testing.assert_allclose(P.sum(axis=1), 1.0, atol=1e-12)
        for bad in ([[1.0, 3.0, 4.0]], [[np.nan, 3.0, 4.0]], [[2.0, 3.0]]):
            with self.assertRaises(R8.ML8Abort):
                R8.implied_probabilities(bad)

    def test_market_loader_skips_test_season(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "canonical.csv"
            cols = [c for _, cs, _ in R8.MARKET_SOURCES for c in cs]
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["match_id", "season", *cols])
                w.writeheader()
                for mid, s in (("v1", "2024-2025"), ("t1", "2025-2026"), ("x", "2023-2024")):
                    w.writerow({"match_id": mid, "season": s, **{c: "2.5" for c in cols}})
            out = R8.load_market_odds(["v1", "t1", "x"], p)
            self.assertEqual(set(out), {"v1"})


class TestFrozenSpec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = R8.OUT_DIR / R8.SPEC_NAME
        if not path.is_file():
            raise unittest.SkipTest("especificación aún no congelada (antes de `run_ml8 freeze`)")
        cls.spec = json.loads(path.read_text(encoding="utf-8"))

    def test_features_hyperparameters_and_policy(self):
        s = self.spec
        self.assertEqual(s["candidate_id"], "M2-R1")
        self.assertEqual(tuple(s["features_ordered"]), LM.representation_features("R1"))
        self.assertEqual(s["hyperparameters"], {"n_neighbors": 101, "weights": "uniform", "metric": "euclidean",
                                                "algorithm": "auto"})
        with open(R8.ML_DIR / "ml3" / "ml3_knn_selected_configs.csv", newline="", encoding="utf-8") as fh:
            r1 = next(r for r in csv.DictReader(fh) if r["representation"] == "R1")
        self.assertEqual((int(r1["selected_n_neighbors"]), r1["selected_weights"]), (101, "uniform"))
        self.assertEqual([p["class"] for p in s["pipeline"]], ["sklearn.preprocessing.StandardScaler",
                                                               "sklearn.neighbors.KNeighborsClassifier"])
        self.assertEqual(s["class_order"], ["H", "D", "A"])
        self.assertIsNone(s["calibration"])
        self.assertEqual(s["refit_policy"]["option"], "a")
        self.assertEqual(s["allowed_training_data"]["seasons"], ["2021-2022", "2022-2023", "2023-2024"])
        self.assertEqual(s["allowed_training_data"]["n"], 1049)

    def test_artifact_verifies_and_reproduces_ml7(self):
        v = R8.verify_frozen_artifact()
        est = v["estimator"]
        self.assertEqual(int(est.named_steps["knn"].n_samples_fit_), 1049)
        train, val = R7.load_dev_rows(self.spec["features_ordered"])
        rep = R8.predictions_match_ml7(est, val, self.spec["features_ordered"])
        self.assertTrue(rep["identical"])
        self.assertFalse(rep["labels_used"])
        Xva = np.array([[r["x"][c] for c in self.spec["features_ordered"]] for r in val[:5]])
        lib = est.predict_proba(Xva)
        P = KNN.predict_proba_hda(est, Xva)
        for k, c in enumerate(M.CLASS_ORDER):
            np.testing.assert_array_equal(P[:, k], lib[:, list(est.classes_).index(c)])

    def test_tampered_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            spec = dict(self.spec)
            spec["artifact"] = {**spec["artifact"], "sha256": "0" * 64}
            p = Path(d) / "spec.json"
            p.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaises(R8.ML8Abort):
                R8.verify_frozen_artifact(p)


class TestDecisionLog(unittest.TestCase):
    def test_decision_ids_unique_and_selection_registered(self):
        text = R8.DECISION_LOG.read_text(encoding="utf-8")
        ids = [line.split("|")[1].strip() for line in text.splitlines() if line.startswith("| D")]
        self.assertEqual(len(ids), len(set(ids)))
        if "| D50 |" not in text:
            raise unittest.SkipTest("Decision Log aún sin las decisiones de ML-8")
        self.assertTrue(R8.decision_log_registers_selection())
        for d in ("D50", "D51", "D52", "D53", "D54"):
            self.assertEqual(text.count(f"| {d} |"), 1)
        self.assertNotIn("| D55 |", text)


if __name__ == "__main__":
    unittest.main()
