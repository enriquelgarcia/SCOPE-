"""Validaciones V11, V12, V13, V16 y V17 de FEATURES (validation_spec_v0.1 §2).

FEATURES y CANONICAL se leen como texto desde los bytes generados; los valores se
parsean aquí. Solo se comparten las constantes del contrato (esquema 5.4 y settings).
"""
from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter, defaultdict

from src.config import settings
from src.data import features_schema as FS
from src.data.build_interim import serialize_csv
from src.validation.results import CheckResult

_INT = re.compile(r"-?(0|[1-9]\d*)")
_DT = re.compile(r"\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d:00")


def read_csv(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    recs = list(csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))
    return recs[0], [dict(zip(recs[0], r)) for r in recs[1:]]


def schema_guard(r: CheckResult, header) -> bool:
    """Las pruebas que leen columnas por nombre declaran FAIL (no excepción) si el esquema es inválido."""
    if list(header) != list(FS.FEATURES_COLUMNS):
        r.fail("Esquema FEATURES inválido (columnas faltantes/extra/desordenadas; ver V17): prueba no evaluable")
        return False
    return True


def fnum(v: str) -> float | None:
    return None if v == "" else float(v)


class FeaturesContext:
    def __init__(self, features: bytes, canonical: bytes):
        self.data = features
        self.header, self.rows = read_csv(features)
        self.ragged = sum(1 for _ in [])
        _, self.canonical = read_csv(canonical)
        self.can_by_id = {m["match_id"]: m for m in self.canonical}
        recs = list(csv.reader(io.StringIO(features.decode("utf-8"), newline="")))
        self.ragged = sum(1 for r in recs[1:] if len(r) != len(recs[0]))


# ------------------------------------------------------------------ V11
def check_v11(ctx: FeaturesContext) -> CheckResult:
    r = CheckResult("V11", "Integridad referencial FEATURES ↔ CANONICAL")
    ids = Counter(x.get("match_id") for x in ctx.rows)
    if len(ctx.rows) != len(ctx.canonical):
        r.fail(f"{len(ctx.rows)} filas != {len(ctx.canonical)} de CANONICAL")
    if any(n > 1 for n in ids.values()):
        r.fail(f"match_id repetidos: {[k for k, n in ids.items() if n > 1][:5]}")
    extra, missing = set(ids) - set(ctx.can_by_id), set(ctx.can_by_id) - set(ids)
    if extra or missing:
        r.fail(f"match_id extra: {len(extra)}; faltantes: {len(missing)}")
    for x in ctx.rows:
        m = ctx.can_by_id.get(x.get("match_id"))
        if m and (x.get("result") != m["result"] or x.get("goal_difference") != m["goal_difference"]):
            r.fail(f"{x['match_id']}: result/goal_difference distintos de CANONICAL")
    return r


def _team_sequences(ctx: FeaturesContext):
    """(season, team_id) -> [(kickoff, n_prev, rates...)] en orden de kickoff (desde CANONICAL)."""
    seq = defaultdict(list)
    for x in ctx.rows:
        m = ctx.can_by_id.get(x["match_id"])
        if m is None:
            continue
        for p, side in (("h", "home"), ("a", "away")):
            seq[(m["season"], m[f"{side}_team_id"])].append(
                (m["kickoff_datetime"], x[f"{p}_n_prev_season"], [x[f"{p}_{k}"] for k in FS.RATE_METRICS]))
    return seq


# ------------------------------------------------------------------ V12
def check_v12(ctx: FeaturesContext) -> CheckResult:
    r = CheckResult("V12", "Reinicio de temporada: n_prev_season 0,1,…,37 por equipo-temporada; vacíos si 0")
    if not schema_guard(r, ctx.header):
        return r
    seq = _team_sequences(ctx)
    for key, items in sorted(seq.items()):
        items.sort(key=lambda t: t[0])
        ns = [t[1] for t in items]
        if ns != [str(i) for i in range(len(items))]:
            r.fail(f"{key}: n_prev_season {ns[:6]}… no es 0,1,2,… en orden de kickoff")
        if len(items) and int(ns[-1] or -1) > 37:
            r.fail(f"{key}: máximo {ns[-1]} > 37")
        for ko, n, rates in items:
            if n == "0" and any(v != "" for v in rates):
                r.fail(f"{key} {ko}: n_prev_season = 0 con métricas no vacías")
            if n not in ("", "0") and any(v == "" for v in rates):
                r.fail(f"{key} {ko}: métrica vacía con n_prev_season = {n}")
    r.info.append(f"Equipo-temporadas: {len(seq)}; partidos por equipo-temporada: "
                  f"{sorted(Counter(len(v) for v in seq.values()).items())}")
    return r


# ------------------------------------------------------------------ V13
def check_v13(ctx: FeaturesContext, threshold: int = settings.ELIGIBILITY_THRESHOLD) -> CheckResult:
    r = CheckResult("V13", f"Elegibilidad: min(h_n, a_n) ≥ {threshold}; elegibles sin vacíos; conteos")
    if not schema_guard(r, ctx.header):
        return r
    per = Counter()
    for x in ctx.rows:
        try:
            exp = min(int(x["h_n_prev_season"]), int(x["a_n_prev_season"])) >= threshold
        except ValueError:
            r.fail(f"{x.get('match_id')}: n_prev_season no entero")
            continue
        got = x["is_modeling_eligible"]
        if got != ("true" if exp else "false"):
            r.fail(f"{x['match_id']}: is_modeling_eligible {got!r} != {exp}")
        if got == "true":
            per[x["season"]] += 1
            empty = [c for c in FS.NUMERIC_FEATURES if x[c] == ""]
            if empty:
                r.fail(f"{x['match_id']}: elegible con vacíos en {empty[:3]}")
    if threshold == settings.ELIGIBILITY_THRESHOLD and dict(per) != settings.EXPECTED_ELIGIBLE:
        r.fail(f"Elegibles por temporada {dict(sorted(per.items()))} != {settings.EXPECTED_ELIGIBLE}")
    r.info.append(f"Elegibles por temporada: {dict(sorted(per.items()))}; total {sum(per.values())}")
    return r


# ------------------------------------------------------------------ V16
def check_v16(ctx: FeaturesContext) -> CheckResult:
    r = CheckResult("V16", "diff_x == h_x − a_x (vacío si algún lado vacío); feature_version = '0.1'")
    if not schema_guard(r, ctx.header):
        return r
    exact = 0
    for x in ctx.rows:
        for m in FS.DIFF_METRICS:
            h, a, d = fnum(x[f"h_{m}"]), fnum(x[f"a_{m}"]), fnum(x[f"diff_{m}"])
            if h is None or a is None:
                if d is not None:
                    r.fail(f"{x['match_id']} diff_{m}: debería estar vacío")
            elif d is None or d != h - a:
                r.fail(f"{x['match_id']} diff_{m} = {x[f'diff_{m}']!r} != {h!r} − {a!r}")
            else:
                exact += 1
        if x["feature_version"] != settings.FEATURE_VERSION:
            r.fail(f"{x['match_id']}: feature_version {x['feature_version']!r}")
    r.info.append(f"Diferencias no vacías verificadas con igualdad exacta del double: {exact}")
    return r


# ------------------------------------------------------------------ V17
def check_v17(ctx: FeaturesContext) -> CheckResult:
    r = CheckResult("V17", "FEATURES: esquema normativo (5.4), serialización (4.0, D43) e idempotencia")
    d = ctx.data
    if d.startswith(b"\xef\xbb\xbf") or b"\r" in d or not d.endswith(b"\n"):
        r.fail("Se exige UTF-8 sin BOM y LF (incluida la última línea)")
    if ctx.header != list(FS.FEATURES_COLUMNS):
        r.fail(f"Cabecera distinta de las 30 columnas de 5.4 (recibidas {len(ctx.header)})")
        return r
    if ctx.ragged:
        r.fail(f"{ctx.ragged} filas con número de campos distinto de 30")
        return r
    for i, x in enumerate(ctx.rows, start=1):
        for s in FS.FEATURES_SCHEMA:
            v = x[s.name]
            where = f"fila {i} {s.name}={v!r}"
            if v in settings.NULL_LITERALS:
                r.fail(f"{where}: literal nulo")
            elif v == "":
                if not s.nullable:
                    r.fail(f"{where}: vacío en columna no nula")
            elif s.logical_type == "int" and not _INT.fullmatch(v):
                r.fail(f"{where}: entero inválido")
            elif s.logical_type == "float":
                try:
                    f = float(v)
                    ok = math.isfinite(f) and repr(f) == v and (not f.is_integer() or "." in v or "e" in v)
                except ValueError:
                    ok = False
                if not ok:
                    r.fail(f"{where}: float no serializado como repr sin redondeo (4.0, D43)")
            elif s.logical_type == "datetime" and not _DT.fullmatch(v):
                r.fail(f"{where}: datetime inválido")
            elif s.logical_type == "categorical" and v not in ("H", "D", "A"):
                r.fail(f"{where}: categoría inválida")
            elif s.logical_type == FS.BOOL and v not in ("true", "false"):
                r.fail(f"{where}: booleano inválido")
        if not r.passed:
            continue
        for p in ("h", "a"):
            n = int(x[f"{p}_n_prev_season"])
            if not 0 <= n <= 37:
                r.fail(f"fila {i}: {p}_n_prev_season {n} fuera de 0–37")
            for m in FS.RATE_METRICS:
                v = fnum(x[f"{p}_{m}"])
                if (v is None) != (n == 0):
                    r.fail(f"fila {i} {p}_{m}: vacío solo si n_prev_season = 0")
                elif v is not None and (v < 0 or (m.startswith("ppg") and v > 3)):
                    r.fail(f"fila {i} {p}_{m} = {v} fuera de dominio")
        if x["feature_version"] != "0.1":
            r.fail(f"fila {i}: feature_version {x['feature_version']!r}")
        if not re.fullmatch(r"\d{4}-\d{4}", x["season"]):
            r.fail(f"fila {i}: season inválida")
    can_order = [m["match_id"] for m in ctx.canonical]
    if [x["match_id"] for x in ctx.rows] != can_order:
        r.fail("Las filas no están en el mismo orden que CANONICAL (kickoff_datetime, match_id)")
    for x in ctx.rows:
        m = ctx.can_by_id.get(x["match_id"])
        if m and (x["season"], x["kickoff_datetime"]) != (m["season"], m["kickoff_datetime"]):
            r.fail(f"{x['match_id']}: season/kickoff_datetime distintos de CANONICAL")
    if r.passed:
        typed = [[FS.parse_value(x[s.name], s.logical_type, s.nullable) for s in FS.FEATURES_SCHEMA]
                 for x in ctx.rows]
        again = serialize_csv(FS.FEATURES_COLUMNS,
                              [tuple(FS.serialize_value(v, s.logical_type) for v, s in zip(t, FS.FEATURES_SCHEMA))
                               for t in typed])
        if again != d:
            r.fail("Idempotencia: leer con dtypes (feature_version string) y reserializar no reproduce el archivo")
    sci = sum(1 for x in ctx.rows for c in FS.NUMERIC_FEATURES if "e" in x[c])
    r.info.append(f"{len(ctx.rows)} filas × {len(ctx.header)} columnas; valores en notación científica: {sci}")
    return r
