"""Lectura tolerante y estricta de los CSV RAW de Football-Data (solo lectura).

- Tolera BOM UTF-8 presente o ausente (Q03) y CRLF (Q04).
- Decodifica UTF-8 de forma estricta (un byte inválido es un error, no se reemplaza).
- Exige que todas las filas tengan el mismo ancho que la cabecera.
- Devuelve los valores como texto exacto del archivo (sin strip ni tipado).
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import settings

UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class RawTable:
    file_name: str
    season: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]     # rows[i] es la fila de datos source_row = i + 1
    has_bom: bool
    line_ending: str                      # "CRLF", "LF" o "MIXED"
    n_bytes: int


class RawFormatError(ValueError):
    pass


def season_from_file_name(file_name: str) -> str:
    """`PL_2021-2022_raw.csv` -> `2021-2022`; exige años consecutivos (contrato §4.1)."""
    m = re.match(settings.RAW_FILE_PATTERN, file_name)
    if not m:
        raise RawFormatError(f"Nombre de archivo RAW inesperado: {file_name}")
    y1, y2 = int(m.group(1)), int(m.group(2))
    if y2 != y1 + 1:
        raise RawFormatError(f"Temporada con años no consecutivos: {file_name}")
    return f"{y1}-{y2}"


def _line_ending(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n")
    cr = data.count(b"\r")
    if crlf == lf == cr and lf > 0:
        return "CRLF"
    if crlf == 0 and cr == 0 and lf > 0:
        return "LF"
    return "MIXED"


def parse_raw_bytes(data: bytes, file_name: str) -> RawTable:
    has_bom = data.startswith(UTF8_BOM)
    text = data[len(UTF8_BOM):].decode("utf-8") if has_bom else data.decode("utf-8")
    if "﻿" in text:
        raise RawFormatError(f"{file_name}: BOM en una posición distinta del inicio")
    records = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    if not records:
        raise RawFormatError(f"{file_name}: archivo vacío")
    header = tuple(records[0])
    if len(set(header)) != len(header):
        raise RawFormatError(f"{file_name}: cabecera con columnas duplicadas")
    if any(h != h.strip() or h == "" for h in header):
        raise RawFormatError(f"{file_name}: nombre de columna vacío o con espacios")
    body = records[1:]
    for i, r in enumerate(body, start=1):
        if len(r) != len(header):
            raise RawFormatError(f"{file_name}: source_row {i} tiene {len(r)} campos (cabecera: {len(header)})")
    return RawTable(
        file_name=file_name, season=season_from_file_name(file_name), header=header,
        rows=tuple(tuple(r) for r in body), has_bom=has_bom,
        line_ending=_line_ending(data), n_bytes=len(data),
    )


def read_raw_csv(path: Path) -> RawTable:
    with open(path, "rb") as fh:          # solo lectura binaria
        data = fh.read()
    return parse_raw_bytes(data, path.name)
