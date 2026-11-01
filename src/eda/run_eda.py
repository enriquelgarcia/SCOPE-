"""Orquestador del EDA de SCOPE v0.1.

Uso (desde la raíz de SCOPE/):  python -m src.eda.run_eda [FASE ...]
Fases disponibles: E1, E2, E2m, E3, E4, E5, E6, E7, E8, E9, E10, E11. Para ampliar: añadir la fase a PHASES.
"""
from __future__ import annotations

import sys

from src.eda import e01_structure_quality, e02_targets, e02m_market, e03_univariate, e04_relationships, e05_m1_linear_dependence, e06_m3_season_last5, e07_p01_burnin, e08_p02_last5, e09_q01_anomaly, e10_temporal_drift, e11_synthesis, eda_io as io

PHASES = {
    "E1": (e01_structure_quality, ["ALL_DESCRIPTIVE"],
           "E1 descriptivo; sin aleatoriedad; sin análisis target-aware"),
    "E2": (e02_targets, e02_targets.SCOPES, e02_targets.NOTES),
    "E2m": (e02m_market, e02m_market.SCOPES, e02m_market.NOTES),
    "E3": (e03_univariate, e03_univariate.SCOPES, e03_univariate.NOTES),
    "E4": (e04_relationships, e04_relationships.SCOPES, e04_relationships.NOTES),
    "E5": (e05_m1_linear_dependence, e05_m1_linear_dependence.SCOPES, e05_m1_linear_dependence.NOTES),
    "E6": (e06_m3_season_last5, e06_m3_season_last5.SCOPES, e06_m3_season_last5.NOTES),
    "E7": (e07_p01_burnin, e07_p01_burnin.SCOPES, e07_p01_burnin.NOTES),
    "E8": (e08_p02_last5, e08_p02_last5.SCOPES, e08_p02_last5.NOTES),
    "E9": (e09_q01_anomaly, e09_q01_anomaly.SCOPES, e09_q01_anomaly.NOTES),
    "E10": (e10_temporal_drift, e10_temporal_drift.SCOPES, e10_temporal_drift.NOTES),
    "E11": (e11_synthesis, e11_synthesis.SCOPES, e11_synthesis.NOTES),
}


def main(argv: list[str]) -> int:
    io.verify_frozen_inputs()                     # antes de cualquier análisis
    for phase in (argv or list(PHASES)):
        module, scopes, notes = PHASES[phase]
        outputs, hashes, _ = module.run()
        path = io.update_manifest(phase, scopes, hashes, outputs, seed=getattr(module, "SEED", None),
                                  notes=notes)
        print(f"{phase}: {len(outputs)} outputs; manifiesto {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
