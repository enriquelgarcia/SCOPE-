"""team_match_log -> FEATURES v0.1 (contrato §5, T1–T10).

Algoritmo (T6): partición por (season, team_id), orden por kickoff_datetime y, para el
partido i de la partición, historia = partidos 0..i-1 (equivalente a `shift(1)`).
- S (season) = toda la historia previa de la temporada (T1, T3);
- L5 = los min(5, n_prev_season) partidos más recientes de S;
- n_prev_season = 0 -> métricas de tasa/ventana None (no se imputan).
Reconstrucción a una fila por partido por `match_id`, usando `is_home` explícitamente.
Las cuotas y las estadísticas del propio partido no se leen en ningún momento (T4, T7).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from src.config import settings
from src.data.build_interim import serialize_csv
from src.data.features_schema import (DIFF_METRICS, FEATURES_COLUMNS, FEATURES_SCHEMA, RATE_METRICS,
                                      serialize_value)
from src.data.team_match_log import build_team_match_log, serialize_team_match_log


class TemporalHypothesisViolation(RuntimeError):
    """Un equipo con dos partidos en el mismo kickoff_datetime (hipótesis 6.1)."""


# --- piezas pequeñas (sustituibles en las autopruebas para simular defectos) ---
def partition_key(entry: dict) -> tuple:
    return (entry["season"], entry["team_id"])            # reinicio por temporada (T3)


def history_before(entries: list[dict], i: int) -> list[dict]:
    return entries[:i]                                   # shift(1): solo partidos anteriores


def last_window(history: list[dict], n: int = settings.LAST_N) -> list[dict]:
    return history[-n:] if n > 0 else []                 # los n más recientes


def _mean(values: list[int]) -> float | None:
    return sum(values) / len(values) if values else None


def team_features(history: list[dict]) -> dict:
    n = len(history)
    w = last_window(history)
    return {
        "n_prev_season": n,
        "ppg_season": _mean([e["points"] for e in history]),
        "gf_pg_season": _mean([e["goals_for"] for e in history]),
        "ga_pg_season": _mean([e["goals_against"] for e in history]),
        "ppg_last5": _mean([e["points"] for e in w]),
        "gf_pg_last5": _mean([e["goals_for"] for e in w]),
        "ga_pg_last5": _mean([e["goals_against"] for e in w]),
        "sot_pg_last5": _mean([e["shots_on_target_for"] for e in w]),
    }


def compute_team_features(tml: list[dict]) -> dict[tuple[str, bool], dict]:
    """(match_id, is_home) -> features del equipo antes de ese partido."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in tml:
        groups[partition_key(e)].append(e)
    out: dict[tuple[str, bool], dict] = {}
    for key in sorted(groups):
        entries = sorted(groups[key], key=lambda e: e["kickoff_datetime"])
        kos = [e["kickoff_datetime"] for e in entries]
        if len(set(kos)) != len(kos):
            raise TemporalHypothesisViolation(f"{key}: partidos con el mismo kickoff_datetime")
        for i, e in enumerate(entries):
            out[(e["match_id"], e["is_home"])] = team_features(history_before(entries, i))
    return out


def _diff(h, a):
    return None if h is None or a is None else h - a


def assemble_features(canonical: list[dict], team_feats: dict[tuple[str, bool], dict]) -> list[dict]:
    rows = []
    for m in canonical:
        h, a = team_feats[(m["match_id"], True)], team_feats[(m["match_id"], False)]
        row = {"match_id": m["match_id"], "season": m["season"], "kickoff_datetime": m["kickoff_datetime"]}
        row.update({f"h_{k}": v for k, v in h.items()})
        row.update({f"a_{k}": v for k, v in a.items()})
        row.update({f"diff_{x}": _diff(h[x], a[x]) for x in DIFF_METRICS})
        row["result"] = m["result"]                       # labels copiados de CANONICAL
        row["goal_difference"] = m["goal_difference"]
        row["is_modeling_eligible"] = min(h["n_prev_season"], a["n_prev_season"]) >= settings.ELIGIBILITY_THRESHOLD
        row["feature_version"] = settings.FEATURE_VERSION
        rows.append(row)
    rows.sort(key=lambda r: (r["kickoff_datetime"], r["match_id"]))   # mismo orden que CANONICAL
    assert set(RATE_METRICS) <= set(h) and len(rows[0]) == len(FEATURES_COLUMNS)
    return rows


def build_features(canonical: list[dict]) -> tuple[list[dict], list[dict]]:
    tml = build_team_match_log(canonical)
    return tml, assemble_features(canonical, compute_team_features(tml))


def serialize_features(rows: list[dict]) -> bytes:
    return serialize_csv(FEATURES_COLUMNS,
                         [tuple(serialize_value(r[c.name], c.logical_type) for c in FEATURES_SCHEMA) for r in rows])


def build_all_bytes(canonical: list[dict]) -> tuple[bytes, bytes]:
    tml, feats = build_features(canonical)
    return serialize_team_match_log(tml), serialize_features(feats)


def write_output(data: bytes, path) -> None:
    settings.assert_writable_output(path)
    protected = {settings.INTERIM_FILE.resolve(), settings.CANONICAL_FILE.resolve()}
    if path.resolve() in protected:
        raise PermissionError(f"CHECKPOINT C no puede sobrescribir {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
