"""Comprobaciones internas de `team_match_log` (C01–C02; no son IDs del contrato).

Independencia: CANONICAL y team_match_log se leen como texto con csv; la perspectiva
esperada se recalcula aquí sin usar `src.data.team_match_log`.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict

from src.validation.results import CheckResult

EXPECTED_TML_HEADER = ["match_id", "season", "kickoff_datetime", "team_id", "opponent_team_id", "is_home",
                       "goals_for", "goals_against", "points", "shots_on_target_for"]


def _rows(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    recs = list(csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))
    return recs[0], [dict(zip(recs[0], r)) for r in recs[1:]]


def check_c01(tml: bytes, canonical_rows: int) -> CheckResult:
    r = CheckResult("C01", "team_match_log: formato, cabecera, 2 × partidos filas, orden (team_id, kickoff)")
    if tml.startswith(b"\xef\xbb\xbf") or b"\r" in tml or not tml.endswith(b"\n"):
        r.fail("Se exige UTF-8 sin BOM y LF")
    header, rows = _rows(tml)
    if header != EXPECTED_TML_HEADER:
        r.fail(f"Cabecera inesperada: {header}")
        return r
    if len(rows) != 2 * canonical_rows:
        r.fail(f"{len(rows)} filas != 2 × {canonical_rows}")
    keys = [(x["team_id"], x["kickoff_datetime"], x["match_id"]) for x in rows]
    if keys != sorted(keys):
        r.fail("Filas no ordenadas por (team_id, kickoff_datetime)")
    r.info.append(f"{len(rows)} filas × {len(header)} columnas")
    return r


def check_c02(tml: bytes, canonical: bytes) -> CheckResult:
    r = CheckResult("C02", "team_match_log: espejo local/visitante y valores derivados solo de CANONICAL")
    _, trows = _rows(tml)
    _, crows = _rows(canonical)
    by_match = defaultdict(list)
    for x in trows:
        by_match[x["match_id"]].append(x)
    if set(by_match) != {m["match_id"] for m in crows}:
        r.fail("Los match_id de team_match_log no coinciden con CANONICAL")
    pts_total = Counter()
    for m in crows:
        pair = by_match.get(m["match_id"], [])
        if len(pair) != 2 or sorted(x["is_home"] for x in pair) != ["false", "true"]:
            r.fail(f"{m['match_id']}: se esperan exactamente 2 filas (una local, una visitante)")
            continue
        home = next(x for x in pair if x["is_home"] == "true")
        away = next(x for x in pair if x["is_home"] == "false")
        hg, ag = int(m["home_goals"]), int(m["away_goals"])
        hp = 3 if hg > ag else 1 if hg == ag else 0
        ap = 3 if ag > hg else 1 if hg == ag else 0
        exp_home = {"season": m["season"], "kickoff_datetime": m["kickoff_datetime"],
                    "team_id": m["home_team_id"], "opponent_team_id": m["away_team_id"],
                    "goals_for": str(hg), "goals_against": str(ag), "points": str(hp),
                    "shots_on_target_for": m["home_shots_on_target"]}
        exp_away = {"season": m["season"], "kickoff_datetime": m["kickoff_datetime"],
                    "team_id": m["away_team_id"], "opponent_team_id": m["home_team_id"],
                    "goals_for": str(ag), "goals_against": str(hg), "points": str(ap),
                    "shots_on_target_for": m["away_shots_on_target"]}
        for got, exp, side in ((home, exp_home, "local"), (away, exp_away, "visitante")):
            for k, v in exp.items():
                if got[k] != v:
                    r.fail(f"{m['match_id']} ({side}) {k}: {got[k]!r} != {v!r}")
        if home["team_id"] == home["opponent_team_id"]:
            r.fail(f"{m['match_id']}: team_id == opponent_team_id")
        if (home["goals_for"], home["goals_against"]) != (away["goals_against"], away["goals_for"]):
            r.fail(f"{m['match_id']}: goles no espejados")
        total = int(home["points"]) + int(away["points"])
        if total not in (2, 3) or (total == 2) != (m["result"] == "D"):
            r.fail(f"{m['match_id']}: puntos {home['points']}+{away['points']} incoherentes con {m['result']}")
        pts_total[total] += 1
    r.info.append(f"Partidos con 3+0 puntos: {pts_total[3]}; con 1+1: {pts_total[2]}")
    return r
