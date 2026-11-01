"""CHECKPOINT B — INTERIM -> CANONICAL.

Uso (desde la raíz de SCOPE/):
    python -m src.run_checkpoint_b

Secuencia: V01 (antes) -> SHA-256 de INTERIM == aprobado -> A01–A11 sobre INTERIM (solo lectura)
-> CANONICAL (dos construcciones, comparación byte a byte) -> escritura -> V02–V10
-> V01 y SHA-256 de INTERIM (después) -> informe. Código de salida 0 solo si todo es PASS.
INTERIM nunca se reescribe en este checkpoint.
"""
from __future__ import annotations

import hashlib
import logging
import sys

from src.config import settings
from src.data.build_canonical import (InterimMismatch, build_canonical_records, read_approved_interim,
                                      serialize_canonical, write_canonical)
from src.data.contract_docs import load_manifest, load_raw_dictionary, raw_data_entries
from src.data.interim_schema import build_interim_schema
from src.data.team_mapping import load_team_mapping
from src.run_checkpoint_a import build_interim_bytes
from src.validation.canonical_checks import CanonicalContext, run_canonical_checks
from src.validation.interim_checks import run_interim_checks
from src.validation.raw_integrity import check_v01
from src.validation.report import write_report_b
from src.validation.results import CheckResult, all_passed

log = logging.getLogger("scope.checkpoint_b")


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_canonical_bytes() -> bytes:
    return serialize_canonical(build_canonical_records(read_approved_interim(), load_team_mapping()))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    entries = raw_data_entries(load_manifest())
    raw_paths = [m.path(settings.PROJECT_ROOT) for m in entries]

    v01_before, hashes_before = check_v01(phase="(antes)")
    interim_before = _sha(settings.INTERIM_FILE) if settings.INTERIM_FILE.is_file() else "missing"
    gate = CheckResult("B00", "Entrada: INTERIM existe y su SHA-256 es el aprobado en CHECKPOINT A")
    if interim_before != settings.INTERIM_APPROVED_SHA256:
        gate.fail(f"SHA-256 INTERIM {interim_before} != aprobado {settings.INTERIM_APPROVED_SHA256}")
    if not (v01_before.passed and gate.passed):
        for d in v01_before.details + gate.details:
            log.error(d)
        write_report_b([v01_before, gate], hashes_before, {}, (interim_before, ""), None, blocked=True)
        log.error("RAW o INTERIM no coinciden con el estado aprobado: proceso detenido")
        return 1

    a_results, _ = run_interim_checks(
        settings.INTERIM_FILE.read_bytes(), build_interim_schema(load_raw_dictionary()), raw_paths,
        {m.file_name: m.rows for m in entries}, rebuild=lambda: build_interim_bytes()[0])
    gate.info.append("A01–A11 sobre INTERIM: " + ", ".join(f"{r.check_id} {r.status}" for r in a_results))
    if not all_passed(a_results):
        gate.fail("INTERIM no supera A01–A11")
        write_report_b([v01_before, gate, *a_results], hashes_before, {}, (interim_before, ""), None, True)
        return 1

    try:
        first, second = build_canonical_bytes(), build_canonical_bytes()
    except InterimMismatch as exc:
        log.error("%s", exc)
        return 1
    det = CheckResult("B01", "Determinismo: dos construcciones desde el mismo INTERIM dan los mismos bytes")
    if first != second:
        det.fail("Las dos construcciones difieren")
    det.info.append(f"SHA-256 construcción 1 = {hashlib.sha256(first).hexdigest()}")
    det.info.append(f"SHA-256 construcción 2 = {hashlib.sha256(second).hexdigest()}")
    write_canonical(first)
    on_disk = settings.CANONICAL_FILE.read_bytes()
    if on_disk != first:
        det.fail("El archivo escrito no coincide con la construcción en memoria")

    ctx = CanonicalContext(on_disk, raw_paths, settings.TEAM_MAPPING_PATH, {m.file_name for m in entries})
    v_results = run_canonical_checks(ctx)

    v01_after, hashes_after = check_v01(phase="(después)")
    if hashes_after != hashes_before:
        v01_after.fail("SHA-256 RAW distintos antes/después")
    interim_after = _sha(settings.INTERIM_FILE)
    if interim_after != interim_before:
        v01_after.fail("INTERIM cambió durante CHECKPOINT B")

    results = [v01_before, gate, det, *v_results, v01_after]
    for r in results:
        log.info("%s %-4s %s", r.check_id, r.status, r.title)
        for d in r.details[:10]:
            log.error("   %s", d)
    ok = all_passed(results)
    canonical_sha = hashlib.sha256(on_disk).hexdigest()
    write_report_b(results, hashes_before, hashes_after, (interim_before, interim_after), canonical_sha, not ok)
    log.info("CANONICAL SHA-256: %s", canonical_sha)
    log.info("CHECKPOINT B: %s", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
