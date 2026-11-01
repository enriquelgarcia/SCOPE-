"""INTERIM -> CANONICAL (CHECKPOINT B).

Una fila CANONICAL por fila INTERIM. Solo transformaciones documentadas en el contrato:
mapeos (`Div`, equipos), composición temporal, derivación de `goal_difference`,
`match_id`, `match_seq_season` y `dq_flags`. Ninguna anomalía se corrige.
Orden de filas: (`kickoff_datetime`, `match_id`) ascendente (D30).
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
from datetime import date, datetime, time
from pathlib import Path

from src.config import settings
from src.data.build_interim import serialize_csv
from src.data.canonical_schema import CANONICAL_COLUMNS, CANONICAL_SCHEMA, RAW_SOURCE, serialize_value
from src.data.team_mapping import TeamMapping

log = logging.getLogger(__name__)


class InterimMismatch(RuntimeError):
    pass


def read_approved_interim(path: Path = settings.INTERIM_FILE,
                          expected_sha256: str = settings.INTERIM_APPROVED_SHA256) -> list[dict[str, str]]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise InterimMismatch(f"INTERIM no coincide con el aprobado: {digest} != {expected_sha256}")
    return interim_rows_from_bytes(data)


def interim_rows_from_bytes(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""), strict=True))


def compute_dq_flags(r: dict) -> str | None:
    """Catálogo del registro de calidad §1, en orden de catálogo; None = sin avisos."""
    flags = []
    if r["home_shots_on_target"] > r["home_shots"]:
        flags.append("HST_GT_HS")
    if r["away_shots_on_target"] > r["away_shots"]:
        flags.append("AST_GT_AS")
    if r["home_goals"] > r["home_shots_on_target"] or r["away_goals"] > r["away_shots_on_target"]:
        flags.append("GOALS_GT_SOT")
    return "|".join(flags) if flags else None


def build_match_id(competition_code: str, season: str, match_date: date, home: str, away: str) -> str:
    return f"{competition_code}_{season}_{match_date.strftime('%Y%m%d')}_{home}_{away}"


def _required(row: dict[str, str], col: str) -> str:
    v = row[col]
    if v == "":
        raise ValueError(f"{row['source_file']}:{row['source_row']} {col} vacío")
    return v


def canonical_record(row: dict[str, str], mapping: TeamMapping) -> dict:
    div = _required(row, "Div")
    if div not in settings.COMPETITION_CODE_MAP:
        raise ValueError(f"Div desconocido: {div!r}")
    comp = settings.COMPETITION_CODE_MAP[div]
    match_date = date.fromisoformat(_required(row, "Date"))          # INTERIM ya en ISO (D24)
    ko_time = time.fromisoformat(_required(row, "Time"))
    home_id, home_name = mapping.resolve(row["source_name"], _required(row, "HomeTeam"))
    away_id, away_name = mapping.resolve(row["source_name"], _required(row, "AwayTeam"))
    rec = {
        "competition_code": comp, "season": row["season"], "source_name": row["source_name"],
        "source_file": row["source_file"], "source_row": int(row["source_row"]),
        "match_date": match_date, "kickoff_time": ko_time,
        "kickoff_datetime": datetime.combine(match_date, ko_time),
        "home_team_id": home_id, "away_team_id": away_id,
        "home_team_name": home_name, "away_team_name": away_name,
    }
    for col, raw_col in RAW_SOURCE.items():
        t = next(c.logical_type for c in CANONICAL_SCHEMA if c.name == col)
        v = _required(row, raw_col)
        rec[col] = int(v) if t == "int" else float(v) if t == "float" else v.strip()
    rec["goal_difference"] = rec["home_goals"] - rec["away_goals"]
    rec["match_id"] = build_match_id(comp, rec["season"], match_date, home_id, away_id)
    rec["dq_flags"] = compute_dq_flags(rec)
    return rec


def assign_match_seq_season(records: list[dict]) -> None:
    """Rango 1..n por temporada según (kickoff_datetime, match_id). Solo orden auxiliar (T5)."""
    by_season: dict[str, list[dict]] = {}
    for r in records:
        by_season.setdefault(r["season"], []).append(r)
    for rows in by_season.values():
        for i, r in enumerate(sorted(rows, key=lambda x: (x["kickoff_datetime"], x["match_id"])), start=1):
            r["match_seq_season"] = i


def build_canonical_records(interim_rows: list[dict[str, str]], mapping: TeamMapping) -> list[dict]:
    records = [canonical_record(r, mapping) for r in interim_rows]
    assign_match_seq_season(records)
    records.sort(key=lambda r: (r["kickoff_datetime"], r["match_id"]))
    return records


def serialize_canonical(records: list[dict]) -> bytes:
    rows = [tuple(serialize_value(r[c.name], c.logical_type) for c in CANONICAL_SCHEMA) for r in records]
    return serialize_csv(CANONICAL_COLUMNS, rows)


def write_canonical(data: bytes, path: Path = settings.CANONICAL_FILE) -> Path:
    settings.assert_writable_output(path)
    if path.resolve() == settings.INTERIM_FILE.resolve():
        raise PermissionError("CANONICAL no puede sobrescribir INTERIM")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    log.info("CANONICAL escrito: %s (%d bytes)", path, len(data))
    return path
