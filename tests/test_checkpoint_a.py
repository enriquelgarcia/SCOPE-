"""Tests de CHECKPOINT A (RAW -> INTERIM).

Ejecutar desde la raíz de SCOPE/:  python -m unittest discover -s tests -v
Los defectos sintéticos se aplican solo en memoria o en copias temporales fuera de SCOPE/.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.config import settings
from src.data.build_interim import build_interim_table, serialize_csv
from src.data.cell_parsing import CellParseError, to_interim_text
from src.data.contract_docs import load_manifest, load_raw_dictionary, raw_data_entries
from src.data.interim_schema import build_interim_schema
from src.data.raw_reader import RawFormatError, parse_raw_bytes, season_from_file_name
from src.validation.interim_checks import parse_interim, run_interim_checks
from src.validation.raw_integrity import check_v01


def _build():
    manifest = load_manifest()
    entries = raw_data_entries(manifest)
    schema = build_interim_schema(load_raw_dictionary())
    from src.data.raw_reader import read_raw_csv
    tables = [read_raw_csv(m.path(settings.PROJECT_ROOT)) for m in entries]
    table = build_interim_table(tables, schema)
    return serialize_csv(table.header, table.rows), table, schema, entries


class CheckpointABase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.table, cls.schema, cls.entries = _build()
        cls.raw_paths = [m.path(settings.PROJECT_ROOT) for m in cls.entries]
        cls.manifest_rows = {m.file_name: m.rows for m in cls.entries}

    def run_checks(self, data: bytes):
        results, _ = run_interim_checks(data, self.schema, self.raw_paths, self.manifest_rows, rebuild=None)
        return {r.check_id: r for r in results}

    def mutate(self, fn) -> bytes:
        header, rows = parse_interim(self.data)
        fn(header, rows)
        return serialize_csv(tuple(header), [tuple(r) for r in rows])

    def assertFails(self, data: bytes, *ids: str):
        res = self.run_checks(data)
        failed = {k for k, r in res.items() if not r.passed}
        for i in ids:
            self.assertIn(i, failed, f"{i} debía fallar; fallaron {sorted(failed)}")


class TestRawIntegrity(unittest.TestCase):
    def test_v01_passes_on_real_raw(self):
        res, hashes = check_v01()
        self.assertTrue(res.passed, res.details)
        self.assertEqual(len(hashes), 6)   # 5 CSV + notes.txt

    def test_v01_detects_one_modified_byte_in_a_copy(self):
        manifest = load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for m in manifest:
                dst = root / m.relative_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(m.path(settings.PROJECT_ROOT), dst)
            self.assertTrue(check_v01(root=root)[0].passed)
            target = root / raw_data_entries(manifest)[2].relative_path
            b = bytearray(target.read_bytes())
            i = b.index(b"Arsenal")
            b[i] = ord("a")
            target.write_bytes(bytes(b))
            res, _ = check_v01(root=root)
            self.assertFalse(res.passed)
            self.assertTrue(any("SHA-256" in d for d in res.details))


class TestParsing(unittest.TestCase):
    def test_bom_and_crlf_tolerated_identically(self):
        body = b"Div,Date,Referee\r\nE0,13/08/2021,M Oliver\r\n"
        a = parse_raw_bytes(b"\xef\xbb\xbf" + body, "PL_2021-2022_raw.csv")
        b = parse_raw_bytes(body, "PL_2021-2022_raw.csv")
        self.assertEqual(a.header, b.header)
        self.assertEqual(a.rows, b.rows)
        self.assertTrue(a.has_bom)
        self.assertFalse(b.has_bom)
        self.assertEqual(a.header[0], "Div")          # sin '﻿' pegado al nombre

    def test_ragged_row_rejected(self):
        with self.assertRaises(RawFormatError):
            parse_raw_bytes(b"A,B\r\n1\r\n", "PL_2021-2022_raw.csv")

    def test_season_from_file_name(self):
        self.assertEqual(season_from_file_name("PL_2024-2025_raw.csv"), "2024-2025")
        with self.assertRaises(RawFormatError):
            season_from_file_name("PL_2024-2026_raw.csv")

    def test_strict_date_and_time(self):
        self.assertEqual(to_interim_text("13/08/2021", "date"), "2021-08-13")
        self.assertEqual(to_interim_text("05/01/2024", "date"), "2024-01-05")   # día/mes
        for bad in ("5/1/2024", "13/08/21", "2021-08-13", "31/02/2024", "13/13/2021"):
            with self.assertRaises((CellParseError, ValueError)):
                to_interim_text(bad, "date")
        self.assertEqual(to_interim_text("09:05", "time"), "09:05")
        for bad in ("9:05", "24:00", "12:60"):
            with self.assertRaises((CellParseError, ValueError)):
                to_interim_text(bad, "time")

    def test_numbers_are_not_silently_fixed(self):
        self.assertEqual(to_interim_text("4", "float"), "4.0")
        self.assertEqual(to_interim_text("1.85", "float"), "1.85")
        self.assertEqual(to_interim_text("", "float"), "")
        for bad, t in ((" 3", "int"), ("3.0", "int"), ("1,85", "float"), ("NaN", "float"), ("inf", "float")):
            with self.assertRaises(CellParseError):
                to_interim_text(bad, t)

    def test_strings_only_stripped(self):
        self.assertEqual(to_interim_text("J Gillett ", "string"), "J Gillett")

    def test_cannot_write_into_raw(self):
        with self.assertRaises(PermissionError):
            settings.assert_writable_output(settings.RAW_DIR / "x.csv")
        with self.assertRaises(PermissionError):
            settings.assert_writable_output(settings.DOCS_DIR / "x.csv")


class TestInterimOutput(CheckpointABase):
    def test_all_checks_pass_on_real_build(self):
        res = self.run_checks(self.data)
        self.assertEqual(len(res), 10)
        for r in res.values():
            self.assertTrue(r.passed, f"{r.check_id}: {r.details[:3]}")

    def test_shape(self):
        header, rows = parse_interim(self.data)
        self.assertEqual(len(header), 4 + 162)
        self.assertEqual(len(rows), 1900)
        self.assertEqual(header[:4], list(settings.TRACE_COLUMNS))

    def test_source_row_is_one_based_data_row(self):
        header, rows = parse_interim(self.data)
        first = rows[0]
        self.assertEqual(first[header.index("source_row")], "1")
        self.assertEqual(first[header.index("Date")], "2021-08-13")
        self.assertEqual((first[header.index("HomeTeam")], first[header.index("AwayTeam")]),
                         ("Brentford", "Arsenal"))

    def test_deterministic_build(self):
        self.assertEqual(_build()[0], self.data)

    def test_file_on_disk_matches_build(self):
        if not settings.INTERIM_FILE.is_file():
            self.skipTest("INTERIM aún no generado; ejecutar python -m src.run_checkpoint_a")
        self.assertEqual(settings.INTERIM_FILE.read_bytes(), self.data)

    def test_known_anomaly_preserved(self):
        header, rows = parse_interim(self.data)
        r = next(x for x in rows if x[2] == "PL_2021-2022_raw.csv" and x[3] == "9")
        self.assertEqual((r[header.index("AS")], r[header.index("AST")]), ("8", "9"))


class TestFloatSerializationD43(CheckpointABase):
    """D43: floats con valor entero llevan parte decimal explícita (4.0, nunca 4)."""

    def test_integral_floats_have_explicit_decimal(self):
        header, rows = parse_interim(self.data)
        float_idx = [i for i, c in enumerate(header) if self.schema.type_of(c) == "float"]
        n_integral = 0
        for r in rows:
            for i in float_idx:
                v = r[i]
                if v == "":
                    continue
                self.assertRegex(v, r"^-?\d+\.\d+$", f"{header[i]}={v!r}")
                if float(v).is_integer():
                    n_integral += 1
                    self.assertTrue(v.endswith(".0"), f"{header[i]}={v!r}")
        self.assertGreater(n_integral, 0)

    def test_avg_columns_integral_values(self):
        header, rows = parse_interim(self.data)
        for c in ("AvgH", "AvgD", "AvgA", "AvgCH", "AvgCD", "AvgCA"):
            j = header.index(c)
            for r in rows:
                if float(r[j]).is_integer():
                    self.assertEqual(r[j], f"{int(float(r[j]))}.0")

    def test_quality_register_q17_q19_preserved(self):
        header, rows = parse_interim(self.data)
        get = lambda f, sr: next(r for r in rows if r[2] == f and r[3] == str(sr))
        r = get("PL_2021-2022_raw.csv", 167)
        self.assertEqual((r[header.index("B365C>2.5")], r[header.index("B365C<2.5")]), ("0.0", "0.0"))
        for sr in range(121, 131):
            self.assertEqual(get("PL_2025-2026_raw.csv", sr)[header.index("MaxAHA")], "22.0")
        self.assertEqual(get("PL_2025-2026_raw.csv", 312)[header.index("MaxAHH")], "3.5")

    def test_integer_text_in_float_column_is_detected(self):
        def f(h, rows):
            j = h.index("AvgH")
            i = next(k for k, r in enumerate(rows) if float(r[j]).is_integer())
            rows[i][j] = rows[i][j][:-2]          # "4.0" -> "4"
        self.assertFails(self.mutate(f), "A10")


class TestChecksDetectSyntheticDefects(CheckpointABase):
    """Autopruebas: cada defecto sintético debe hacer fallar al menos una comprobación."""

    def _col(self, header, name):
        return header.index(name)

    def test_swapped_odds_between_rows(self):
        def f(h, rows):
            j = self._col(h, "AvgH")
            rows[0][j], rows[1][j] = rows[1][j], rows[0][j]
        self.assertFails(self.mutate(f), "A05")

    def test_swapped_stats_between_rows(self):
        def f(h, rows):
            j = self._col(h, "HST")
            rows[10][j], rows[11][j] = rows[11][j], rows[10][j]
        self.assertFails(self.mutate(f), "A05")

    def test_dropped_row(self):
        self.assertFails(self.mutate(lambda h, rows: rows.pop(100)), "A03", "A04")

    def test_duplicated_row(self):
        def f(h, rows):
            rows[5] = list(rows[4])
        self.assertFails(self.mutate(f), "A04")

    def test_duplicated_match_with_new_trace(self):
        def f(h, rows):
            off = len(settings.TRACE_COLUMNS)
            rows[5][off:] = rows[4][off:]
        self.assertFails(self.mutate(f), "A05", "A09")

    def test_day_month_confusion(self):
        def f(h, rows):
            j = self._col(h, "Date")
            i = next(k for k, r in enumerate(rows) if int(r[j][8:]) <= 12 and r[j][5:7] != r[j][8:])
            y, m, d = rows[i][j].split("-")
            rows[i][j] = f"{y}-{d}-{m}"
        self.assertFails(self.mutate(f), "A05")

    def test_zero_based_source_row(self):
        def f(h, rows):
            j = self._col(h, "source_row")
            for r in rows:
                r[j] = str(int(r[j]) - 1)
        self.assertFails(self.mutate(f), "A04")

    def test_value_in_absent_column(self):
        def f(h, rows):
            rows[0][self._col(h, "BFEH")] = "2.0"     # BFE no existe en 2021-22
        self.assertFails(self.mutate(f), "A05", "A07")

    def test_corrected_anomaly_is_detected(self):
        def f(h, rows):
            i = next(k for k, r in enumerate(rows) if r[2] == "PL_2021-2022_raw.csv" and r[3] == "9")
            rows[i][self._col(h, "AST")] = "8"
        self.assertFails(self.mutate(f), "A05", "A08")

    def test_unstripped_referee(self):
        def f(h, rows):
            i = next(k for k, r in enumerate(rows) if r[2] == "PL_2023-2024_raw.csv" and r[3] == "357")
            rows[i][self._col(h, "Referee")] += " "
        self.assertFails(self.mutate(f), "A05")

    def test_imputed_missing_odd(self):
        def f(h, rows):
            j = self._col(h, "PSH")
            i = next(k for k, r in enumerate(rows) if r[0] == "2025-2026" and r[j] == "")
            rows[i][j] = "2.0"
        self.assertFails(self.mutate(f), "A05", "A07")

    def test_null_literal(self):
        def f(h, rows):
            j = self._col(h, "PSH")
            i = next(k for k, r in enumerate(rows) if r[0] == "2025-2026" and r[j] == "")
            rows[i][j] = "NaN"
        self.assertFails(self.mutate(f), "A01")

    def test_bom_and_crlf_in_output(self):
        self.assertFails(b"\xef\xbb\xbf" + self.data, "A01")
        self.assertFails(self.data.replace(b"\n", b"\r\n"), "A01")

    def test_renamed_column(self):
        def f(h, rows):
            h[self._col(h, "FTHG")] = "home_goals"
        self.assertFails(self.mutate(f), "A02")

    def test_rows_reordered(self):
        def f(h, rows):
            rows[0], rows[1] = rows[1], rows[0]
        self.assertFails(self.mutate(f), "A04")


if __name__ == "__main__":
    unittest.main()
