"""Tests de CHECKPOINT C (CANONICAL -> team_match_log -> FEATURES).

Ejecutar desde la raíz de SCOPE/:  python -m unittest discover -s tests -v
Los defectos metodológicos se simulan sustituyendo (mock.patch) piezas del builder real o
alterando en memoria la salida; RAW, INTERIM y CANONICAL solo se leen.
"""
from __future__ import annotations

import csv
import io
import unittest
from unittest import mock

from src.config import settings
from src.data import build_features as BF
from src.data import team_match_log as TML
from src.data.build_interim import serialize_csv
from src.data.canonical_reader import CanonicalMismatch, read_approved_canonical
from src.data.features_schema import FEATURES_COLUMNS, RATE_METRICS
from src.validation.features_checks import (FeaturesContext, check_v11, check_v12, check_v13, check_v16,
                                            check_v17, read_csv)
from src.validation.leakage_checks import check_v14, check_v15, perturb_match
from src.validation.tml_checks import check_c01, check_c02


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = read_approved_canonical()
        cls.canonical_bytes = settings.CANONICAL_FILE.read_bytes()
        cls.can_rows = read_csv(cls.canonical_bytes)[1]
        cls.can_by_id = {m["match_id"]: m for m in cls.can_rows}
        cls.tml, cls.feat = BF.build_all_bytes(cls.canonical)

    def checks(self, feat: bytes, with_oracle: bool = True) -> dict:
        ctx = FeaturesContext(feat, self.canonical_bytes)
        res = [check_v11(ctx), check_v12(ctx), check_v13(ctx), check_v16(ctx), check_v17(ctx)]
        if with_oracle:
            res.append(check_v15(self.can_rows, read_csv(feat)[1]))
        return {r.check_id: r for r in res}

    def assertFails(self, feat: bytes, *ids: str):
        failed = {k for k, r in self.checks(feat).items() if not r.passed}
        for i in ids:
            self.assertIn(i, failed, f"{i} debía fallar; fallaron {sorted(failed)}")

    def build_patched(self, **patches) -> tuple[bytes, bytes]:
        """Construye con piezas defectuosas del builder de features (mock.patch)."""
        with mock.patch.multiple(BF, **patches):
            return BF.build_all_bytes(self.canonical)

    def mutate(self, fn) -> bytes:
        recs = list(csv.reader(io.StringIO(self.feat.decode("utf-8"), newline="")))
        header, rows = recs[0], recs[1:]
        fn(header, rows)
        return serialize_csv(tuple(header), [tuple(r) for r in rows])


class TestOfficialOutputs(Base):
    def test_all_checks_pass(self):
        for r in self.checks(self.feat).values():
            self.assertTrue(r.passed, f"{r.check_id}: {r.details[:3]}")
        self.assertTrue(check_c01(self.tml, 1900).passed)
        self.assertTrue(check_c02(self.tml, self.canonical_bytes).passed)

    def test_shapes_and_eligibility(self):
        h, rows = read_csv(self.feat)
        self.assertEqual((len(rows), len(h)), (1900, 30))
        self.assertEqual(tuple(h), FEATURES_COLUMNS)
        self.assertEqual(len(read_csv(self.tml)[1]), 3800)
        self.assertEqual(sum(x["is_modeling_eligible"] == "true" for x in rows), 1749)
        self.assertFalse(any(c.startswith(("mkt_", "home_", "away_")) for c in h))

    def test_determinism_and_files_on_disk(self):
        self.assertEqual(BF.build_all_bytes(self.canonical), (self.tml, self.feat))
        if settings.FEATURES_FILE.is_file():
            self.assertEqual(settings.FEATURES_FILE.read_bytes(), self.feat)
            self.assertEqual(settings.TEAM_MATCH_LOG_FILE.read_bytes(), self.tml)

    def test_contract_example_semantics(self):
        # Partido 9 de un equipo: n_prev_season = 8 y ppg_season = puntos de sus 8 partidos previos
        h, rows = read_csv(self.feat)
        x = next(r for r in rows if r["h_n_prev_season"] == "8")
        m = self.can_by_id[x["match_id"]]
        team = m["home_team_id"]
        prev = sorted((c for c in self.can_rows if c["season"] == m["season"] and team in
                       (c["home_team_id"], c["away_team_id"]) and c["kickoff_datetime"] < m["kickoff_datetime"]),
                      key=lambda c: c["kickoff_datetime"])
        self.assertEqual(len(prev), 8)
        pts = [3 if (c["result"] == "H") == (c["home_team_id"] == team) and c["result"] != "D" else
               1 if c["result"] == "D" else 0 for c in prev]
        self.assertEqual(float(x["h_ppg_season"]), sum(pts) / 8)

    def test_canonical_gate(self):
        with self.assertRaises(CanonicalMismatch):
            read_approved_canonical(expected_sha256="0" * 64)

    def test_perturbation_is_coherent(self):
        for m in self.canonical[:60]:
            p = perturb_match(m)
            self.assertEqual(p["goal_difference"], p["home_goals"] - p["away_goals"])
            self.assertNotEqual(p["result"], m["result"])
            self.assertLessEqual(p["ht_home_goals"], p["home_goals"])


class TestBuilderDefectsDetected(Base):
    """Errores metodológicos reales inyectados en el builder."""

    def test_shift_removed_includes_current_match(self):
        _, feat = self.build_patched(history_before=lambda entries, i: entries[:i + 1])
        self.assertFails(feat, "V12", "V15")

    def test_shift_removed_detected_by_perturbation(self):
        with mock.patch.object(BF, "history_before", lambda entries, i: entries[:i + 1]):
            r = check_v14(self.canonical, baseline=BF.build_features(self.canonical)[1])
        self.assertFalse(r.passed)
        self.assertTrue(any("propio_t" in d for d in r.details))

    def test_future_match_leaks_into_earlier_match(self):
        leak = lambda entries, i: entries[:i] + entries[i + 1:i + 2]
        _, feat = self.build_patched(history_before=leak)
        self.assertFails(feat, "V15")
        with mock.patch.object(BF, "history_before", leak):
            r = check_v14(self.canonical, baseline=BF.build_features(self.canonical)[1])
        self.assertFalse(r.passed)
        self.assertTrue(any("anteriores_o_simultaneos" in d for d in r.details))

    def test_full_season_aggregate(self):
        _, feat = self.build_patched(history_before=lambda entries, i: entries[:i] + entries[i + 1:])
        self.assertFails(feat, "V12", "V15")

    def test_no_season_reset(self):
        _, feat = self.build_patched(partition_key=lambda e: e["team_id"])
        self.assertFails(feat, "V12", "V15")

    def test_last6_instead_of_last5(self):
        _, feat = self.build_patched(last_window=lambda h, n=5: h[-6:])
        self.assertFails(feat, "V15")

    def test_unordered_window_takes_first_five(self):
        _, feat = self.build_patched(last_window=lambda h, n=5: h[:5])
        self.assertFails(feat, "V15")

    def test_sot_from_wrong_side(self):
        orig = TML.perspective

        def wrong(match, is_home):
            r = orig(match, is_home)
            r["shots_on_target_for"] = match["away_shots_on_target" if is_home else "home_shots_on_target"]
            return r
        with mock.patch.object(TML, "perspective", wrong):
            tml, feat = BF.build_all_bytes(self.canonical)
        self.assertFalse(check_c02(tml, self.canonical_bytes).passed)
        self.assertFails(feat, "V15")

    def test_points_wrong(self):
        with mock.patch.object(TML, "points_for", lambda gf, ga: 3 if gf > ga else 0):
            tml, feat = BF.build_all_bytes(self.canonical)
        self.assertFalse(check_c02(tml, self.canonical_bytes).passed)
        self.assertFails(feat, "V15")

    def test_eligibility_threshold_changed(self):
        with mock.patch.object(settings, "ELIGIBILITY_THRESHOLD", 2):
            _, feat = BF.build_all_bytes(self.canonical)
        self.assertFails(feat, "V13")


class TestOutputDefectsDetected(Base):
    """Defectos directos en el archivo FEATURES."""

    def test_current_match_sot_leaked(self):
        def f(h, rows):
            for r in rows:
                m = self.can_by_id[r[0]]
                if r[h.index("h_sot_pg_last5")]:
                    r[h.index("h_sot_pg_last5")] = repr(float(m["home_shots_on_target"]))
        self.assertFails(self.mutate(f), "V15")

    def test_home_away_swapped(self):
        def f(h, rows):
            for r in rows:
                for m in ("n_prev_season",) + RATE_METRICS:
                    i, j = h.index(f"h_{m}"), h.index(f"a_{m}")
                    r[i], r[j] = r[j], r[i]
        self.assertFails(self.mutate(f), "V15", "V16")

    def test_first_match_imputed_with_zero(self):
        def f(h, rows):
            for r in rows:
                if r[h.index("h_n_prev_season")] == "0":
                    for m in RATE_METRICS:
                        r[h.index(f"h_{m}")] = "0.0"
        self.assertFails(self.mutate(f), "V12", "V17", "V15")

    def test_wrong_diff(self):
        def f(h, rows):
            for r in rows:
                if r[h.index("diff_ppg_season")]:
                    r[h.index("diff_ppg_season")] = repr(-float(r[h.index("diff_ppg_season")]) + 0.5)
                    break
        self.assertFails(self.mutate(f), "V16", "V15")

    def test_eligibility_flag_flipped(self):
        def f(h, rows):
            j = h.index("is_modeling_eligible")
            rows[500][j] = "false" if rows[500][j] == "true" else "true"
        self.assertFails(self.mutate(f), "V13")

    def test_target_modified(self):
        def f(h, rows):
            j = h.index("result")
            rows[10][j] = "D" if rows[10][j] != "D" else "H"
        self.assertFails(self.mutate(f), "V11")

    def test_missing_row(self):
        self.assertFails(self.mutate(lambda h, rows: rows.pop(100)), "V11", "V17")

    def test_duplicated_match_id(self):
        def f(h, rows):
            rows[101] = list(rows[100])
        self.assertFails(self.mutate(f), "V11")

    def test_extra_market_column(self):
        def f(h, rows):
            h.insert(26, "mkt_avg_pre_home")
            for r in rows:
                r.insert(26, self.can_by_id[r[0]]["mkt_avg_pre_home"])
        self.assertFails(self.mutate(f), "V17")

    def test_market_value_infiltrated_as_feature(self):
        def f(h, rows):
            for r in rows:
                if r[h.index("h_ppg_season")]:
                    r[h.index("h_ppg_season")] = self.can_by_id[r[0]]["mkt_avg_pre_home"]
        self.assertFails(self.mutate(f), "V15", "V16")

    def test_missing_column(self):
        def f(h, rows):
            j = h.index("a_sot_pg_last5")
            h.pop(j)
            for r in rows:
                r.pop(j)
        self.assertFails(self.mutate(f), "V17")

    def test_physical_order_wrong(self):
        def f(h, rows):
            rows[0], rows[1] = rows[1], rows[0]
        self.assertFails(self.mutate(f), "V17")

    def test_feature_version_wrong(self):
        def f(h, rows):
            rows[0][h.index("feature_version")] = "0.10"
        self.assertFails(self.mutate(f), "V16", "V17")

    def test_nan_literal_and_rounding(self):
        def f(h, rows):
            rows[0][h.index("h_ppg_season")] = "NaN"
            r = next(r for r in rows if "." in r[h.index("a_ppg_season")] and len(r[h.index("a_ppg_season")]) > 6)
            r[h.index("a_ppg_season")] = r[h.index("a_ppg_season")][:5]
        self.assertFails(self.mutate(f), "V17")

    def test_team_match_log_row_missing_or_not_mirrored(self):
        recs = self.tml.decode("utf-8").splitlines(keepends=True)
        self.assertFalse(check_c01("".join(recs[:-1]).encode(), 1900).passed)
        broken = self.tml.replace(b",true,", b",false,", 1)
        self.assertFalse(check_c02(broken, self.canonical_bytes).passed)


if __name__ == "__main__":
    unittest.main()
