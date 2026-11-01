"""Validaciones V02–V10 de CANONICAL (validation_spec_v0.1 §2).

Independencia respecto del builder:
- CANONICAL se lee desde los bytes del archivo generado;
- RAW se vuelve a leer con `IndependentRaw` (csv.DictReader + utf-8-sig) y la fecha RAW
  se re-parsea con %d/%m/%Y solo en V03/V06, como exige la especificación;
- `team_mapping_v0.1.csv` se lee aquí directamente con csv, sin `TeamMapping`;
- los `dq_flags` esperados se recalculan con código propio.
Solo se comparten las constantes del contrato (esquema 4.9 y settings).
"""
from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time
from pathlib import Path

from src.config import settings
from src.data import canonical_schema as CS
from src.validation.interim_checks import IndependentRaw
from src.validation.results import CheckResult

# Registro de calidad §2.1–2.2 (source_file, source_row)
Q01 = ("PL_2021-2022_raw.csv", 9)
GOALS_GT_SOT_LOCATIONS = {
    ("PL_2021-2022_raw.csv", 15), ("PL_2021-2022_raw.csv", 79), ("PL_2021-2022_raw.csv", 205),
    ("PL_2022-2023_raw.csv", 106), ("PL_2022-2023_raw.csv", 319),
    ("PL_2023-2024_raw.csv", 66), ("PL_2023-2024_raw.csv", 91), ("PL_2023-2024_raw.csv", 329),
    ("PL_2024-2025_raw.csv", 123), ("PL_2024-2025_raw.csv", 139),
    ("PL_2025-2026_raw.csv", 132), ("PL_2025-2026_raw.csv", 208),
}
EXPECTED_DQ_COUNTS = {"HST_GT_HS": 0, "AST_GT_AS": 1, "GOALS_GT_SOT": 12}

NON_NEGATIVE_INT = [c.name for c in CS.CANONICAL_SCHEMA if c.logical_type == CS.INT
                    and c.name not in ("goal_difference", "source_row", "match_seq_season")]
MKT = [c for c in CS.CANONICAL_COLUMNS if c.startswith("mkt_")]

_RX = {
    CS.INT: re.compile(r"-?(0|[1-9]\d*)"),
    CS.DATE: re.compile(r"\d{4}-\d{2}-\d{2}"),
    CS.TIME: re.compile(r"([01]\d|2[0-3]):[0-5]\d"),
    CS.DATETIME: re.compile(r"\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d:00"),
    CS.CATEGORICAL: re.compile(r"[HDA]"),
}
_FLOAT_RX = re.compile(r"-?\d+\.\d+")          # D43: parte decimal explícita
_SEASON_RX = re.compile(r"(\d{4})-(\d{4})")
_TEAM_RX = re.compile(r"[a-z0-9_]+")
_MATCH_ID_RX = re.compile(r"EPL_\d{4}-\d{4}_\d{8}_[a-z0-9_]+_[a-z0-9_]+")


# ------------------------------------------------------------------ contexto
class CanonicalContext:
    def __init__(self, data: bytes, raw_paths: list[Path], mapping_path: Path, raw_file_names: set[str]):
        self.data = data
        self.raw = IndependentRaw(raw_paths)
        self.raw_file_names = raw_file_names
        with open(mapping_path, encoding="utf-8-sig", newline="") as fh:
            self.mapping_rows = list(csv.DictReader(fh))
        self.header: list[str] = []
        self.rows: list[dict[str, str]] = []
        self.parse_error: str | None = None
        try:
            recs = list(csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))
            self.header = recs[0]
            self.rows = [dict(zip(self.header, r)) for r in recs[1:] if len(r) == len(self.header)]
            self.ragged = sum(1 for r in recs[1:] if len(r) != len(self.header))
        except Exception as exc:                      # noqa: BLE001 - se informa como FAIL
            self.parse_error = str(exc)

    def raw_row(self, row: dict[str, str]) -> dict[str, str] | None:
        f = self.raw.files.get(row.get("source_file", ""))
        try:
            sr = int(row.get("source_row", ""))
        except ValueError:
            return None
        if f is None or not 1 <= sr <= len(f[2]):
            return None
        return f[2][sr - 1]

    def alias_lookup(self, source: str, alias: str):
        hits = [m for m in self.mapping_rows if m["source"] == source and m["source_name"] == alias]
        return hits[0] if len(hits) == 1 else None


def _sign(x: int) -> str:
    return "H" if x > 0 else "A" if x < 0 else "D"


def _key(r):
    return (r["source_file"], r["source_row"])


# ------------------------------------------------------------------ V02
def check_v02(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V02", "CANONICAL: esquema normativo (4.9), serialización (4.0) e idempotencia")
    d = ctx.data
    if d.startswith(b"\xef\xbb\xbf"):
        r.fail("BOM al inicio")
    if b"\r" in d:
        r.fail("Contiene CR (se exige LF)")
    if not d.endswith(b"\n"):
        r.fail("Falta LF final")
    if ctx.parse_error:
        r.fail(f"CSV ilegible: {ctx.parse_error}")
        return r
    if ctx.header != list(CS.CANONICAL_COLUMNS):
        r.fail(f"Cabecera distinta de las 42 columnas de 4.9 (recibidas {len(ctx.header)})")
        return r
    if ctx.ragged:
        r.fail(f"{ctx.ragged} filas con número de campos distinto de 42")
    for i, row in enumerate(ctx.rows, start=1):
        for spec in CS.CANONICAL_SCHEMA:
            v = row[spec.name]
            where = f"fila {i} {spec.name}={v!r}"
            if v in settings.NULL_LITERALS:
                r.fail(f"{where}: literal nulo")
                continue
            if v == "":
                if not spec.nullable:
                    r.fail(f"{where}: vacío en columna no nula")
                continue
            t = spec.logical_type
            if t in _RX and not _RX[t].fullmatch(v):
                r.fail(f"{where}: no cumple el formato {t}")
                continue
            try:
                if t == CS.DATE:
                    date.fromisoformat(v)
                elif t == CS.DATETIME:
                    datetime.fromisoformat(v)
                elif t == CS.FLOAT:
                    x = float(v)
                    if not _FLOAT_RX.fullmatch(v) or repr(x) != v or not math.isfinite(x):
                        r.fail(f"{where}: float no serializado como repr sin redondeo con decimal explícito (D43)")
                elif t == CS.STRING and (v != v.strip() or "\n" in v):
                    r.fail(f"{where}: espacios o saltos de línea")
            except ValueError:
                r.fail(f"{where}: valor inválido para {t}")
        # dominios de 4.9
        m = _SEASON_RX.fullmatch(row["season"])
        if not m or int(m.group(2)) != int(m.group(1)) + 1:
            r.fail(f"fila {i}: season {row['season']!r}")
        if not _MATCH_ID_RX.fullmatch(row["match_id"]):
            r.fail(f"fila {i}: match_id con formato inválido")
        if row["competition_code"] != "EPL" or row["source_div"] != "E0":
            r.fail(f"fila {i}: competition_code/source_div fuera de dominio")
        if row["source_name"] != settings.SOURCE_NAME:
            r.fail(f"fila {i}: source_name {row['source_name']!r}")
        if row["source_file"] not in ctx.raw_file_names:
            r.fail(f"fila {i}: source_file no es raw_data del manifiesto")
        for c in ("source_row", "match_seq_season"):
            if _RX[CS.INT].fullmatch(row[c]) and not 1 <= int(row[c]) <= settings.ROWS_PER_SEASON:
                r.fail(f"fila {i}: {c} fuera de 1–380")
        for c in ("home_team_id", "away_team_id"):
            if not _TEAM_RX.fullmatch(row[c]):
                r.fail(f"fila {i}: {c} inválido")
        f = row["dq_flags"]
        if f:
            codes = f.split("|")
            if (len(set(codes)) != len(codes) or any(c not in settings.DQ_FLAG_CATALOG for c in codes)
                    or codes != sorted(codes, key=settings.DQ_FLAG_CATALOG.index)):
                r.fail(f"fila {i}: dq_flags fuera de catálogo/orden: {f!r}")
    if not r.passed:
        return r
    keys = [(row["kickoff_datetime"], row["match_id"]) for row in ctx.rows]
    if keys != sorted(keys):
        r.fail("Filas no ordenadas por (kickoff_datetime, match_id)")
    # idempotencia: leer con dtypes del esquema y reserializar
    from src.data.build_interim import serialize_csv
    typed = [[CS.parse_value(row[s.name], s.logical_type, s.nullable) for s in CS.CANONICAL_SCHEMA]
             for row in ctx.rows]
    again = serialize_csv(CS.CANONICAL_COLUMNS,
                          [tuple(CS.serialize_value(v, s.logical_type) for v, s in zip(t, CS.CANONICAL_SCHEMA))
                           for t in typed])
    if again != d:
        r.fail("Idempotencia: leer con tipos del esquema y reserializar no reproduce el archivo")
    r.info.append(f"{len(ctx.rows)} filas × {len(ctx.header)} columnas")
    return r


# ------------------------------------------------------------------ V03
def check_v03(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V03", "Trazabilidad completa: comparación campo por campo con RAW re-leído")
    keys = []
    for i, row in enumerate(ctx.rows, start=1):
        raw = ctx.raw_row(row)
        if raw is None:
            r.fail(f"fila {i}: ({row.get('source_file')}, {row.get('source_row')}) no existe en RAW")
            continue
        keys.append(_key(row))
        season = ctx.raw.files[row["source_file"]][0]
        where = f"{row['source_file']}:{row['source_row']}"
        exp: dict[str, object] = {
            "season": season, "source_div": raw["Div"],
            "competition_code": settings.COMPETITION_CODE_MAP.get(raw["Div"]),
            "referee": raw["Referee"].strip(),
            "result": raw["FTR"], "ht_result": raw["HTR"],
        }
        try:
            exp["match_date"] = datetime.strptime(raw["Date"], settings.RAW_DATE_FORMAT).date().isoformat()
            exp["kickoff_time"] = datetime.strptime(raw["Time"], settings.RAW_TIME_FORMAT).strftime("%H:%M")
        except ValueError:
            r.fail(f"{where}: Date/Time RAW no parsean de forma estricta")
        for side, col in (("home", "HomeTeam"), ("away", "AwayTeam")):
            m = ctx.alias_lookup(row["source_name"], raw[col])
            exp[f"{side}_team_id"] = m["team_id"] if m else None
            exp[f"{side}_team_name"] = m["display_name"] if m else None
        for c, v in exp.items():
            if row.get(c) != v:
                r.fail(f"{where} {c}: CANONICAL={row.get(c)!r} esperado={v!r}")
        for c, raw_col in CS.RAW_SOURCE.items():
            t = CS.TYPE_OF[c]
            if t == CS.INT:
                ok = _RX[CS.INT].fullmatch(row[c]) and raw[raw_col] != "" and int(row[c]) == int(raw[raw_col])
            elif t == CS.FLOAT:
                try:
                    ok = float(row[c]) == float(raw[raw_col])          # igualdad exacta del double
                except ValueError:
                    ok = False
            else:
                ok = True                                            # strings ya comparados arriba
            if not ok:
                r.fail(f"{where} {c}: CANONICAL={row[c]!r} RAW {raw_col}={raw[raw_col]!r}")
    dup = [k for k, n in Counter(keys).items() if n > 1]
    if dup:
        r.fail(f"(source_file, source_row) repetidos: {dup[:5]}")
    expected = {(f, str(n)) for f, (_, _, rr) in ctx.raw.files.items() for n in range(1, len(rr) + 1)}
    if set(keys) != expected:
        r.fail(f"Filas RAW omitidas: {len(expected - set(keys))}")
    r.info.append(f"Filas comparadas: {len(keys)}; campos por fila trasladados desde RAW: "
                  f"{len(CS.RAW_SOURCE) + 8}")
    return r


# ------------------------------------------------------------------ V04
def check_v04(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V04", "Unicidad de match_id y de la clave natural; regla de construcción")
    ids = Counter(row["match_id"] for row in ctx.rows)
    if any(n > 1 for n in ids.values()):
        r.fail(f"match_id repetidos: {[k for k, n in ids.items() if n > 1][:5]}")
    nat = Counter((row["competition_code"], row["season"], row["match_date"], row["home_team_id"],
                   row["away_team_id"]) for row in ctx.rows)
    if any(n > 1 for n in nat.values()):
        r.fail("Clave natural repetida")
    for row in ctx.rows:
        expected = (f"{row['competition_code']}_{row['season']}_{row['match_date'].replace('-', '')}_"
                    f"{row['home_team_id']}_{row['away_team_id']}")
        if row["match_id"] != expected:
            r.fail(f"match_id {row['match_id']!r} != regla {expected!r}")
    return r


# ------------------------------------------------------------------ V05
def check_v05(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V05", "Conteos y calendario (380/temporada, 20 equipos, 19+19, parejas únicas)")
    if len(ctx.rows) != settings.EXPECTED_SEASONS * settings.ROWS_PER_SEASON:
        r.fail(f"Total {len(ctx.rows)} filas")
    by = defaultdict(list)
    for row in ctx.rows:
        by[row["season"]].append(row)
    if len(by) != settings.EXPECTED_SEASONS:
        r.fail(f"Temporadas: {sorted(by)}")
    for season, rows in sorted(by.items()):
        teams = {x["home_team_id"] for x in rows} | {x["away_team_id"] for x in rows}
        home = Counter(x["home_team_id"] for x in rows)
        away = Counter(x["away_team_id"] for x in rows)
        pairs = Counter((x["home_team_id"], x["away_team_id"]) for x in rows)
        full = {(a, b) for a in teams for b in teams if a != b}
        if len(rows) != settings.ROWS_PER_SEASON:
            r.fail(f"{season}: {len(rows)} partidos")
        if len(teams) != settings.TEAMS_PER_SEASON:
            r.fail(f"{season}: {len(teams)} equipos")
        if any(home[t] != 19 or away[t] != 19 for t in teams):
            r.fail(f"{season}: algún equipo sin 19 partidos de local y 19 de visitante")
        if set(pairs) != full or any(n != 1 for n in pairs.values()):
            r.fail(f"{season}: parejas (local, visitante) no forman el producto completo sin diagonal "
                   f"(faltan {len(full - set(pairs))}, repetidas {sum(n - 1 for n in pairs.values())})")
        r.info.append(f"{season}: {len(rows)} partidos, {len(teams)} equipos, {len(pairs)} parejas")
    return r


# ------------------------------------------------------------------ V06
def check_v06(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V06", "Fechas y orden temporal (formato ISO, RAW estricto, ventana, seq, hipótesis 6.1)")
    by_season = defaultdict(list)
    for row in ctx.rows:
        where = f"{row['match_id']}"
        md, kt, kd = row["match_date"], row["kickoff_time"], row["kickoff_datetime"]
        try:
            d = date.fromisoformat(md) if _RX[CS.DATE].fullmatch(md) else None
        except ValueError:
            d = None
        if d is None:
            r.fail(f"{where}: match_date inválido {md!r}")
            continue
        if not _RX[CS.TIME].fullmatch(kt):
            r.fail(f"{where}: kickoff_time inválido {kt!r}")
        if not _RX[CS.DATETIME].fullmatch(kd) or kd != f"{md}T{kt}:00":
            r.fail(f"{where}: kickoff_datetime {kd!r} != match_date + T + kickoff_time + :00")
        raw = ctx.raw_row(row)
        if raw is not None:
            try:
                iso = datetime.strptime(raw["Date"], settings.RAW_DATE_FORMAT).date().isoformat()
                hhmm = datetime.strptime(raw["Time"], settings.RAW_TIME_FORMAT).strftime("%H:%M")
                if (iso, hhmm) != (md, kt):
                    r.fail(f"{where}: re-parseo estricto de RAW {raw['Date']} {raw['Time']} != {md} {kt}")
            except ValueError:
                r.fail(f"{where}: Date/Time RAW no cumplen %d/%m/%Y / %H:%M")
        m = _SEASON_RX.fullmatch(row["season"])
        if m and not date(int(m.group(1)), 8, 1) <= d <= date(int(m.group(2)), 6, 30):
            r.fail(f"{where}: {md} fuera de la ventana agosto–junio de {row['season']}")
        by_season[row["season"]].append(row)
    for season, rows in sorted(by_season.items()):
        seq = [int(x["match_seq_season"]) for x in rows]
        if sorted(seq) != list(range(1, len(rows) + 1)):
            r.fail(f"{season}: match_seq_season no es 1..{len(rows)} sin huecos ni repeticiones")
        expected = sorted(rows, key=lambda x: (x["kickoff_datetime"], x["match_id"]))
        if [int(x["match_seq_season"]) for x in expected] != list(range(1, len(rows) + 1)):
            r.fail(f"{season}: match_seq_season inconsistente con el orden (kickoff_datetime, match_id)")
        per_day, per_ko = Counter(), Counter()
        for x in rows:
            for t in (x["home_team_id"], x["away_team_id"]):
                per_day[(t, x["match_date"])] += 1
                per_ko[(t, x["kickoff_datetime"])] += 1
        bad = [k for k, n in per_day.items() if n > 1] + [k for k, n in per_ko.items() if n > 1]
        if bad:
            r.fail(f"{season}: equipo con dos partidos el mismo día / kickoff (hipótesis 6.1): {bad[:5]}")
        simult = sum(n for n in Counter(x["kickoff_datetime"] for x in rows).values() if n > 1)
        r.info.append(f"{season}: partidos con kickoff compartido con otro partido: {simult}")
    return r


# ------------------------------------------------------------------ V07
def check_v07(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V07", "Equipos: (fuente, alias RAW) -> team_id -> display_name exactos")
    frozen = {m["team_id"] for m in ctx.mapping_rows}
    if len(frozen) != settings.EXPECTED_TEAM_IDS:
        r.fail(f"team_mapping tiene {len(frozen)} team_id (congelados: {settings.EXPECTED_TEAM_IDS})")
    sources = {m["source"] for m in ctx.mapping_rows}
    used = set()
    for row in ctx.rows:
        where = row["match_id"]
        if row["source_name"] not in sources:
            r.fail(f"{where}: CANONICAL.source_name {row['source_name']!r} no es un team_mapping.source")
        raw = ctx.raw_row(row)
        if raw is None:
            r.fail(f"{where}: sin fila RAW (ver V03)")
            continue
        for side, col in (("home", "HomeTeam"), ("away", "AwayTeam")):
            m = ctx.alias_lookup(row["source_name"], raw[col])
            if m is None:
                r.fail(f"{where}: alias RAW {raw[col]!r} sin mapeo único")
                continue
            if row[f"{side}_team_id"] != m["team_id"]:
                r.fail(f"{where}: {side}_team_id {row[f'{side}_team_id']!r} != team_id de {raw[col]!r} ({m['team_id']})")
            if row[f"{side}_team_name"] != m["display_name"]:
                r.fail(f"{where}: {side}_team_name {row[f'{side}_team_name']!r} != {m['display_name']!r}")
        if row["home_team_id"] == row["away_team_id"]:
            r.fail(f"{where}: local == visitante")
        used |= {row["home_team_id"], row["away_team_id"]}
    if used != frozen:
        r.fail(f"team_id usados ({len(used)}) != congelados ({len(frozen)}): "
               f"{sorted(used ^ frozen)[:5]}")
    r.info.append(f"team_id distintos en CANONICAL: {len(used)}")
    return r


# ------------------------------------------------------------------ V08
def check_v08(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V08", "Rangos: enteros ≥ 0, HT ≤ FT, cuotas > 1.0, ht_result coherente")
    for row in ctx.rows:
        where = row["match_id"]
        try:
            ints = {c: int(row[c]) for c in NON_NEGATIVE_INT}
            mkt = {c: float(row[c]) for c in MKT}
        except ValueError:
            r.fail(f"{where}: resultado/estadística/cuota nula o no numérica")
            continue
        for c, v in ints.items():
            if v < 0:
                r.fail(f"{where}: {c} = {v} < 0")
        if ints["ht_home_goals"] > ints["home_goals"] or ints["ht_away_goals"] > ints["away_goals"]:
            r.fail(f"{where}: goles al descanso > goles finales")
        for c, v in mkt.items():
            if not v > 1.0:
                r.fail(f"{where}: {c} = {v} ≤ 1.0")
        if row["ht_result"] != _sign(ints["ht_home_goals"] - ints["ht_away_goals"]):
            r.fail(f"{where}: ht_result {row['ht_result']} incoherente con los goles al descanso")
    return r


# ------------------------------------------------------------------ V09
def check_v09(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V09", "Targets: goal_difference = home − away; result = sign(goal_difference)")
    dist = Counter()
    for row in ctx.rows:
        try:
            hg, ag, gd = int(row["home_goals"]), int(row["away_goals"]), int(row["goal_difference"])
        except ValueError:
            r.fail(f"{row['match_id']}: goles no enteros")
            continue
        if gd != hg - ag:
            r.fail(f"{row['match_id']}: goal_difference {gd} != {hg} − {ag}")
        if row["result"] != _sign(hg - ag):
            r.fail(f"{row['match_id']}: result {row['result']} != sign({hg - ag})")
        dist[row["result"]] += 1
    r.info.append(f"Distribución de result: {dict(sorted(dist.items()))}")
    return r


# ------------------------------------------------------------------ V10
def _expected_flags(row: dict[str, str]) -> str:
    g = lambda c: int(row[c])
    out = []
    if g("home_shots_on_target") > g("home_shots"):
        out.append("HST_GT_HS")
    if g("away_shots_on_target") > g("away_shots"):
        out.append("AST_GT_AS")
    if g("home_goals") > g("home_shots_on_target") or g("away_goals") > g("away_shots_on_target"):
        out.append("GOALS_GT_SOT")
    return "|".join(out)


def check_v10(ctx: CanonicalContext) -> CheckResult:
    r = CheckResult("V10", "dq_flags: conjunto exacto por fila, catálogo, orden; conteos y localizaciones")
    counts = Counter()
    where_flag = defaultdict(set)
    for row in ctx.rows:
        try:
            exp = _expected_flags(row)
        except ValueError:
            r.fail(f"{row['match_id']}: estadísticas no enteras")
            continue
        got = row["dq_flags"]
        if got != exp:
            r.fail(f"{row['match_id']}: dq_flags {got!r} != esperado {exp!r}")
        for code in filter(None, got.split("|")):
            if code not in settings.DQ_FLAG_CATALOG:
                r.fail(f"{row['match_id']}: código fuera de catálogo {code!r}")
            counts[code] += 1
            where_flag[code].add(_key(row))
    full = {c: counts.get(c, 0) for c in settings.DQ_FLAG_CATALOG}
    if full != EXPECTED_DQ_COUNTS:
        r.fail(f"Conteos {full} != registro {EXPECTED_DQ_COUNTS}")
    if where_flag["AST_GT_AS"] != {(Q01[0], str(Q01[1]))}:
        r.fail(f"AST_GT_AS en {sorted(where_flag['AST_GT_AS'])}, se espera {Q01}")
    if where_flag["GOALS_GT_SOT"] != {(f, str(n)) for f, n in GOALS_GT_SOT_LOCATIONS}:
        r.fail("GOALS_GT_SOT no coincide con las localizaciones del registro de calidad §2.2")
    r.info.append(f"Conteos: {full}")
    return r


ALL_CHECKS = (check_v02, check_v03, check_v04, check_v05, check_v06, check_v07, check_v08, check_v09, check_v10)


def run_canonical_checks(ctx: CanonicalContext) -> list[CheckResult]:
    results = [check_v02(ctx)]
    if ctx.parse_error or ctx.header != list(CS.CANONICAL_COLUMNS):
        return results            # sin esquema válido el resto no es interpretable
    return results + [chk(ctx) for chk in ALL_CHECKS[1:]]
