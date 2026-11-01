"""Mapeo de equipos: (source, alias RAW) -> team_id -> display_name (contrato §8, D27, D31).

Estricto: un alias desconocido, un alias duplicado o un team_id con dos display_name
distintos hacen fallar la carga o la resolución. No se generan slugs.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import settings

_TEAM_ID_RE = re.compile(r"^[a-z0-9_]+$")


class UnknownTeamAlias(KeyError):
    pass


@dataclass(frozen=True)
class TeamMapping:
    alias_to_id: dict[tuple[str, str], str]     # (source, source_name) -> team_id
    display_name: dict[str, str]                # team_id -> display_name

    def resolve(self, source: str, alias: str) -> tuple[str, str]:
        key = (source, alias)
        if key not in self.alias_to_id:
            raise UnknownTeamAlias(f"Alias sin mapeo: source={source!r} source_name={alias!r}")
        team_id = self.alias_to_id[key]
        return team_id, self.display_name[team_id]

    @property
    def team_ids(self) -> frozenset[str]:
        return frozenset(self.display_name)


def load_team_mapping(path: Path = settings.TEAM_MAPPING_PATH) -> TeamMapping:
    alias_to_id: dict[tuple[str, str], str] = {}
    display: dict[str, str] = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["source"], r["source_name"])
            tid, name = r["team_id"], r["display_name"]
            if key in alias_to_id:
                raise ValueError(f"Alias duplicado en team_mapping: {key}")
            if not _TEAM_ID_RE.match(tid):
                raise ValueError(f"team_id inválido: {tid!r}")
            if tid in display and display[tid] != name:
                raise ValueError(f"team_id {tid} con dos display_name")
            if name != name.strip() or not name:
                raise ValueError(f"display_name inválido para {tid}")
            alias_to_id[key] = tid
            display[tid] = name
    return TeamMapping(alias_to_id, display)
