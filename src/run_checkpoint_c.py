"""CHECKPOINT C — CANONICAL -> team_match_log -> FEATURES.

Uso (desde la raíz de SCOPE/):
    python -m src.run_checkpoint_c

Secuencia: V01 (antes) -> SHA-256 de INTERIM y CANONICAL == aprobados -> V02–V10 sobre
CANONICAL (solo lectura) -> team_match_log y FEATURES (dos construcciones, comparación
byte a byte) -> escritura -> C01–C02, V11–V17 -> V01 y SHA-256 de capas previas (después)
-> informe. Código de salida 0 solo si todo es PASS. No reescribe RAW, INTERIM ni CANONICAL.
"""
from __future__ import annotations

import logging
import sys

from src.config import settings
from src.data.build_features import build_all_bytes, build_features, sha256, write_output
from src.data.canonical_reader import CanonicalMismatch, read_approved_canonical
from src.data.contract_docs import load_manifest, raw_data_entries
from src.validation.canonical_checks import CanonicalContext, run_canonical_checks
from src.validation.features_checks import (FeaturesContext, check_v11, check_v12, check_v13, check_v16,
                                            check_v17, read_csv)
from src.validation.leakage_checks import check_v14, check_v15
from src.validation.raw_integrity import check_v01
from src.validation.report import write_report_generic
from src.validation.results import CheckResult, all_passed
from src.validation.tml_checks import check_c01, check_c02

log = logging.getLogger("scope.checkpoint_c")
TITLE = "CHECKPOINT C — CANONICAL → team_match_log → FEATURES: informe de validación"


def _file_sha(path) -> str:
    return sha256(path.read_bytes()) if path.is_file() else "missing"


def _prior_layers() -> dict[str, str]:
    return {"INTERIM": _file_sha(settings.INTERIM_FILE), "CANONICAL": _file_sha(settings.CANONICAL_FILE)}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    entries = raw_data_entries(load_manifest())
    raw_paths = [m.path(settings.PROJECT_ROOT) for m in entries]
    approved = {"INTERIM": settings.INTERIM_APPROVED_SHA256, "CANONICAL": settings.CANONICAL_APPROVED_SHA256}

    v01_before, hashes_before = check_v01(phase="(antes)")
    layers_before = _prior_layers()
    gate = CheckResult("C00", "Entrada: INTERIM y CANONICAL aprobados; V02–V10 en modo lectura")
    for k, v in layers_before.items():
        if v != approved[k]:
            gate.fail(f"SHA-256 {k} {v} != aprobado {approved[k]}")
    if gate.passed:
        canonical_bytes = settings.CANONICAL_FILE.read_bytes()
        ctx_b = CanonicalContext(canonical_bytes, raw_paths, settings.TEAM_MAPPING_PATH,
                                 {m.file_name for m in entries})
        b_results = run_canonical_checks(ctx_b)
        gate.info.append("V02–V10 sobre CANONICAL: " + ", ".join(f"{r.check_id} {r.status}" for r in b_results))
        if not all_passed(b_results):
            gate.fail("CANONICAL no supera V02–V10")
    if not (v01_before.passed and gate.passed):
        for d in v01_before.details + gate.details:
            log.error(d)
        write_report_generic(settings.REPORT_C_FILE, TITLE, [], [v01_before, gate], hashes_before, {}, True)
        log.error("Capas previas no coinciden con el estado aprobado: proceso detenido")
        return 1

    try:
        canonical = read_approved_canonical()
    except CanonicalMismatch as exc:
        log.error("%s", exc)
        return 1
    tml1, feat1 = build_all_bytes(canonical)
    tml2, feat2 = build_all_bytes(canonical)
    det = CheckResult("C03", "Determinismo: dos construcciones dan bytes idénticos (team_match_log y FEATURES)")
    if tml1 != tml2:
        det.fail("team_match_log difiere entre construcciones")
    if feat1 != feat2:
        det.fail("FEATURES difiere entre construcciones")
    write_output(tml1, settings.TEAM_MATCH_LOG_FILE)
    write_output(feat1, settings.FEATURES_FILE)
    tml_disk, feat_disk = settings.TEAM_MATCH_LOG_FILE.read_bytes(), settings.FEATURES_FILE.read_bytes()
    if (tml_disk, feat_disk) != (tml1, feat1):
        det.fail("Los archivos escritos no coinciden con la construcción en memoria")
    det.info.append(f"team_match_log: {sha256(tml1)} = {sha256(tml2)}")
    det.info.append(f"FEATURES: {sha256(feat1)} = {sha256(feat2)}")

    ctx = FeaturesContext(feat_disk, canonical_bytes)
    _, can_rows = read_csv(canonical_bytes)
    _, feat_rows = read_csv(feat_disk)
    results = [v01_before, gate, det,
               check_c01(tml_disk, len(canonical)), check_c02(tml_disk, canonical_bytes),
               check_v11(ctx), check_v12(ctx), check_v13(ctx),
               check_v14(canonical, baseline=build_features(canonical)[1]),
               check_v15(can_rows, feat_rows), check_v16(ctx), check_v17(ctx)]

    v01_after, hashes_after = check_v01(phase="(después)")
    if hashes_after != hashes_before:
        v01_after.fail("SHA-256 RAW distintos antes/después")
    layers_after = _prior_layers()
    for k in approved:
        if layers_after[k] != approved[k]:
            v01_after.fail(f"{k} cambió durante CHECKPOINT C")
    v01_after.info.append(f"INTERIM después: {layers_after['INTERIM']}; CANONICAL después: {layers_after['CANONICAL']}")
    results.append(v01_after)

    for r in results:
        log.info("%s %-4s %s", r.check_id, r.status, r.title)
        for d in r.details[:10]:
            log.error("   %s", d)
    ok = all_passed(results)
    preamble = [f"- INTERIM aprobado / después: `{approved['INTERIM']}` / `{layers_after['INTERIM']}`",
                f"- CANONICAL aprobado / después: `{approved['CANONICAL']}` / `{layers_after['CANONICAL']}`",
                f"- team_match_log: `data/interim/team_match_log_v0.1.csv` — SHA-256 `{sha256(tml_disk)}`",
                f"- FEATURES: `data/features/pl_features_v0.1.csv` — SHA-256 `{sha256(feat_disk)}`"]
    write_report_generic(settings.REPORT_C_FILE, TITLE, preamble, results, hashes_before, hashes_after, not ok)
    log.info("team_match_log SHA-256: %s", sha256(tml_disk))
    log.info("FEATURES SHA-256: %s", sha256(feat_disk))
    log.info("CHECKPOINT C: %s", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
