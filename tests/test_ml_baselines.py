"""Tests de baselines B0/B1 y de los guardas de alcance de ML-1.

Ejecutar desde la raíz de SCOPE/:  python -m unittest tests.test_ml_baselines -v
Los tests de alcance leen FEATURES v0.1 congelado (D44) solo para comprobar qué filas se cargan
y los tamaños de los folds; no calculan métricas.
"""
from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.config import settings
from src.eda import eda_io
from src.ml import baselines as B
from src.ml import run_ml1 as R

H, D, A = "H", "D", "A"


class TestBaselines(unittest.TestCase):
    def test_class_prior_frequencies(self):
        np.testing.assert_allclose(B.class_prior([H, H, D, A, H, A, H, D]), [0.5, 0.25, 0.25])

    def test_prior_sums_to_one_and_ignores_order(self):
        y = [A, H, D, H, H, A, D]
        p = B.class_prior(y)
        self.assertAlmostEqual(p.sum(), 1.0, delta=1e-12)
        np.testing.assert_array_equal(p, B.class_prior(sorted(y)))

    def test_majority_and_tie_break(self):
        self.assertEqual(B.majority_class([A, A, H]), A)
        self.assertEqual(B.majority_class([A, H, D]), H)            # empate triple → H
        self.assertEqual(B.majority_class([D, A, D, A]), D)          # empate D/A → D

    def test_b0_is_one_hot_majority(self):
        np.testing.assert_array_equal(B.baseline_distribution("B0", [A, A, H]), [0, 0, 1])

    def test_baseline_proba_shape_and_constancy(self):
        P = B.baseline_proba("B1", [H, D, A, H], 5)
        self.assertEqual(P.shape, (5, 3))
        self.assertTrue((P == P[0]).all())

    def test_rejects_unknown_or_empty(self):
        with self.assertRaises(Exception):
            B.class_prior([])
        with self.assertRaises(Exception):
            B.class_prior([H, "X"])
        with self.assertRaises(ValueError):
            B.baseline_distribution("B9", [H])

    def test_prior_depends_only_on_given_train(self):
        self.assertFalse(np.array_equal(B.class_prior([H, H, D]), B.class_prior([H, H, D, A, A])))


class TestScopeAndFolds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        eda_io.verify_frozen_inputs()                                 # D44
        cls.rows = R.load_train_labels()

    def test_only_train_seasons_loaded(self):
        seasons = {r["season"] for r in self.rows}
        self.assertEqual(seasons, set(eda_io.SEASONS_TRAIN_DESIGN))
        self.assertNotIn(eda_io.SEASON_VALIDATION, seasons)
        self.assertNotIn(eda_io.SEASON_FINAL_TEST, seasons)
        self.assertEqual(len(self.rows), 1049)
        self.assertEqual({k for r in self.rows for k in r}, {"match_id", "season", "kickoff_datetime", "result"})

    def test_fold_sizes_and_temporal_order(self):
        folds = R.build_folds(self.rows)
        self.assertEqual([(f["fold"], len(f["train"]), len(f["eval"])) for f in folds],
                         [("T1", 350, 350), ("T2", 700, 349)])
        for f in folds:
            self.assertLess(max(r["kickoff_datetime"] for r in f["train"]),
                            min(r["kickoff_datetime"] for r in f["eval"]))

    def test_fold_guard_rejects_future_rows_in_train(self):
        bad = [dict(r) for r in self.rows]
        # Mover un partido de 2023/24 a la temporada 2021/22 del train → conteos/orden inválidos
        victim = next(r for r in bad if r["season"] == "2023-2024")
        victim["season"] = "2021-2022"
        with self.assertRaises(R.ML1Abort):
            R.build_folds(bad)

    def test_loader_rejects_file_without_train_seasons(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            src = settings.FEATURES_FILE
            dst = tmp / "features_only_dev_val.csv"
            with open(src, newline="", encoding="utf-8") as fi, open(dst, "w", newline="", encoding="utf-8") as fo:
                rd = csv.DictReader(fi)
                wr = csv.DictWriter(fo, fieldnames=rd.fieldnames, lineterminator="\n")
                wr.writeheader()
                for r in rd:
                    if r["season"] in ("2021-2022", "2022-2023"):     # falta 2023/24
                        wr.writerow(r)
            with self.assertRaises(R.ML1Abort):
                R.load_train_labels(dst)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
