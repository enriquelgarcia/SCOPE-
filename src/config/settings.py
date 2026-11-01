"""Configuración explícita de SCOPE v0.1 (CHECKPOINT A).

Todas las rutas se resuelven desde la raíz de SCOPE/ (contrato §14, D40).
"""
from __future__ import annotations

from pathlib import Path

CONTRACT_VERSION = "0.1"


def find_project_root(start: Path | None = None) -> Path:
    """Sube desde `start` hasta encontrar la raíz de SCOPE (contiene el contrato)."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "docs" / "contract" / "SCOPE_Data_Contract_v0.1.md").is_file():
            return candidate
    raise FileNotFoundError("No se encontró la raíz de SCOPE (docs/contract/SCOPE_Data_Contract_v0.1.md)")


PROJECT_ROOT = find_project_root()

# --- Documentos contractuales (solo lectura) ---
DOCS_DIR = PROJECT_ROOT / "docs"
MANIFEST_PATH = DOCS_DIR / "data_dictionary" / "raw_manifest_v0.1.csv"
RAW_DICTIONARY_PATH = DOCS_DIR / "data_dictionary" / "raw_dictionary_v0.1.csv"

# --- RAW (inmutable; nunca se escribe aquí) ---
RAW_DIR = PROJECT_ROOT / "Premier_League_data_raw_csv"
RAW_FILE_PATTERN = r"^PL_(\d{4})-(\d{4})_raw\.csv$"
READ_ONLY_DIRS = (RAW_DIR, PROJECT_ROOT / "Documentacion de datos", DOCS_DIR,
                  PROJECT_ROOT / "Premier_League_data_xlsx")

# --- Salidas generadas ---
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
INTERIM_FILE = INTERIM_DIR / "pl_interim_v0.1.csv"
REPORTS_DIR = PROJECT_ROOT / "reports" / "checkpoint_a"
REPORT_FILE = REPORTS_DIR / "checkpoint_a_validation_report.md"

# --- CHECKPOINT B: INTERIM aprobado -> CANONICAL ---
TEAM_MAPPING_PATH = DOCS_DIR / "data_dictionary" / "team_mapping_v0.1.csv"
INTERIM_APPROVED_SHA256 = "cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad"
CANONICAL_DIR = PROJECT_ROOT / "data" / "canonical"
CANONICAL_FILE = CANONICAL_DIR / "pl_canonical_v0.1.csv"
REPORTS_B_DIR = PROJECT_ROOT / "reports" / "checkpoint_b"
REPORT_B_FILE = REPORTS_B_DIR / "checkpoint_b_validation_report.md"
COMPETITION_CODE_MAP = {"E0": "EPL"}          # contrato §4.1
EXPECTED_TEAM_IDS = 27                        # D27
TEAMS_PER_SEASON = 20
DQ_FLAG_CATALOG = ("HST_GT_HS", "AST_GT_AS", "GOALS_GT_SOT")   # orden de catálogo (D33)

# --- CHECKPOINT C: CANONICAL aprobado -> team_match_log -> FEATURES ---
CANONICAL_APPROVED_SHA256 = "06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1"
TEAM_MATCH_LOG_FILE = PROJECT_ROOT / "data" / "interim" / "team_match_log_v0.1.csv"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"
FEATURES_FILE = FEATURES_DIR / "pl_features_v0.1.csv"
REPORTS_C_DIR = PROJECT_ROOT / "reports" / "checkpoint_c"
REPORT_C_FILE = REPORTS_C_DIR / "checkpoint_c_validation_report.md"
FEATURE_VERSION = "0.1"                       # contrato §5.3 (string)
ELIGIBILITY_THRESHOLD = 3                     # D48 — burn-in v0.1 aprobado (P01 cerrada)
LAST_N = 5                                    # ventana last5 (§5, P02)
EXPECTED_ELIGIBLE = {"2021-2022": 350, "2022-2023": 350, "2023-2024": 349,
                     "2024-2025": 350, "2025-2026": 350}            # V13
LEAKAGE_SEED = 42                             # V14/V15 (D37)
LEAKAGE_RANDOM_SAMPLE = 100                   # V14/V15 (D37)
ORACLE_TOLERANCE = 1e-9                       # V15

# --- Constantes del contrato ---
SOURCE_NAME = "football-data.co.uk"          # contrato §4.1
ROWS_PER_SEASON = 380
EXPECTED_SEASONS = 5
EXPECTED_UNION_COLUMNS = 162                 # contrato §2, §9
EXPECTED_COMMON_COLUMNS = 88                 # diccionario RAW §1

# Columnas de trazabilidad de INTERIM: se anteponen y se mantienen separadas de las
# 162 columnas RAW. Nombres y semántica tomados del contrato §4.1.
TRACE_COLUMNS = ("season", "source_name", "source_file", "source_row")

# Formatos temporales (contrato §4.0, D28)
RAW_DATE_FORMAT = "%d/%m/%Y"
RAW_TIME_FORMAT = "%H:%M"
ISO_DATE_FORMAT = "%Y-%m-%d"

NULL_LITERALS = ("NaN", "nan", "NA", "NULL", "None", "null")


def assert_writable_output(path: Path) -> None:
    """Impide escribir dentro de RAW, docs o documentación de la fuente."""
    resolved = path.resolve()
    for protected in READ_ONLY_DIRS:
        p = protected.resolve()
        if resolved == p or p in resolved.parents:
            raise PermissionError(f"Escritura prohibida en zona de solo lectura: {resolved}")
