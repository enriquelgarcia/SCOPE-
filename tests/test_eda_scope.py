"""Tests de seguridad del EDA (scopes temporales e integridad de entradas congeladas).

Adicionales a los 104 tests del pipeline (A/B/C), que no se modifican.
Ejecutar desde la raíz de SCOPE/:  python -m unittest tests.test_eda_scope -v
Solo leen los artefactos congelados; las escrituras de prueba van a directorios temporales.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from src.eda import eda_io as io

FAKE_SHA = "0" * 64


class TestIntegrity(unittest.TestCase):
    def test_frozen_inputs_match_d44(self):
        self.assertEqual(io.verify_frozen_inputs(), io.FROZEN_SHA256)

    def test_sha_mismatch_raises(self):
        bad = dict(io.FROZEN_SHA256, FEATURES=FAKE_SHA)
        with self.assertRaises(io.FrozenInputMismatch):
            io.verify_frozen_inputs(expected=bad)

    def test_altered_copy_raises(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            copy = tmp / "features_copy.csv"
            data = io.FEATURES_FILE.read_bytes()
            copy.write_bytes(data.replace(b"\n", b"\r\n"))          # p. ej. reserialización CRLF
            paths = dict(io.FROZEN_PATHS, FEATURES=copy)
            with self.assertRaises(io.FrozenInputMismatch):
                io.verify_frozen_inputs(paths=paths)
            with self.assertRaises(io.FrozenInputMismatch):
                io.load_features(io.ALL_DESCRIPTIVE, path=copy)
        finally:
            shutil.rmtree(tmp)

    def test_loaders_check_sha(self):
        for loader in (io.load_canonical, io.load_features, io.load_team_match_log):
            with self.assertRaises(io.FrozenInputMismatch):
                loader(io.ALL_DESCRIPTIVE, expected_sha256=FAKE_SHA)


class TestScopes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = {(name, kind): loader(scope)
                      for name, scope in io.SCOPES.items()
                      for kind, loader in (("canonical", io.load_canonical),
                                           ("features", io.load_features))}

    def seasons(self, scope, kind):
        return set(self.loaded[(scope, kind)]["season"].unique())

    def test_constants(self):
        self.assertEqual(io.SEASONS_TRAIN_DESIGN, ("2021-2022", "2022-2023", "2023-2024"))
        self.assertEqual(io.SEASON_VALIDATION, "2024-2025")
        self.assertEqual(io.SEASON_FINAL_TEST, "2025-2026")
        self.assertEqual(set(io.SEASONS_TRAIN_DESIGN) | {io.SEASON_VALIDATION, io.SEASON_FINAL_TEST},
                         set(io.SEASONS_ALL))

    def test_train_target_only_train_seasons(self):
        for kind in ("canonical", "features"):
            self.assertEqual(self.seasons("TRAIN_TARGET", kind), set(io.SEASONS_TRAIN_DESIGN))
        tml = io.load_team_match_log(io.TRAIN_TARGET)
        self.assertEqual(set(tml["season"].unique()), set(io.SEASONS_TRAIN_DESIGN))

    def test_dev_predictors_seasons(self):
        for kind in ("canonical", "features"):
            self.assertEqual(self.seasons("DEV_PREDICTORS", kind),
                             set(io.SEASONS_TRAIN_DESIGN) | {io.SEASON_VALIDATION})

    def test_dev_predictors_excludes_target_post_market(self):
        forbidden_can = {c for c, r in io.CANONICAL_ROLES.items() if r in ("TARGET", "POST", "MARKET", "DQ")}
        for kind in ("canonical", "features"):
            cols = set(self.loaded[("DEV_PREDICTORS", kind)].columns)
            self.assertNotIn("result", cols)
            self.assertNotIn("goal_difference", cols)
            self.assertFalse(cols & forbidden_can, cols & forbidden_can)
            self.assertFalse(any(c.startswith("mkt_") for c in cols))
        self.assertEqual(tuple(self.loaded[("DEV_PREDICTORS", "features")].columns),
                         io.DEVX_FEATURES_COLUMNS)
        self.assertEqual(tuple(self.loaded[("DEV_PREDICTORS", "canonical")].columns),
                         io.DEVX_CANONICAL_COLUMNS)

    def test_dev_predictors_refuses_team_match_log(self):
        with self.assertRaises(io.ScopeViolation):
            io.load_team_match_log(io.DEV_PREDICTORS)

    def test_validation_only_2024_25(self):
        for kind in ("canonical", "features"):
            self.assertEqual(self.seasons("VAL_DESCRIPTIVE", kind), {"2024-2025"})

    def test_test_only_2025_26(self):
        for kind in ("canonical", "features"):
            self.assertEqual(self.seasons("TEST_DESCRIPTIVE", kind), {"2025-2026"})

    def test_all_descriptive_complete(self):
        self.assertEqual(len(self.loaded[("ALL_DESCRIPTIVE", "canonical")]), 1900)
        self.assertEqual(len(self.loaded[("ALL_DESCRIPTIVE", "features")]), 1900)
        self.assertEqual(self.seasons("ALL_DESCRIPTIVE", "features"), set(io.SEASONS_ALL))


ROOT = io.settings.PROJECT_ROOT

# Destinos que la guarda debe rechazar. Las rutas solo se construyen; nunca se crean.
FORBIDDEN_TARGETS = [
    ROOT / "data" / "canonical" / "tables" / "t__ALL.csv",      # el incidente original
    ROOT / "data" / "x.csv",
    ROOT / "data" / "interim" / "x.csv",
    ROOT / "data" / "features" / "x.csv",
    *io.FROZEN_PATHS.values(),                                  # los cuatro artefactos D44
    ROOT / "Premier_League_data_raw_csv" / "x.csv",
    ROOT / "Premier_League_data_xlsx" / "x.csv",
    ROOT / "Documentacion de datos" / "x.txt",
    ROOT / "docs" / "EDA" / "x.md",
    ROOT / "docs" / ".obsidian" / "x.json",
    ROOT / "src" / "eda" / "x.csv",
    ROOT / "tests" / "x.csv",
    ROOT / "reports" / "x.csv",
    ROOT / "reports" / "checkpoint_c" / "x.md",
    ROOT / "x.csv",
    io.EDA_REPORTS_DIR,                                         # la propia raíz no es un archivo válido
    io.EDA_REPORTS_DIR / ".." / ".." / "data" / "x.csv",        # traversal
    ROOT.parent / "fuera_de_scope_no_temporal.csv",             # fuera de SCOPE y no temporal
]
FORBIDDEN_OUT_ROOTS = [ROOT, ROOT / "data", ROOT / "data" / "canonical", ROOT / "docs",
                       ROOT / "src", ROOT / "tests", ROOT / "reports", ROOT / "Premier_League_data_raw_csv"]


def _snapshot(dirs):
    """Contenido actual (nombres) de carpetas existentes, para comprobar que nada aparece."""
    return {d: sorted(p.name for p in d.iterdir()) for d in dirs if d.is_dir()}


class TestOutputGuard(unittest.TestCase):
    """Pruebas sin escritura real: la guarda es pura y las operaciones de E/S se sustituyen por mocks."""

    def test_guard_rejects_forbidden_paths(self):
        for target in FORBIDDEN_TARGETS:
            with self.subTest(target=str(target)):
                with self.assertRaises(PermissionError):
                    io.assert_allowed_output(target)

    def test_guard_allows_reports_eda_and_temp(self):
        io.assert_allowed_output(io.EDA_REPORTS_DIR / "tables" / "x__ALL.csv")
        io.assert_allowed_output(io.EDA_REPORTS_DIR / "eda_run_manifest.json")
        io.assert_allowed_output(Path(tempfile.gettempdir()) / "scope_eda_test" / "x.csv")

    def _io_mocks(self):
        return (mock.patch.object(pd.DataFrame, "to_csv"), mock.patch.object(Path, "mkdir"),
                mock.patch.object(Path, "write_text"), mock.patch("builtins.open"))

    def test_write_table_forbidden_root_performs_no_io(self):
        before = _snapshot(FORBIDDEN_OUT_ROOTS)
        df = pd.DataFrame({"x": [1]})
        m_csv, m_mkdir, m_wt, m_open = self._io_mocks()
        with m_csv as to_csv, m_mkdir as mkdir, m_wt as write_text, m_open as open_:
            for out_root in FORBIDDEN_OUT_ROOTS:
                with self.subTest(out_root=str(out_root)):
                    with self.assertRaises(PermissionError):
                        io.write_table(df, "t", phase="TEST", scope=io.ALL_DESCRIPTIVE, out_root=out_root)
            for m in (to_csv, mkdir, write_text, open_):
                m.assert_not_called()
        self.assertEqual(before, _snapshot(FORBIDDEN_OUT_ROOTS))

    def test_update_manifest_forbidden_root_performs_no_io(self):
        before = _snapshot(FORBIDDEN_OUT_ROOTS)
        m_csv, m_mkdir, m_wt, m_open = self._io_mocks()
        with m_csv, m_mkdir as mkdir, m_wt as write_text, m_open as open_:
            for out_root in FORBIDDEN_OUT_ROOTS:
                with self.subTest(out_root=str(out_root)):
                    with self.assertRaises(PermissionError):
                        io.update_manifest("TEST", ["ALL_DESCRIPTIVE"], {}, [], out_root=out_root)
            for m in (mkdir, write_text, open_):
                m.assert_not_called()
        self.assertEqual(before, _snapshot(FORBIDDEN_OUT_ROOTS))


class TestSafeWrites(unittest.TestCase):
    """Escrituras reales, siempre en un directorio temporal fuera de SCOPE/."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="scope_eda_test_"))
        self.assertNotIn(ROOT.resolve(), self.root.resolve().parents)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_suffix_and_manifest(self):
        df = pd.DataFrame({"season": ["2021-2022"], "x": [1]})
        rec = io.write_table(df, "t_demo", phase="TEST", scope=io.TRAIN_TARGET, out_root=self.root)
        self.assertTrue(rec.path.endswith("t_demo__TRAIN.csv"))
        self.assertEqual(rec.scope, "TRAIN_TARGET")
        self.assertEqual((self.root / "tables" / "t_demo__TRAIN.csv").read_bytes(), b"season,x\n2021-2022,1\n")
        m = io.update_manifest("TEST", ["TRAIN_TARGET"], io.FROZEN_SHA256, [rec], out_root=self.root)
        self.assertTrue(m.is_file())

    def test_write_rejects_out_of_scope_seasons(self):
        df = pd.DataFrame({"season": ["2025-2026"], "x": [1]})
        with self.assertRaises(io.ScopeViolation):
            io.write_table(df, "t_bad", phase="TEST", scope=io.TRAIN_TARGET, out_root=self.root)

    def test_write_rejects_target_in_devx(self):
        df = pd.DataFrame({"season": ["2021-2022"], "goal_difference": [1]})
        with self.assertRaises(io.ScopeViolation):
            io.write_table(df, "t_bad", phase="TEST", scope=io.DEV_PREDICTORS, out_root=self.root)

    def test_write_rejects_bad_names(self):
        for name in ("t__ALL", "t.csv", "sub/t", "sub\\t"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    io.write_table(pd.DataFrame({"x": [1]}), name, phase="TEST",
                                   scope=io.ALL_DESCRIPTIVE, out_root=self.root)


def tearDownModule():
    # Ninguna prueba puede haber alterado los artefactos congelados.
    io.verify_frozen_inputs()


if __name__ == "__main__":
    unittest.main()
