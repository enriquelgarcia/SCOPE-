"""Resultado común de una comprobación de validación."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    check_id: str
    title: str
    passed: bool = True
    details: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def fail(self, message: str, limit: int = 50) -> None:
        self.passed = False
        if len(self.details) < limit:
            self.details.append(message)

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


def all_passed(results: list[CheckResult]) -> bool:
    return all(r.passed for r in results)
