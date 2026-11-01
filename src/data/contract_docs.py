"""Lectura de los documentos contractuales legibles por máquina (manifiesto, diccionario)."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from src.config import settings


@dataclass(frozen=True)
class ManifestEntry:
    file_name: str
    relative_path: str
    season: str
    rows: int | None
    columns: int | None
    sha256: str
    has_bom: bool | None
    min_date: str
    max_date: str
    bytes: int | None
    line_ending: str
    role: str

    def path(self, root: Path) -> Path:
        return root / Path(self.relative_path)


def _opt_int(v: str) -> int | None:
    return int(v) if v != "" else None


def _opt_bool(v: str) -> bool | None:
    return {"true": True, "false": False, "": None}[v]


def load_manifest(path: Path = settings.MANIFEST_PATH) -> list[ManifestEntry]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [
            ManifestEntry(
                file_name=r["file_name"], relative_path=r["relative_path"], season=r["season"],
                rows=_opt_int(r["rows"]), columns=_opt_int(r["columns"]), sha256=r["sha256"].lower(),
                has_bom=_opt_bool(r["has_bom"]), min_date=r["min_date"], max_date=r["max_date"],
                bytes=_opt_int(r["bytes"]), line_ending=r["line_ending"], role=r["role"],
            )
            for r in csv.DictReader(fh)
        ]


def raw_data_entries(manifest: list[ManifestEntry]) -> list[ManifestEntry]:
    """Entradas `role = raw_data`, en orden de temporada (orden determinista)."""
    return sorted((m for m in manifest if m.role == "raw_data"), key=lambda m: m.season)


@dataclass(frozen=True)
class DictionaryColumn:
    column: str
    family: str
    present: dict[str, bool]          # season -> presente en el RAW de esa temporada
    canonical_field: str


def load_raw_dictionary(path: Path = settings.RAW_DICTIONARY_PATH) -> list[DictionaryColumn]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        season_cols = [c for c in reader.fieldnames if c.startswith("present_")]
        out = []
        for r in reader:
            out.append(DictionaryColumn(
                column=r["column"], family=r["family"],
                present={c.removeprefix("present_"): r[c] == "1" for c in season_cols},
                canonical_field=r["canonical_field"],
            ))
        return out
