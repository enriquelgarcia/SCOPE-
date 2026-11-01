"""Esquema normativo de FEATURES v0.1 (contrato §5.4) y serialización (§4.0, D43).

30 columnas en el orden normativo. Reutiliza la serialización de CANONICAL y añade `bool`.
Ausente (None) = campo CSV vacío. Floats con `repr` (más corta con ida y vuelta exacta;
puede producir notación científica para valores muy pequeños, p. ej. `5.551115123125783e-17`).
"""
from __future__ import annotations

from src.data import canonical_schema as CS
from src.data.canonical_schema import ColumnSpec

BOOL = "bool"
BOOL_SERIALIZATION = {True: "true", False: "false"}

# Métricas por equipo (§5.1) y métricas con diferencia (§5.2), en orden normativo
TEAM_METRICS = ("n_prev_season", "ppg_season", "gf_pg_season", "ga_pg_season",
                "ppg_last5", "gf_pg_last5", "ga_pg_last5", "sot_pg_last5")
RATE_METRICS = TEAM_METRICS[1:]                 # nullables; vacías solo si n_prev_season = 0
DIFF_METRICS = RATE_METRICS                     # no existe diff_n_prev_season

_cols: list[ColumnSpec] = [ColumnSpec("match_id", CS.STRING), ColumnSpec("season", CS.STRING),
                           ColumnSpec("kickoff_datetime", CS.DATETIME)]
for _p in ("h", "a"):
    _cols.append(ColumnSpec(f"{_p}_n_prev_season", CS.INT))
    _cols += [ColumnSpec(f"{_p}_{m}", CS.FLOAT, nullable=True) for m in RATE_METRICS]
_cols += [ColumnSpec(f"diff_{m}", CS.FLOAT, nullable=True) for m in DIFF_METRICS]
_cols += [ColumnSpec("result", CS.CATEGORICAL), ColumnSpec("goal_difference", CS.INT),
          ColumnSpec("is_modeling_eligible", BOOL), ColumnSpec("feature_version", CS.STRING)]

FEATURES_SCHEMA: tuple[ColumnSpec, ...] = tuple(_cols)
FEATURES_COLUMNS: tuple[str, ...] = tuple(c.name for c in FEATURES_SCHEMA)
NUMERIC_FEATURES: tuple[str, ...] = FEATURES_COLUMNS[3:26]       # 16 por equipo + 7 diferencias
assert len(FEATURES_SCHEMA) == 30 and len(NUMERIC_FEATURES) == 23


def serialize_value(value, logical_type: str) -> str:
    if logical_type == BOOL:
        if not isinstance(value, bool):
            raise TypeError(f"Se esperaba bool: {value!r}")
        return BOOL_SERIALIZATION[value]
    return CS.serialize_value(value, logical_type)


def parse_value(text: str, logical_type: str, nullable: bool):
    if logical_type == BOOL:
        return {"true": True, "false": False}[text]
    return CS.parse_value(text, logical_type, nullable)
