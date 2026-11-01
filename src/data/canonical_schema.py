"""Esquema normativo de CANONICAL v0.1 (contrato §4.9) y serialización (§4.0, D43).

42 columnas, en orden. Todas no nulas salvo `dq_flags`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time

STRING, INT, FLOAT, DATE, TIME, DATETIME, CATEGORICAL = (
    "string", "int", "float", "date", "time", "datetime", "categorical")


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    logical_type: str
    nullable: bool = False


_SPEC = [
    ("match_id", STRING), ("competition_code", STRING), ("season", STRING),
    ("source_name", STRING), ("source_file", STRING), ("source_row", INT), ("source_div", STRING),
    ("match_date", DATE), ("kickoff_time", TIME), ("kickoff_datetime", DATETIME),
    ("match_seq_season", INT),
    ("home_team_id", STRING), ("away_team_id", STRING),
    ("home_team_name", STRING), ("away_team_name", STRING), ("referee", STRING),
    ("home_goals", INT), ("away_goals", INT), ("ht_home_goals", INT), ("ht_away_goals", INT),
    ("ht_result", CATEGORICAL),
    ("home_shots", INT), ("away_shots", INT),
    ("home_shots_on_target", INT), ("away_shots_on_target", INT),
    ("home_corners", INT), ("away_corners", INT), ("home_fouls", INT), ("away_fouls", INT),
    ("home_yellow_cards", INT), ("away_yellow_cards", INT),
    ("home_red_cards", INT), ("away_red_cards", INT),
    ("result", CATEGORICAL), ("goal_difference", INT),
    ("mkt_avg_pre_home", FLOAT), ("mkt_avg_pre_draw", FLOAT), ("mkt_avg_pre_away", FLOAT),
    ("mkt_avg_close_home", FLOAT), ("mkt_avg_close_draw", FLOAT), ("mkt_avg_close_away", FLOAT),
]
CANONICAL_SCHEMA: tuple[ColumnSpec, ...] = tuple(ColumnSpec(n, t) for n, t in _SPEC) + (
    ColumnSpec("dq_flags", STRING, nullable=True),)
CANONICAL_COLUMNS: tuple[str, ...] = tuple(c.name for c in CANONICAL_SCHEMA)
TYPE_OF = {c.name: c.logical_type for c in CANONICAL_SCHEMA}

# Columnas CANONICAL copiadas 1:1 desde una columna RAW/INTERIM (diccionario RAW §7)
RAW_SOURCE = {
    "source_div": "Div", "referee": "Referee",
    "home_goals": "FTHG", "away_goals": "FTAG", "result": "FTR",
    "ht_home_goals": "HTHG", "ht_away_goals": "HTAG", "ht_result": "HTR",
    "home_shots": "HS", "away_shots": "AS",
    "home_shots_on_target": "HST", "away_shots_on_target": "AST",
    "home_corners": "HC", "away_corners": "AC", "home_fouls": "HF", "away_fouls": "AF",
    "home_yellow_cards": "HY", "away_yellow_cards": "AY",
    "home_red_cards": "HR", "away_red_cards": "AR",
    "mkt_avg_pre_home": "AvgH", "mkt_avg_pre_draw": "AvgD", "mkt_avg_pre_away": "AvgA",
    "mkt_avg_close_home": "AvgCH", "mkt_avg_close_draw": "AvgCD", "mkt_avg_close_away": "AvgCA",
}


def serialize_value(value, logical_type: str) -> str:
    """Valor tipado -> texto CSV (§4.0). None -> campo vacío."""
    if value is None:
        return ""
    if logical_type in (STRING, CATEGORICAL):
        return value
    if logical_type == INT:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"Se esperaba int: {value!r}")
        return str(value)
    if logical_type == FLOAT:
        x = float(value)
        if not math.isfinite(x):
            raise ValueError(f"Float no finito: {value!r}")
        return repr(x)        # más corta con ida y vuelta exacta; enteros como `4.0` (D43)
    if logical_type == DATE:
        return value.isoformat()
    if logical_type == TIME:
        return value.strftime("%H:%M")
    if logical_type == DATETIME:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError(f"datetime fuera de convención: {value!r}")
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    raise ValueError(f"Tipo lógico desconocido: {logical_type}")


def parse_value(text: str, logical_type: str, nullable: bool):
    """Texto CSV -> valor tipado, con dtypes explícitos (§4.0 'Tipado en lectura')."""
    if text == "":
        if nullable:
            return None
        raise ValueError("Campo vacío en columna no nula")
    if logical_type in (STRING, CATEGORICAL):
        return text
    if logical_type == INT:
        return int(text)
    if logical_type == FLOAT:
        return float(text)
    if logical_type == DATE:
        return date.fromisoformat(text)
    if logical_type == TIME:
        return time.fromisoformat(text)
    if logical_type == DATETIME:
        return datetime.fromisoformat(text)
    raise ValueError(f"Tipo lógico desconocido: {logical_type}")
