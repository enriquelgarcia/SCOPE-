"""Esquema de INTERIM v0.1: 4 columnas de trazabilidad + unión de las 162 columnas RAW.

Los nombres RAW se conservan sin cambios (todavía no se usan nombres CANONICAL) y en el
orden del diccionario RAW (= orden de primera aparición en las temporadas).

El tipo lógico de cada columna RAW se deriva de su `family` en `raw_dictionary_v0.1.csv`
(no de inspeccionar valores), salvo las categóricas FTR/HTR de las familias de resultado.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import settings
from src.data.contract_docs import DictionaryColumn

# Tipos lógicos de INTERIM
STRING, DATE, TIME, INT, FLOAT, CATEGORICAL = "string", "date", "time", "int", "float", "categorical"

TRACE_TYPES = {"season": STRING, "source_name": STRING, "source_file": STRING, "source_row": INT}

_FAMILY_TYPES = {
    "identification": STRING,
    "participants": STRING,
    "referee": STRING,
    "result_full_time": INT,
    "result_half_time": INT,
    "match_statistics": INT,
    "odds_1x2_pre": FLOAT,
    "odds_ou25_pre": FLOAT,
    "odds_ah_pre": FLOAT,
    "odds_1x2_close": FLOAT,
    "odds_ou25_close": FLOAT,
    "odds_ah_close": FLOAT,
}
_COLUMN_OVERRIDES = {"Date": DATE, "Time": TIME, "FTR": CATEGORICAL, "HTR": CATEGORICAL}


@dataclass(frozen=True)
class InterimSchema:
    raw_columns: tuple[str, ...]                 # 162, orden del diccionario
    raw_types: dict[str, str]
    presence: dict[str, dict[str, bool]]         # columna -> temporada -> presente

    @property
    def columns(self) -> tuple[str, ...]:
        return settings.TRACE_COLUMNS + self.raw_columns

    def type_of(self, column: str) -> str:
        return TRACE_TYPES[column] if column in TRACE_TYPES else self.raw_types[column]


def build_interim_schema(dictionary: list[DictionaryColumn]) -> InterimSchema:
    cols = tuple(d.column for d in dictionary)
    if len(cols) != len(set(cols)):
        raise ValueError("El diccionario RAW contiene columnas duplicadas")
    if set(cols) & set(settings.TRACE_COLUMNS):
        raise ValueError("Una columna RAW colisiona con una columna de trazabilidad")
    types = {}
    for d in dictionary:
        t = _COLUMN_OVERRIDES.get(d.column) or _FAMILY_TYPES.get(d.family)
        if d.family == "datetime" and d.column not in _COLUMN_OVERRIDES:
            t = None
        if t is None:
            raise ValueError(f"Sin tipo lógico definido para {d.column} (family={d.family})")
        types[d.column] = t
    return InterimSchema(raw_columns=cols, raw_types=types,
                         presence={d.column: dict(d.present) for d in dictionary})
