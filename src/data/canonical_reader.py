"""Lectura tipada del CANONICAL aprobado (dtypes del esquema 4.9; §4.0 'Tipado en lectura')."""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from src.config import settings
from src.data.canonical_schema import CANONICAL_COLUMNS, CANONICAL_SCHEMA, parse_value


class CanonicalMismatch(RuntimeError):
    pass


def parse_canonical_bytes(data: bytes) -> list[dict]:
    reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
    header = next(reader)
    if tuple(header) != CANONICAL_COLUMNS:
        raise CanonicalMismatch("Cabecera CANONICAL distinta del esquema 4.9")
    return [{s.name: parse_value(v, s.logical_type, s.nullable) for s, v in zip(CANONICAL_SCHEMA, row)}
            for row in reader]


def read_approved_canonical(path: Path = settings.CANONICAL_FILE,
                            expected_sha256: str = settings.CANONICAL_APPROVED_SHA256) -> list[dict]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise CanonicalMismatch(f"CANONICAL no coincide con el aprobado: {digest} != {expected_sha256}")
    return parse_canonical_bytes(data)
