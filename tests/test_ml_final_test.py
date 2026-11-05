"""Tests de ML-9 (evaluación final única del modelo congelado).

Ejecutar desde la raíz de SCOPE/:  ~/.venvs/scope-ml-py310/bin/python -m unittest tests.test_ml_final_test -v
Ningún test lee etiquetas reales de FINAL TEST: los loaders de etiquetas y de mercado se prueban con CSV sintéticos.
El único acceso a 2025/26 real es predictor-only (conteo de filas elegibles, sin `result`).
"""
from __future__ import annotations

import csv
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from src.ml import metrics as M
from src.ml import run_ml8 as R8
from src.ml import run_ml9 as R9

FEATS = list(R9.EXPECTED_FEATURES)


def _feature_csv(path, rows):
    cols = ["match_id", "season", "kickoff_datetime", "h_n_prev_season", "a_n_prev_season", *FEATS,
            "result", "goal_difference", "is_modeling_eligible"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for i, (season, elig, res) in enumerate(rows):
            w.writerow({"match_id": f"m{i}", "season": season, "kickoff_datetime": f"2025-09-{i + 1:02d}T15:00:00",
                        "h_n_prev_season": "5" if elig else "1", "a_n_prev_season": "5",
                        **{c: str(0.1 * (i + 1)) for c in FEATS}, "result": res, "goal_difference": "1",
                        "is_modeling_eligible": "true" if elig else "false"})


class TestFrozenArtifact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.est, cls.spec = R9.load_frozen_model()

    def test_artifact_hash_family_features_hyperparams(self):
        self.assertEqual(self.spec["artifact"]["sha256"],
                         "63b84ceb8e0a5779ac239af78a38d4d0d47a481eb42cefd84970a6524f3f35a3")
        knn = self.est.named_steps["knn"]
        self.assertEqual(type(knn).__name__, "KNeighborsClassifier")
        self.assertEqual((knn.n_neighbors, knn.weights, knn.metric), (101, "uniform", "euclidean"))
        self.assertEqual(tuple(self.spec["features_ordered"]), R9.EXPECTED_FEATURES)

    def test_fitted_exactly_on_train_full_without_refit(self):
        before = R9.fitted_state_digest(self.est)
        chk = R9.check_fitted_on_train_full(self.est, R9.EXPECTED_FEATURES)
        self.assertEqual(chk["n_train"], 1049)
        self.assertTrue(chk["stored_X_matches"] and chk["stored_y_matches"] and chk["scaler_matches_train_full"])
        self.assertEqual(R9.fitted_state_digest(self.est), before)

    def test_version_mismatch_is_rejected(self):
        env = R8.R.environment()
        with mock.patch.object(R8.R, "environment", return_value={**env, "scikit-learn": "1.8.0"}):
            with self.assertRaises(R9.ML9Abort):
                R9.load_frozen_model()

    def test_feature_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            spec = {**self.spec, "features_ordered": ["diff_ppg_season", "diff_gf_pg_season", "diff_ppg_last5"]}
            p = Path(d) / "spec.json"
            p.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaises(R9.ML9Abort):
                R9.load_frozen_model(p)

    def test_prediction_order_hda_and_no_refit(self):
        rows = [{"match_id": f"s{i}", "x": dict(zip(FEATS, v))}
                for i, v in enumerate(np.random.default_rng(0).normal(size=(20, 3)).tolist())]
        before = R9.fitted_state_digest(self.est)
        P = R9.predict_frozen(self.est, rows, FEATS)
        self.assertEqual(R9.fitted_state_digest(self.est), before)
        X = np.array([[r["x"][c] for c in FEATS] for r in rows])
        lib, classes = self.est.predict_proba(X), [str(c) for c in self.est.classes_]
        for k, c in enumerate(M.CLASS_ORDER):
            np.testing.assert_array_equal(P[:, k], lib[:, classes.index(c)])
        np.testing.assert_array_equal(P, R9.predict_frozen(self.est, rows, FEATS))      # reproducible

    def test_runner_never_fits(self):
        src = inspect.getsource(R9)
        self.assertNotIn(".fit(", src)
        self.assertNotIn("GridSearch", src)


class TestTestLoaders(unittest.TestCase):
    def test_real_test_features_predictor_only(self):
        rows = R9.load_test_features(FEATS)
        self.assertEqual(len(rows), 350)
        self.assertEqual(len({r["match_id"] for r in rows}), 350)
        self.assertEqual({r["season"] for r in rows}, {"2025-2026"})
        for r in rows:
            self.assertEqual(set(r), {"match_id", "season", "kickoff_datetime", "x"})
            self.assertEqual(set(r["x"]), set(FEATS))

    def test_forbidden_predictor_columns(self):
        for bad in (["result"], ["goal_difference"], ["mkt_avg_pre_home"]):
            with self.assertRaises(R9.ML9Abort):
                R9.load_test_features(bad)

    def test_synthetic_labels_market_and_exclusions(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "features.csv"
            _feature_csv(fp, [("2025-2026", True, "H"), ("2025-2026", False, "A"), ("2024-2025", True, "D"),
                              ("2025-2026", True, "D")])
            rows = R9.load_test_features(FEATS, fp)
            self.assertEqual([r["match_id"] for r in rows], ["m0", "m3"])
            self.assertTrue(all("result" not in r for r in rows))
            self.assertEqual(R9.load_test_labels(["m0", "m3"], fp), {"m0": "H", "m3": "D"})
            with self.assertRaises(R9.ML9Abort):
                R9.load_test_labels(["m0"], fp)
            cp = Path(d) / "canonical.csv"
            cols = [c for _, cs, _ in R8.MARKET_SOURCES for c in cs]
            with open(cp, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["match_id", "season", *cols])
                w.writeheader()
                for mid, s in (("m0", "2025-2026"), ("m3", "2025-2026"), ("m2", "2024-2025")):
                    w.writerow({"match_id": mid, "season": s, **{c: "2.5" for c in cols}})
            odds = R9.load_test_market_odds(["m0", "m3", "m2"], cp)
            self.assertEqual(set(odds), {"m0", "m3"})


class TestSealAndMetrics(unittest.TestCase):
    def test_seal_detects_any_change(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            data = b"run_id,p_H\nx,0.5\n"
            (base / R9.SEALED).write_bytes(data)
            (base / R9.SEAL).write_text(json.dumps({"sha256": R9._sha_bytes(data)}), encoding="utf-8")
            R9.verify_seal(base)
            (base / R9.SEALED).write_bytes(data.replace(b"0.5", b"0.6"))
            with self.assertRaises(R9.ML9Abort):
                R9.verify_seal(base)

    def test_evaluate_refuses_second_run(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(R9, "OUT_DIR", Path(d)):
                (Path(d) / R9.SEALED).write_text("sealed", encoding="utf-8")
                self.assertEqual(R9.cmd_evaluate(), 1)

    def test_tables_use_common_engine_and_train_priors(self):
        rng = np.random.default_rng(1)
        n = 30
        P = rng.dirichlet([3, 2, 2], size=n)
        y = list(rng.choice(["H", "D", "A"], size=n))
        ids = [f"t{i}" for i in range(n)]
        train = ["H"] * 50 + ["D"] * 25 + ["A"] * 25
        odds = {i: {src: ["2.0", "3.4", "3.9"] for src, _, _ in R8.MARKET_SOURCES} for i in ids}
        with mock.patch.object(R9, "comparison_rows", return_value=[]):
            tables, info = R9.build_tables(ids, P, y, train, odds, FEATS)
        self.assertAlmostEqual(tables["ml9_test_metrics.csv"][0]["log_loss"], M.log_loss(y, P)["log_loss"], places=12)
        np.testing.assert_allclose(info["sources"]["B1"][0], [0.5, 0.25, 0.25])     # TRAIN, no TEST
        b1 = next(r for r in tables["ml9_test_baseline_comparison.csv"] if r["source"] == "B1")
        self.assertAlmostEqual(b1["relative_log_loss_improvement_of_knn_vs_B1"],
                               (b1["log_loss"] - M.log_loss(y, P)["log_loss"]) / b1["log_loss"], places=12)
        self.assertEqual(info["coverage"]["MARKET_PRE"]["missing"], 0)
        odds[ids[0]]["MARKET_PRE"][1] = ""
        with mock.patch.object(R9, "comparison_rows", return_value=[]):
            tables, info = R9.build_tables(ids, P, y, train, odds, FEATS)
        self.assertNotIn("MARKET_PRE", info["sources"])                                # no se inventan cuotas
        self.assertEqual(info["coverage"]["MARKET_PRE"]["missing"], 1)


if __name__ == "__main__":
    unittest.main()
