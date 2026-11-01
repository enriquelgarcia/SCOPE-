"""CANONICAL -> team_match_log (contrato §2, §3; T6).

Artefacto auxiliar: dos filas por partido (perspectiva local y visitante), derivadas solo
de CANONICAL. Orden del archivo: (`team_id`, `kickoff_datetime`) — "ordenado por equipo y
kickoff_datetime" (§2). Es disposición física, no frontera temporal (T5).
"""
from __future__ import annotations

from src.data.build_interim import serialize_csv
from src.data.features_schema import BOOL_SERIALIZATION, serialize_value

TML_SCHEMA: tuple[tuple[str, str], ...] = (
    ("match_id", "string"), ("season", "string"), ("kickoff_datetime", "datetime"),
    ("team_id", "string"), ("opponent_team_id", "string"), ("is_home", "bool"),
    ("goals_for", "int"), ("goals_against", "int"), ("points", "int"), ("shots_on_target_for", "int"),
)
TML_COLUMNS = tuple(c for c, _ in TML_SCHEMA)


def points_for(goals_for: int, goals_against: int) -> int:
    """3 / 1 / 0 desde la perspectiva del equipo (§5)."""
    if goals_for > goals_against:
        return 3
    if goals_for == goals_against:
        return 1
    return 0


def perspective(match: dict, is_home: bool) -> dict:
    side, other = ("home", "away") if is_home else ("away", "home")
    gf, ga = match[f"{side}_goals"], match[f"{other}_goals"]
    return {
        "match_id": match["match_id"], "season": match["season"],
        "kickoff_datetime": match["kickoff_datetime"],
        "team_id": match[f"{side}_team_id"], "opponent_team_id": match[f"{other}_team_id"],
        "is_home": is_home, "goals_for": gf, "goals_against": ga, "points": points_for(gf, ga),
        "shots_on_target_for": match[f"{side}_shots_on_target"],
    }


def build_team_match_log(canonical: list[dict]) -> list[dict]:
    rows = [perspective(m, h) for m in canonical for h in (True, False)]
    rows.sort(key=lambda r: (r["team_id"], r["kickoff_datetime"], r["match_id"]))
    return rows


def serialize_team_match_log(rows: list[dict]) -> bytes:
    def ser(v, t):
        return BOOL_SERIALIZATION[v] if t == "bool" else serialize_value(v, t)
    return serialize_csv(TML_COLUMNS, [tuple(ser(r[c], t) for c, t in TML_SCHEMA) for r in rows])
