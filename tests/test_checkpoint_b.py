"""Tests de CHECKPOINT B (INTERIM -> CANONICAL).

Ejecutar desde la raíz de SCOPE/:  python -m unittest discover -s tests -v
Los defectos sintéticos se aplican solo en memoria; INTERIM y RAW solo se leen.
"""
from __future__ import annotations

import csv
import hashlib
import io
import unittest

from src.config import settings
from src.data.build_canonical import (InterimMismatch, build_canonical_records, compute_dq_flags,
                                      interim_rows_from_bytes, read_approved_interim, serialize_canonical)
from src.data.build_interim import serialize_csv
from src.data.canonical_schema import CANONICAL_COLUMNS
from src.data.contract_docs import load_manifest, raw_data_entries
from src.data.team_mapping import UnknownTeamAlias, load_team_mapping
from src.validation.canonical_checks import CanonicalContext, run_canonical_checks


def _canonical_bytes() -> bytes:
    return serialize_canonical(build_canonical_records(read_approved_interim(), load_team_mapping()))


class CanonicalBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _canonical_bytes()
        entries = raw_data_entries(load_manifest())
        cls.raw_paths = [m.path(settings.PROJECT_ROOT) for m in entries]
        cls.raw_names = {m.file_name for m in entries}

    def run_checks(self, data: bytes) -> dict:
        ctx = CanonicalContext(data, self.raw_paths, settings.TEAM_MAPPING_PATH, self.raw_names)
        return {r.check_id: r for r in run_canonical_checks(ctx)}

    def table(self):
        recs = list(csv.reader(io.StringIO(self.data.decode("utf-8"), newline="")))
        return recs[0], recs[1:]

    def mutate(self, fn) -> bytes:
        header, rows = self.table()
        fn(header, rows)
        return serialize_csv(tuple(header), [tuple(r) for r in rows])

    def assertFails(self, data: bytes, *ids: str):
        res = self.run_checks(data)
        failed = {k for k, r in res.items() if not r.passed}
        for i in ids:
            self.assertIn(i, failed, f"{i} debía fallar; fallaron {sorted(failed)}")

    @staticmethod
    def idx(header, row_pred, rows):
        return next(i for i, r in enumerate(rows) if row_pred(dict(zip(header, r))))


class TestCanonicalOutput(CanonicalBase):
    def test_all_v02_v10_pass(self):
        res = self.run_checks(self.data)
        self.assertEqual(sorted(res), ["V02", "V03", "V04", "V05", "V06", "V07", "V08", "V09", "V10"])
        for r in res.values():
            self.assertTrue(r.passed, f"{r.check_id}: {r.details[:3]}")

    def test_shape_and_contract_example(self):
        header, rows = self.table()
        self.assertEqual(tuple(header), CANONICAL_COLUMNS)
        self.assertEqual(len(header), 42)
        self.assertEqual(len(rows), 1900)
        first = dict(zip(header, rows[0]))
        self.assertEqual(first["match_id"], "EPL_2021-2022_20210813_brentford_arsenal")   # contrato §8
        self.assertEqual(first["kickoff_datetime"], "2021-08-13T20:00:00")
        self.assertEqual(first["match_seq_season"], "1")

    def test_determinism(self):
        self.assertEqual(hashlib.sha256(_canonical_bytes()).hexdigest(), hashlib.sha256(self.data).hexdigest())

    def test_file_on_disk_matches_build(self):
        if not settings.CANONICAL_FILE.is_file():
            self.skipTest("CANONICAL aún no generado; ejecutar python -m src.run_checkpoint_b")
        self.assertEqual(settings.CANONICAL_FILE.read_bytes(), self.data)

    def test_known_anomalies_kept_and_flagged(self):
        header, rows = self.table()
        q01 = dict(zip(header, rows[self.idx(header, lambda r: r["source_file"] == "PL_2021-2022_raw.csv"
                                             and r["source_row"] == "9", rows)]))
        self.assertEqual((q01["away_shots"], q01["away_shots_on_target"], q01["dq_flags"]), ("8", "9", "AST_GT_AS"))
        q02 = dict(zip(header, rows[self.idx(header, lambda r: r["source_file"] == "PL_2023-2024_raw.csv"
                                             and r["source_row"] == "357", rows)]))
        self.assertEqual(q02["referee"], "J Gillett")

    def test_no_market_columns_beyond_avg(self):
        self.assertEqual([c for c in CANONICAL_COLUMNS if c.startswith("mkt_")],
                         ["mkt_avg_pre_home", "mkt_avg_pre_draw", "mkt_avg_pre_away",
                          "mkt_avg_close_home", "mkt_avg_close_draw", "mkt_avg_close_away"])


class TestBuilderGuards(unittest.TestCase):
    def test_unknown_alias_fails_build(self):
        rows = interim_rows_from_bytes(settings.INTERIM_FILE.read_bytes())
        rows[0] = dict(rows[0], HomeTeam="Brentford FC")
        with self.assertRaises(UnknownTeamAlias):
            build_canonical_records(rows, load_team_mapping())

    def test_unknown_div_fails_build(self):
        rows = interim_rows_from_bytes(settings.INTERIM_FILE.read_bytes())
        rows[0] = dict(rows[0], Div="E1")
        with self.assertRaises(ValueError):
            build_canonical_records(rows, load_team_mapping())

    def test_interim_hash_gate(self):
        with self.assertRaises(InterimMismatch):
            read_approved_interim(expected_sha256="0" * 64)

    def test_dq_flags_catalog_order(self):
        r = dict(home_shots=3, home_shots_on_target=4, away_shots=1, away_shots_on_target=2,
                 home_goals=5, away_goals=0)
        self.assertEqual(compute_dq_flags(r), "HST_GT_HS|AST_GT_AS|GOALS_GT_SOT")
        r.update(home_shots_on_target=1, away_shots_on_target=0, home_goals=0)
        self.assertIsNone(compute_dq_flags(r))


class TestChecksDetectSyntheticDefects(CanonicalBase):
    """Autopruebas (validation_spec §3): cada defecto debe hacer fallar la prueba indicada."""

    def test_team_ids_swapped_between_two_teams_everywhere(self):
        # Intercambio consistente arsenal <-> chelsea (incluso en match_id): solo V07/V03 lo detectan
        def f(h, rows):
            sw = {"arsenal": "chelsea", "chelsea": "arsenal"}
            for r in rows:
                for c in ("home_team_id", "away_team_id"):
                    i = h.index(c)
                    r[i] = sw.get(r[i], r[i])
                d = dict(zip(h, r))
                r[h.index("match_id")] = (f"{d['competition_code']}_{d['season']}_{d['match_date'].replace('-', '')}"
                                          f"_{d['home_team_id']}_{d['away_team_id']}")
        self.assertFails(self.mutate(f), "V07", "V03")

    def test_home_away_ids_swapped_in_one_row(self):
        def f(h, rows):
            a, b = h.index("home_team_id"), h.index("away_team_id")
            rows[3][a], rows[3][b] = rows[3][b], rows[3][a]
        self.assertFails(self.mutate(f), "V07", "V04")

    def test_display_name_wrong(self):
        def f(h, rows):
            rows[0][h.index("home_team_name")] = "Brentford FC"
        self.assertFails(self.mutate(f), "V07", "V03")

    def test_date_serialized_in_raw_format(self):
        def f(h, rows):
            rows[0][h.index("match_date")] = "13/08/2021"
        self.assertFails(self.mutate(f), "V02", "V06")

    def test_day_month_confusion_consistent_iso(self):
        def f(h, rows):
            i = self.idx(h, lambda r: int(r["match_date"][8:]) <= 12 and r["match_date"][5:7] != r["match_date"][8:]
                         and r["match_date"][5:7] in ("08", "09", "10", "11", "12", "01", "02", "03", "04", "05"), rows)
            d = dict(zip(h, rows[i]))
            y, m, dd = d["match_date"].split("-")
            new = f"{y}-{dd}-{m}"
            rows[i][h.index("match_date")] = new
            rows[i][h.index("kickoff_datetime")] = f"{new}T{d['kickoff_time']}:00"
        self.assertFails(self.mutate(f), "V03", "V06")

    def test_kickoff_datetime_inconsistent(self):
        def f(h, rows):
            rows[0][h.index("kickoff_datetime")] = "2021-08-13T20:00:01"
        self.assertFails(self.mutate(f), "V02", "V06")

    def test_wrong_match_id(self):
        def f(h, rows):
            rows[0][h.index("match_id")] = "EPL_2021-2022_20210814_brentford_arsenal"
        self.assertFails(self.mutate(f), "V04")

    def test_odds_from_another_match(self):
        def f(h, rows):
            j = h.index("mkt_avg_pre_home")
            k = next(i for i in range(1, len(rows)) if rows[i][j] != rows[0][j])
            rows[0][j], rows[k][j] = rows[k][j], rows[0][j]
        self.assertFails(self.mutate(f), "V03")

    def test_closing_odds_from_another_match(self):
        def f(h, rows):
            j = h.index("mkt_avg_close_away")
            k = next(i for i in range(1, len(rows)) if rows[i][j] != rows[5][j])
            rows[5][j], rows[k][j] = rows[k][j], rows[5][j]
        self.assertFails(self.mutate(f), "V03")

    def test_stats_from_another_match(self):
        def f(h, rows):
            j = h.index("home_corners")
            k = next(i for i in range(1, len(rows)) if rows[i][j] != rows[0][j])
            rows[0][j], rows[k][j] = rows[k][j], rows[0][j]
        self.assertFails(self.mutate(f), "V03")

    def test_wrong_source_row(self):
        def f(h, rows):
            j = h.index("source_row")
            rows[10][j] = str(int(rows[10][j]) + 1)
        self.assertFails(self.mutate(f), "V03")

    def test_inconsistent_target(self):
        def f(h, rows):
            j = h.index("result")
            rows[0][j] = "D" if rows[0][j] != "D" else "H"
        self.assertFails(self.mutate(f), "V09", "V03")

    def test_wrong_goal_difference(self):
        def f(h, rows):
            j = h.index("goal_difference")
            rows[0][j] = str(int(rows[0][j]) + 1)
        self.assertFails(self.mutate(f), "V09")

    def test_coherent_but_fake_score(self):
        # goles, diferencia, resultado y HT cambiados juntos (fila válida): solo V03 lo detecta
        def f(h, rows):
            for c, v in (("home_goals", "0"), ("away_goals", "0"), ("ht_home_goals", "0"), ("ht_away_goals", "0"),
                         ("ht_result", "D"), ("result", "D"), ("goal_difference", "0")):
                rows[0][h.index(c)] = v
        self.assertFails(self.mutate(f), "V03")

    def test_dq_flag_moved_to_wrong_row(self):
        # totales correctos, localización incorrecta
        def f(h, rows):
            j = h.index("dq_flags")
            src = self.idx(h, lambda r: r["dq_flags"] == "AST_GT_AS", rows)
            dst = self.idx(h, lambda r: r["dq_flags"] == "", rows)
            rows[src][j], rows[dst][j] = "", "AST_GT_AS"
        self.assertFails(self.mutate(f), "V10")

    def test_dq_flags_wrong_order(self):
        def f(h, rows):
            rows[0][h.index("dq_flags")] = "GOALS_GT_SOT|AST_GT_AS"
        self.assertFails(self.mutate(f), "V02", "V10")

    def test_dq_flags_literal_none(self):
        def f(h, rows):
            rows[0][h.index("dq_flags")] = "NONE"
        self.assertFails(self.mutate(f), "V02", "V10")

    def test_extra_column(self):
        def f(h, rows):
            h.append("p_home")
            for r in rows:
                r.append("0.5")
        self.assertFails(self.mutate(f), "V02")

    def test_missing_column(self):
        def f(h, rows):
            j = h.index("referee")
            h.pop(j)
            for r in rows:
                r.pop(j)
        self.assertFails(self.mutate(f), "V02")

    def test_float_written_as_integer(self):
        def f(h, rows):
            j = h.index("mkt_avg_pre_home")
            i = next(k for k, r in enumerate(rows) if float(r[j]).is_integer())
            rows[i][j] = rows[i][j][:-2]                       # "4.0" -> "4" (viola D43)
        self.assertFails(self.mutate(f), "V02")

    def test_rounded_float(self):
        def f(h, rows):
            rows[0][h.index("mkt_avg_pre_home")] = "4.020"
        self.assertFails(self.mutate(f), "V02")

    def test_wrong_match_seq_season(self):
        def f(h, rows):
            j = h.index("match_seq_season")
            rows[0][j], rows[1][j] = rows[1][j], rows[0][j]
        self.assertFails(self.mutate(f), "V06")

    def test_rows_out_of_order(self):
        def f(h, rows):
            rows[0], rows[1] = rows[1], rows[0]
        self.assertFails(self.mutate(f), "V02")

    def test_duplicate_fixture_and_missing_fixture(self):
        def f(h, rows):
            d0 = dict(zip(h, rows[0]))
            i = self.idx(h, lambda r: r["season"] == d0["season"] and r["home_team_id"] == d0["home_team_id"]
                         and r["away_team_id"] != d0["away_team_id"], rows)
            rows[i][h.index("away_team_id")] = d0["away_team_id"]
        self.assertFails(self.mutate(f), "V05", "V07")

    def test_dropped_row(self):
        self.assertFails(self.mutate(lambda h, rows: rows.pop(50)), "V03", "V05")

    def test_market_odd_not_above_one(self):
        def f(h, rows):
            rows[0][h.index("mkt_avg_close_draw")] = "1.0"
        self.assertFails(self.mutate(f), "V08")

    def test_ht_greater_than_ft(self):
        def f(h, rows):
            rows[0][h.index("ht_away_goals")] = "3"
        self.assertFails(self.mutate(f), "V08")

    def test_bom_and_crlf(self):
        self.assertFails(b"\xef\xbb\xbf" + self.data, "V02")
        self.assertFails(self.data.replace(b"\n", b"\r\n"), "V02")

    def test_unstripped_referee(self):
        def f(h, rows):
            rows[0][h.index("referee")] += " "
        self.assertFails(self.mutate(f), "V02", "V03")


if __name__ == "__main__":
    unittest.main()
