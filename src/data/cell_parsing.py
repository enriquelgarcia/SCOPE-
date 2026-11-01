"""Parseo y serialización de celdas RAW -> INTERIM (solo transformaciones técnicas).

Reglas (ninguna imputa, corrige ni descarta valores):
- celda vacía -> nulo -> campo CSV vacío;
- string / categorical: `strip()` (Q02); se registra cada celda modificada;
- date: parseo estricto `dd/mm/yyyy` (%d/%m/%Y, con regex de 2/2/4 dígitos) -> `YYYY-MM-DD` (D24, D28);
- time: parseo estricto `HH:MM` -> `HH:MM`;
- int: `-?\\d+` -> entero base 10;
- float: `-?\\d+(\\.\\d+)?` -> float; se serializa con `repr` (representación más corta
  que reproduce exactamente el mismo double; p. ej. RAW `4` -> `4.0`, `1.85` -> `1.85`).
Los valores numéricos con espacios o con formato inesperado provocan error (no se "arreglan").
"""
from __future__ import annotations

import math
import re
from datetime import datetime

from src.config import settings
from src.data import interim_schema as S

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")


class CellParseError(ValueError):
    pass


def parse_raw_date(value: str) -> datetime:
    if not _DATE_RE.match(value):
        raise CellParseError(f"Fecha RAW con formato distinto de dd/mm/yyyy: {value!r}")
    return datetime.strptime(value, settings.RAW_DATE_FORMAT)


def parse_raw_time(value: str) -> str:
    if not _TIME_RE.match(value):
        raise CellParseError(f"Hora RAW con formato distinto de HH:MM: {value!r}")
    return datetime.strptime(value, settings.RAW_TIME_FORMAT).strftime("%H:%M")


def to_interim_text(raw_value: str, logical_type: str) -> str:
    """Convierte el texto RAW de una celda en su serialización INTERIM ('' = nulo)."""
    if logical_type in (S.STRING, S.CATEGORICAL):
        return raw_value.strip()
    if raw_value == "":
        return ""
    if logical_type == S.DATE:
        return parse_raw_date(raw_value).strftime(settings.ISO_DATE_FORMAT)
    if logical_type == S.TIME:
        return parse_raw_time(raw_value)
    if logical_type == S.INT:
        if not _INT_RE.match(raw_value):
            raise CellParseError(f"Entero RAW inválido: {raw_value!r}")
        return str(int(raw_value))
    if logical_type == S.FLOAT:
        if not _FLOAT_RE.match(raw_value):
            raise CellParseError(f"Decimal RAW inválido: {raw_value!r}")
        x = float(raw_value)
        if not math.isfinite(x):
            raise CellParseError(f"Decimal no finito: {raw_value!r}")
        return repr(x)
    raise CellParseError(f"Tipo lógico desconocido: {logical_type}")
