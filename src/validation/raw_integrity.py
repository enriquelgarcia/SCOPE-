"""V01 — Integridad RAW (validation_spec_v0.1 §2).

SHA-256 de cada archivo del manifiesto (5 CSV `raw_data` + `notes.txt`) y, en los CSV,
filas, columnas, BOM, fecha mínima y máxima. Comprueba además bytes y fin de línea,
que el manifiesto también registra. Solo lee archivos.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from src.config import settings
from src.data.cell_parsing import parse_raw_date
from src.data.contract_docs import ManifestEntry, load_manifest, raw_data_entries
from src.data.raw_reader import read_raw_csv
from src.validation.results import CheckResult


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_hashes(manifest: list[ManifestEntry], root: Path) -> dict[str, str]:
    return {m.relative_path: sha256_of(m.path(root)) for m in manifest}


def check_v01(root: Path = settings.PROJECT_ROOT, manifest_path: Path = settings.MANIFEST_PATH,
              phase: str = "") -> tuple[CheckResult, dict[str, str]]:
    res = CheckResult("V01", f"Integridad RAW por SHA-256 {phase}".strip())
    manifest = load_manifest(manifest_path)
    hashes: dict[str, str] = {}
    raw_entries = raw_data_entries(manifest)
    if len(raw_entries) != settings.EXPECTED_SEASONS:
        res.fail(f"El manifiesto tiene {len(raw_entries)} filas raw_data (se esperan {settings.EXPECTED_SEASONS})")
    for m in manifest:
        p = m.path(root)
        if not p.is_file():
            res.fail(f"No existe {m.relative_path}")
            continue
        digest = sha256_of(p)
        hashes[m.relative_path] = digest
        if digest != m.sha256:
            res.fail(f"SHA-256 distinto en {m.relative_path}: {digest} != {m.sha256}")
        if m.bytes is not None and p.stat().st_size != m.bytes:
            res.fail(f"Tamaño distinto en {m.relative_path}: {p.stat().st_size} != {m.bytes}")
        if m.role != "raw_data":
            continue
        t = read_raw_csv(p)
        if t.season != m.season:
            res.fail(f"{m.file_name}: temporada del nombre {t.season} != manifiesto {m.season}")
        if len(t.rows) != m.rows:
            res.fail(f"{m.file_name}: {len(t.rows)} filas != {m.rows}")
        if len(t.header) != m.columns:
            res.fail(f"{m.file_name}: {len(t.header)} columnas != {m.columns}")
        if t.has_bom != m.has_bom:
            res.fail(f"{m.file_name}: BOM {t.has_bom} != {m.has_bom}")
        if t.line_ending != m.line_ending:
            res.fail(f"{m.file_name}: fin de línea {t.line_ending} != {m.line_ending}")
        di = t.header.index("Date")
        dates = [parse_raw_date(r[di]).date().isoformat() for r in t.rows]
        if min(dates) != m.min_date or max(dates) != m.max_date:
            res.fail(f"{m.file_name}: rango de fechas {min(dates)}..{max(dates)} != {m.min_date}..{m.max_date}")
        res.info.append(f"{m.file_name}: sha256 OK={digest == m.sha256}, filas={len(t.rows)}, "
                        f"columnas={len(t.header)}, BOM={t.has_bom}, {t.line_ending}, "
                        f"{min(dates)}..{max(dates)}")
    return res, hashes
