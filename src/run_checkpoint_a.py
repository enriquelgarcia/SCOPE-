"""CHECKPOINT A — RAW -> INTERIM.

Uso (desde la raíz de SCOPE/):
    python -m src.run_checkpoint_a

Secuencia: V01 (antes) -> lectura RAW -> INTERIM -> escritura -> A01–A11 -> V01 (después)
-> informe en reports/checkpoint_a/. Código de salida 0 solo si todo es PASS.
"""
from __future__ import annotations

import logging
import sys

from src.config import settings
from src.data.build_interim import build_interim_table, serialize_csv, write_interim
from src.data.contract_docs import load_manifest, load_raw_dictionary, raw_data_entries
from src.data.interim_schema import build_interim_schema
from src.data.raw_reader import read_raw_csv
from src.validation.interim_checks import run_interim_checks
from src.validation.raw_integrity import check_v01
from src.validation.report import write_report
from src.validation.results import all_passed

log = logging.getLogger("scope.checkpoint_a")


def build_interim_bytes() -> tuple[bytes, list]:
    manifest = load_manifest()
    schema = build_interim_schema(load_raw_dictionary())
    tables = [read_raw_csv(m.path(settings.PROJECT_ROOT)) for m in raw_data_entries(manifest)]
    table = build_interim_table(tables, schema)
    return serialize_csv(table.header, table.rows), table.strip_events


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log.info("Raíz SCOPE: %s", settings.PROJECT_ROOT)

    v01_before, hashes_before = check_v01(phase="(antes)")
    log.info("V01 antes: %s", v01_before.status)
    if not v01_before.passed:
        for d in v01_before.details:
            log.error(d)
        write_report([v01_before], hashes_before, {}, [], blocked=True)
        log.error("RAW no coincide con el manifiesto: proceso detenido sin generar INTERIM")
        return 1

    data, strip_events = build_interim_bytes()
    write_interim(data)

    manifest = load_manifest()
    raw_entries = raw_data_entries(manifest)
    schema = build_interim_schema(load_raw_dictionary())
    with open(settings.INTERIM_FILE, "rb") as fh:
        on_disk = fh.read()
    results, _ = run_interim_checks(
        on_disk, schema,
        raw_paths=[m.path(settings.PROJECT_ROOT) for m in raw_entries],
        manifest_rows={m.file_name: m.rows for m in raw_entries},
        rebuild=lambda: build_interim_bytes()[0],
    )
    v01_after, hashes_after = check_v01(phase="(después)")
    if hashes_after != hashes_before:
        v01_after.fail("Los SHA-256 después del proceso difieren de los de antes")
    results = [v01_before, *results, v01_after]

    for r in results:
        log.info("%s %-4s %s", r.check_id, r.status, r.title)
        for d in r.details:
            log.error("   %s", d)
    ok = all_passed(results)
    write_report(results, hashes_before, hashes_after, strip_events, blocked=not ok)
    log.info("CHECKPOINT A: %s", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
