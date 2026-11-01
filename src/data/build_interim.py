"""RAW -> INTERIM (CHECKPOINT A).

Una fila INTERIM por fila de datos RAW (1:1). Orden de filas: temporada ascendente y,
dentro de cada temporada, `source_row` ascendente (orden original del archivo RAW).
Columnas: TRACE_COLUMNS + unión de las 162 columnas RAW (nombres originales).
Una columna ausente en una temporada se representa con campo vacío en todas sus filas;
la presencia por temporada queda documentada en `raw_dictionary_v0.1.csv`.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.config import settings
from src.data.cell_parsing import CellParseError, to_interim_text
from src.data.interim_schema import InterimSchema
from src.data.raw_reader import RawTable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StripEvent:
    season: str
    source_file: str
    source_row: int
    column: str
    raw_value: str
    interim_value: str


@dataclass
class InterimTable:
    header: tuple[str, ...]
    rows: list[tuple[str, ...]]
    strip_events: list[StripEvent] = field(default_factory=list)


def _check_table_against_schema(table: RawTable, schema: InterimSchema) -> None:
    unknown = [c for c in table.header if c not in schema.raw_types]
    if unknown:
        raise ValueError(f"{table.file_name}: columnas no presentes en el diccionario RAW: {unknown}")
    expected = {c for c, p in schema.presence.items() if p.get(table.season)}
    if set(table.header) != expected:
        raise ValueError(f"{table.file_name}: columnas no coinciden con el diccionario para {table.season}")


def build_interim_table(tables: list[RawTable], schema: InterimSchema) -> InterimTable:
    out = InterimTable(header=schema.columns, rows=[])
    for table in sorted(tables, key=lambda t: t.season):
        _check_table_against_schema(table, schema)
        position = {c: i for i, c in enumerate(table.header)}
        for source_row, raw_row in enumerate(table.rows, start=1):
            values = [table.season, settings.SOURCE_NAME, table.file_name, str(source_row)]
            for col in schema.raw_columns:
                if col not in position:
                    values.append("")                 # columna ausente en esta temporada
                    continue
                raw_value = raw_row[position[col]]
                try:
                    text = to_interim_text(raw_value, schema.type_of(col))
                except CellParseError as exc:
                    raise CellParseError(f"{table.file_name} source_row={source_row} {col}: {exc}") from exc
                if text != raw_value and raw_value.strip() != raw_value:
                    out.strip_events.append(StripEvent(table.season, table.file_name, source_row,
                                                       col, raw_value, text))
                values.append(text)
            out.rows.append(tuple(values))
        log.info("INTERIM: %s -> %d filas", table.file_name, len(table.rows))
    return out


def serialize_csv(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> bytes:
    """CSV RFC 4180 (comillas solo si hacen falta), UTF-8 sin BOM, LF incluida la última línea."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def write_interim(data: bytes, path: Path = settings.INTERIM_FILE) -> Path:
    settings.assert_writable_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    log.info("INTERIM escrito: %s (%d bytes)", path, len(data))
    return path
