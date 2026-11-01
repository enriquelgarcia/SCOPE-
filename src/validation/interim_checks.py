"""Validaciones de CHECKPOINT A (RAW -> INTERIM).

IDs `A01`–`A11`: comprobaciones internas de este checkpoint (no son IDs del contrato;
V01 es la única prueba de validation_spec_v0.1 que aplica a esta capa).

Independencia: RAW se vuelve a leer aquí con `csv.DictReader` + `utf-8-sig`, sin usar
`raw_reader` ni `build_interim`; INTERIM se lee desde los bytes del archivo generado.
"""
from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.config import settings
from src.data import interim_schema as S
from src.data.interim_schema import InterimSchema
from src.validation.results import CheckResult

# Expectativas documentadas en docs/quality/data_quality_register_v0.1.md
EXPECTED_STRIPPED_CELLS = {("PL_2023-2024_raw.csv", 357, "Referee")}          # Q02
Q01_LOCATION = ("PL_2021-2022_raw.csv", 9, {"AS": "8", "AST": "9"})            # AST_GT_AS
EXPECTED_DQ_COUNTS = {"HST_GT_HS": 0, "AST_GT_AS": 1, "GOALS_GT_SOT": 12}      # §1


# ---------------------------------------------------------------- lectura independiente
class IndependentRaw:
    """RAW re-leído de forma independiente: {source_file: (season, header, [dict por fila])}."""

    def __init__(self, raw_paths: list[Path]):
        self.files: dict[str, tuple[str, list[str], list[dict[str, str]]]] = {}
        for p in raw_paths:
            with open(p, encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                m = re.match(settings.RAW_FILE_PATTERN, p.name)
                self.files[p.name] = (f"{m.group(1)}-{m.group(2)}", list(reader.fieldnames), rows)


def parse_interim(data: bytes) -> tuple[list[str], list[list[str]]]:
    text = data.decode("utf-8")
    records = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    return records[0], records[1:]


# ---------------------------------------------------------------- comprobaciones
def check_file_format(data: bytes) -> CheckResult:
    r = CheckResult("A01", "Formato de archivo INTERIM (UTF-8 sin BOM, LF, sin literales nulos)")
    if data.startswith(b"\xef\xbb\xbf"):
        r.fail("El archivo empieza con BOM")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        r.fail(f"No es UTF-8 válido: {exc}")
        return r
    if b"\r" in data:
        n_cr = data.count(b"\r")
        r.fail(f"Contiene {n_cr} caracteres CR")
    if not data.endswith(b"\n"):
        r.fail("La última línea no termina en LF")
    header, rows = parse_interim(data)
    widths = Counter(len(x) for x in rows)
    if set(widths) != {len(header)}:
        r.fail(f"Anchos de fila inconsistentes: {dict(widths)}")
    for i, row in enumerate(rows, start=1):
        for c, v in zip(header, row):
            if v in settings.NULL_LITERALS:
                r.fail(f"Fila {i}, {c}: literal nulo {v!r}")
    return r


def check_schema(header: list[str], schema: InterimSchema, raw: IndependentRaw) -> CheckResult:
    r = CheckResult("A02", "Esquema: 4 columnas de trazabilidad + unión de 162 columnas RAW")
    expected = list(settings.TRACE_COLUMNS) + list(schema.raw_columns)
    if header != expected:
        r.fail("La cabecera no coincide con TRACE_COLUMNS + orden del diccionario RAW")
    if len(set(header)) != len(header):
        r.fail("Cabecera con nombres duplicados")
    union: list[str] = []
    for name in sorted(raw.files):
        for c in raw.files[name][1]:
            if c not in union:
                union.append(c)
    if len(union) != settings.EXPECTED_UNION_COLUMNS:
        r.fail(f"Unión RAW independiente = {len(union)} columnas (se esperan {settings.EXPECTED_UNION_COLUMNS})")
    if union != list(schema.raw_columns):
        r.fail("La unión RAW (orden de primera aparición) no coincide con el diccionario")
    common = set.intersection(*(set(v[1]) for v in raw.files.values()))
    if len(common) != settings.EXPECTED_COMMON_COLUMNS:
        r.fail(f"Columnas comunes = {len(common)} (se esperan {settings.EXPECTED_COMMON_COLUMNS})")
    for name, (season, cols, _) in sorted(raw.files.items()):
        dict_cols = {c for c, p in schema.presence.items() if p.get(season)}
        if set(cols) != dict_cols:
            r.fail(f"{name}: columnas RAW distintas de las marcadas presentes en el diccionario")
        r.info.append(f"{season}: {len(cols)} columnas RAW")
    r.info.append(f"INTERIM: {len(header)} columnas = {len(settings.TRACE_COLUMNS)} trazabilidad + "
                  f"{len(header) - len(settings.TRACE_COLUMNS)} RAW; comunes a 5 temporadas: {len(common)}")
    return r


def check_counts(header: list[str], rows: list[list[str]], raw: IndependentRaw,
                 manifest_rows: dict[str, int]) -> CheckResult:
    r = CheckResult("A03", "Conteos: 5 temporadas, 380 filas por temporada, 1,900 en total")
    si = header.index("season")
    per_season = Counter(row[si] for row in rows)
    if len(rows) != settings.EXPECTED_SEASONS * settings.ROWS_PER_SEASON:
        r.fail(f"Total de filas = {len(rows)}")
    if len(per_season) != settings.EXPECTED_SEASONS:
        r.fail(f"Temporadas = {sorted(per_season)}")
    for name, (season, _, raw_rows) in sorted(raw.files.items()):
        n = per_season.get(season, 0)
        if not (n == len(raw_rows) == manifest_rows.get(name) == settings.ROWS_PER_SEASON):
            r.fail(f"{season}: INTERIM={n}, RAW={len(raw_rows)}, manifiesto={manifest_rows.get(name)}")
        r.info.append(f"{season}: {n} filas")
    r.info.append(f"Total: {len(rows)} filas")
    return r


def check_traceability(header: list[str], rows: list[list[str]], raw: IndependentRaw) -> CheckResult:
    r = CheckResult("A04", "Trazabilidad 1:1 (season, source_name, source_file, source_row)")
    si, ni, fi, ri = (header.index(c) for c in settings.TRACE_COLUMNS)
    keys = []
    for i, row in enumerate(rows, start=1):
        f, sr = row[fi], row[ri]
        if f not in raw.files:
            r.fail(f"Fila {i}: source_file desconocido {f!r}")
            continue
        if not re.fullmatch(r"[1-9]\d*", sr):
            r.fail(f"Fila {i}: source_row no es entero positivo: {sr!r}")
            continue
        if row[si] != raw.files[f][0]:
            r.fail(f"Fila {i}: season {row[si]} no corresponde a {f}")
        if row[ni] != settings.SOURCE_NAME:
            r.fail(f"Fila {i}: source_name {row[ni]!r}")
        keys.append((row[si], f, int(sr)))
    dup = [k for k, c in Counter(keys).items() if c > 1]
    if dup:
        r.fail(f"(source_file, source_row) repetidos: {dup[:10]}")
    expected = {(s, f, n) for f, (s, _, rr) in raw.files.items() for n in range(1, len(rr) + 1)}
    if set(keys) != expected:
        r.fail(f"Filas RAW omitidas: {len(expected - set(keys))}; filas sin origen: {len(set(keys) - expected)}")
    if keys != sorted(keys):
        r.fail("Las filas no están ordenadas por (season, source_row)")
    return r


def _expected_cell(raw_value: str, logical_type: str) -> str | None:
    """Expectativa independiente; None si el texto RAW no es válido para su tipo."""
    if logical_type in (S.STRING, S.CATEGORICAL):
        return raw_value.strip()
    if raw_value == "":
        return ""
    if logical_type == S.DATE:
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw_value):
            return None
        d, m, y = raw_value.split("/")
        return f"{y}-{m}-{d}"
    if logical_type == S.TIME:
        return raw_value if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", raw_value) else None
    return raw_value   # int/float: se comparan numéricamente


def check_cell_fidelity(header: list[str], rows: list[list[str]], schema: InterimSchema,
                        raw: IndependentRaw) -> tuple[CheckResult, list[tuple[str, int, str, str, str]]]:
    r = CheckResult("A05", "Fidelidad celda a celda con RAW (re-lectura independiente)")
    fi, ri = header.index("source_file"), header.index("source_row")
    changed_strings = []
    compared = 0
    off = len(settings.TRACE_COLUMNS)
    for row in rows:
        f, sr = row[fi], int(row[ri])
        season, raw_cols, raw_rows = raw.files[f]
        raw_row = raw_rows[sr - 1]
        for j, col in enumerate(schema.raw_columns):
            v = row[off + j]
            t = schema.type_of(col)
            if col not in raw_row:
                if v != "":
                    r.fail(f"{f}:{sr} {col}: columna ausente en {season} pero INTERIM={v!r}")
                continue
            rv = raw_row[col]
            compared += 1
            exp = _expected_cell(rv, t)
            if exp is None:
                r.fail(f"{f}:{sr} {col}: valor RAW no válido para {t}: {rv!r}")
            elif t in (S.INT, S.FLOAT) and rv != "":
                try:
                    ok = v != "" and (int(v) == int(rv) if t == S.INT else float(v) == float(rv))
                except ValueError:
                    ok = False
                if not ok:
                    r.fail(f"{f}:{sr} {col}: RAW={rv!r} INTERIM={v!r}")
            elif v != exp:
                r.fail(f"{f}:{sr} {col}: RAW={rv!r} esperado={exp!r} INTERIM={v!r}")
            if t == S.DATE and v and v == exp and datetime.strptime(v, settings.ISO_DATE_FORMAT).strftime(
                    settings.RAW_DATE_FORMAT) != rv:
                r.fail(f"{f}:{sr} {col}: la fecha ISO no reproduce la fecha RAW (día/mes)")
            if t in (S.STRING, S.CATEGORICAL) and v != rv:
                changed_strings.append((f, sr, col, rv, v))
    r.info.append(f"Celdas RAW comparadas: {compared}")
    return r, changed_strings


def check_surface_cleaning(changed: list[tuple[str, int, str, str, str]]) -> CheckResult:
    r = CheckResult("A06", "Limpieza superficial: solo strip() en las celdas documentadas (Q02)")
    got = {(f, sr, c) for f, sr, c, _, _ in changed}
    if got != EXPECTED_STRIPPED_CELLS:
        r.fail(f"Celdas de texto modificadas {sorted(got)} != esperadas {sorted(EXPECTED_STRIPPED_CELLS)}")
    for f, sr, c, rv, v in changed:
        if rv.strip() != v:
            r.fail(f"{f}:{sr} {c}: cambio distinto de strip()")
        r.info.append(f"{f} source_row={sr} {c}: {rv!r} -> {v!r}")
    return r


def check_nulls(header: list[str], rows: list[list[str]], schema: InterimSchema,
                raw: IndependentRaw) -> CheckResult:
    r = CheckResult("A07", "Nulos por temporada y columna: INTERIM == RAW; ausentes = 100 % vacíos")
    si = header.index("season")
    off = len(settings.TRACE_COLUMNS)
    by_season = {s: (cols, rr) for s, cols, rr in raw.files.values()}
    total_absent = 0
    for season, (cols, raw_rows) in sorted(by_season.items()):
        srows = [row for row in rows if row[si] == season]
        for j, col in enumerate(schema.raw_columns):
            n_int = sum(1 for row in srows if row[off + j] == "")
            if col in cols:
                n_raw = sum(1 for x in raw_rows if x[col].strip() == "")
            else:
                n_raw = len(raw_rows)
                total_absent += 1
            if n_int != n_raw:
                r.fail(f"{season} {col}: vacíos INTERIM={n_int} RAW={n_raw}")
        for col in schema.raw_columns:
            if schema.presence[col].get(season) != (col in cols):
                r.fail(f"{season} {col}: presencia distinta de la del diccionario")
    r.info.append(f"Pares (temporada, columna) ausentes representados como vacío: {total_absent}")
    return r


def check_anomalies_preserved(header: list[str], rows: list[list[str]]) -> CheckResult:
    r = CheckResult("A08", "Anomalías conocidas conservadas sin corregir (Q01 y conteos de dq_flags)")
    idx = {c: header.index(c) for c in ("source_file", "source_row", "HS", "AS", "HST", "AST", "FTHG", "FTAG")}
    f, sr, vals = Q01_LOCATION
    hit = [row for row in rows if row[idx["source_file"]] == f and row[idx["source_row"]] == str(sr)]
    if len(hit) != 1 or any(hit[0][idx[c]] != v for c, v in vals.items()):
        r.fail(f"Q01 no conservado en {f}:{sr}")
    g = lambda row, c: int(row[idx[c]])
    counts = {
        "HST_GT_HS": sum(g(x, "HST") > g(x, "HS") for x in rows),
        "AST_GT_AS": sum(g(x, "AST") > g(x, "AS") for x in rows),
        "GOALS_GT_SOT": sum(g(x, "FTHG") > g(x, "HST") or g(x, "FTAG") > g(x, "AST") for x in rows),
    }
    if counts != EXPECTED_DQ_COUNTS:
        r.fail(f"Conteos {counts} != registro de calidad {EXPECTED_DQ_COUNTS}")
    r.info.append(f"Conteos recalculados sobre INTERIM: {counts}")
    return r


def check_duplicates(header: list[str], rows: list[list[str]]) -> CheckResult:
    r = CheckResult("A09", "Sin filas duplicadas por el proceso")
    off = len(settings.TRACE_COLUMNS)
    payload = Counter(tuple(row[off:]) for row in rows)
    d1 = sum(c - 1 for c in payload.values() if c > 1)
    if d1:
        r.fail(f"{d1} filas con las 162 columnas RAW idénticas a otra")
    k = [header.index(c) for c in ("season", "Date", "HomeTeam", "AwayTeam")]
    natural = Counter(tuple(row[i] for i in k) for row in rows)
    d2 = [x for x, c in natural.items() if c > 1]
    if d2:
        r.fail(f"Claves (season, Date, HomeTeam, AwayTeam) repetidas: {d2[:5]}")
    return r


def check_typing(header: list[str], rows: list[list[str]], schema: InterimSchema) -> CheckResult:
    r = CheckResult("A10", "Tipado y serialización estable de cada celda")
    patterns = {
        S.DATE: re.compile(r"\d{4}-\d{2}-\d{2}"), S.TIME: re.compile(r"([01]\d|2[0-3]):[0-5]\d"),
        S.INT: re.compile(r"-?(0|[1-9]\d*)"), S.CATEGORICAL: re.compile(r"[HDA]"),
    }
    for i, row in enumerate(rows, start=1):
        for col, v in zip(header, row):
            t = schema.type_of(col)
            if v == "":
                if col in settings.TRACE_COLUMNS:
                    r.fail(f"Fila {i}: {col} vacío")
                continue
            if t in patterns and not patterns[t].fullmatch(v):
                r.fail(f"Fila {i} {col}: {v!r} no cumple el formato {t}")
            elif t == S.DATE:
                datetime.strptime(v, settings.ISO_DATE_FORMAT)
            elif t == S.FLOAT:
                x = float(v)
                if not math.isfinite(x) or repr(x) != v:
                    r.fail(f"Fila {i} {col}: {v!r} no es la representación estable del float")
            elif t == S.STRING and v != v.strip():
                r.fail(f"Fila {i} {col}: espacios sobrantes")
    return r


def check_determinism(data: bytes, rebuild: Callable[[], bytes]) -> CheckResult:
    r = CheckResult("A11", "Determinismo e idempotencia byte a byte")
    if rebuild() != data:
        r.fail("Una segunda construcción desde RAW no produce bytes idénticos")
    header, rows = parse_interim(data)
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(header)
    w.writerows(rows)
    if buf.getvalue().encode("utf-8") != data:
        r.fail("Leer y reserializar INTERIM no reproduce el archivo")
    return r


def run_interim_checks(data: bytes, schema: InterimSchema, raw_paths: list[Path],
                       manifest_rows: dict[str, int], rebuild: Callable[[], bytes] | None
                       ) -> tuple[list[CheckResult], list]:
    results = [check_file_format(data)]
    if not results[0].passed:
        return results, []
    raw = IndependentRaw(raw_paths)
    header, rows = parse_interim(data)
    results += [check_schema(header, schema, raw)]
    if not results[-1].passed:
        return results, []
    results += [check_counts(header, rows, raw, manifest_rows),
                check_traceability(header, rows, raw)]
    if not results[-1].passed:
        return results, []
    fidelity, changed = check_cell_fidelity(header, rows, schema, raw)
    results += [fidelity, check_surface_cleaning(changed), check_nulls(header, rows, schema, raw),
                check_anomalies_preserved(header, rows), check_duplicates(header, rows),
                check_typing(header, rows, schema)]
    if rebuild is not None:
        results.append(check_determinism(data, rebuild))
    return results, changed
