"""Informe de validación de CHECKPOINT A (Markdown, determinista: sin marcas de tiempo)."""
from __future__ import annotations

import hashlib

from src.config import settings
from src.validation.results import CheckResult


def write_report(results: list[CheckResult], hashes_before: dict[str, str],
                 hashes_after: dict[str, str], strip_events: list, blocked: bool) -> None:
    settings.assert_writable_output(settings.REPORT_FILE)
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# CHECKPOINT A — RAW → INTERIM: informe de validación", "",
             f"Contrato: SCOPE Data Contract v{settings.CONTRACT_VERSION} (FROZEN FOR IMPLEMENTATION)", ""]
    if settings.INTERIM_FILE.is_file():
        data = settings.INTERIM_FILE.read_bytes()
        rel = settings.INTERIM_FILE.relative_to(settings.PROJECT_ROOT).as_posix()
        lines += [f"Salida: `{rel}` — {len(data)} bytes — SHA-256 `{hashlib.sha256(data).hexdigest()}`", ""]
    lines += ["## Resultado por prueba", "", "| ID | Estado | Prueba |", "|---|---|---|"]
    lines += [f"| {r.check_id} | **{r.status}** | {r.title} |" for r in results]
    lines += ["", f"**Resultado global: {'FAIL' if blocked else 'PASS'}**", "", "## Detalle", ""]
    for r in results:
        lines.append(f"### {r.check_id} — {r.title} — {r.status}")
        lines += [f"- {x}" for x in r.info] + [f"- **FALLO:** {x}" for x in r.details] + [""]
    lines += ["## SHA-256 RAW antes / después", "", "| relative_path | antes | después | igual |", "|---|---|---|---|"]
    for k in sorted(hashes_before):
        a = hashes_after.get(k, "")
        lines.append(f"| `{k}` | `{hashes_before[k]}` | `{a}` | {'sí' if a == hashes_before[k] else 'no'} |")
    lines += ["", "## Limpieza superficial aplicada (strip)", ""]
    lines += [f"- `{e.source_file}` source_row={e.source_row} `{e.column}`: {e.raw_value!r} → {e.interim_value!r}"
              for e in strip_events] or ["- ninguna"]
    with open(settings.REPORT_FILE, "wb") as fh:
        fh.write(("\n".join(lines) + "\n").encode("utf-8"))


def write_report_b(results: list[CheckResult], hashes_before: dict[str, str], hashes_after: dict[str, str],
                   interim_sha: tuple[str, str], canonical_sha: str | None, blocked: bool) -> None:
    """Informe de CHECKPOINT B (INTERIM -> CANONICAL)."""
    path = settings.REPORT_B_FILE
    settings.assert_writable_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CHECKPOINT B — INTERIM → CANONICAL: informe de validación", "",
             f"Contrato: SCOPE Data Contract v{settings.CONTRACT_VERSION} (FROZEN FOR IMPLEMENTATION)", "",
             f"- INTERIM aprobado: `{settings.INTERIM_APPROVED_SHA256}`",
             f"- INTERIM antes / después: `{interim_sha[0]}` / `{interim_sha[1]}`"]
    if canonical_sha:
        rel = settings.CANONICAL_FILE.relative_to(settings.PROJECT_ROOT).as_posix()
        lines.append(f"- CANONICAL: `{rel}` — SHA-256 `{canonical_sha}`")
    lines += ["", "## Resultado por prueba", "", "| ID | Estado | Prueba |", "|---|---|---|"]
    lines += [f"| {r.check_id} | **{r.status}** | {r.title} |" for r in results]
    lines += ["", f"**Resultado global: {'FAIL' if blocked else 'PASS'}**", "", "## Detalle", ""]
    for r in results:
        lines.append(f"### {r.check_id} — {r.title} — {r.status}")
        lines += [f"- {x}" for x in r.info] + [f"- **FALLO:** {x}" for x in r.details] + [""]
    lines += ["## SHA-256 RAW antes / después", "", "| relative_path | antes | después | igual |",
              "|---|---|---|---|"]
    for k in sorted(hashes_before):
        a = hashes_after.get(k, "")
        lines.append(f"| `{k}` | `{hashes_before[k]}` | `{a}` | {'sí' if a == hashes_before[k] else 'no'} |")
    with open(path, "wb") as fh:
        fh.write(("\n".join(lines) + "\n").encode("utf-8"))


def write_report_generic(path, title: str, preamble: list[str], results: list[CheckResult],
                         hashes_before: dict[str, str], hashes_after: dict[str, str], blocked: bool) -> None:
    """Informe Markdown determinista (usado por CHECKPOINT C)."""
    settings.assert_writable_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", f"Contrato: SCOPE Data Contract v{settings.CONTRACT_VERSION} "
             "(FROZEN FOR IMPLEMENTATION)", "", *preamble, "",
             "## Resultado por prueba", "", "| ID | Estado | Prueba |", "|---|---|---|"]
    lines += [f"| {r.check_id} | **{r.status}** | {r.title} |" for r in results]
    lines += ["", f"**Resultado global: {'FAIL' if blocked else 'PASS'}**", "", "## Detalle", ""]
    for r in results:
        lines.append(f"### {r.check_id} — {r.title} — {r.status}")
        lines += [f"- {x}" for x in r.info] + [f"- **FALLO:** {x}" for x in r.details] + [""]
    lines += ["## SHA-256 RAW antes / después", "", "| relative_path | antes | después | igual |",
              "|---|---|---|---|"]
    for k in sorted(hashes_before):
        a = hashes_after.get(k, "")
        lines.append(f"| `{k}` | `{hashes_before[k]}` | `{a}` | {'sí' if a == hashes_before[k] else 'no'} |")
    with open(path, "wb") as fh:
        fh.write(("\n".join(lines) + "\n").encode("utf-8"))
