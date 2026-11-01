"""E/S del EDA de SCOPE v0.1: integridad, carga tipada, scopes temporales y outputs auditables.

Reglas (fase E0 aprobada):
- Antes de analizar nada se verifican los cuatro SHA-256 congelados (D44). Ante cualquier
  discrepancia se ABORTA: nunca se regeneran artefactos desde el EDA.
- Los artefactos congelados son solo lectura; este módulo solo escribe en reports/eda/.
- Separación temporal explícita (D42 + política EDA refinada en E0):
    TRAIN / DESIGN  2021/22–2023/24  -> análisis target-aware que puede influir en decisiones
    VALIDATION      2024/25          -> sin uso de su target para decisiones
    FINAL TEST      2025/26          -> solo descripción (D42)
- Cada output lleva el sufijo de su scope y queda registrado en el manifiesto.
"""
from __future__ import annotations

import hashlib
import json
import platform
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import settings
from src.data import canonical_schema as CS
from src.data.canonical_schema import CANONICAL_SCHEMA
from src.data.features_schema import BOOL, FEATURES_SCHEMA, RATE_METRICS

# ---------------------------------------------------------------------------
# Entradas congeladas (D44)
# ---------------------------------------------------------------------------
INTERIM_FILE = settings.INTERIM_FILE
CANONICAL_FILE = settings.CANONICAL_FILE
TEAM_MATCH_LOG_FILE = settings.TEAM_MATCH_LOG_FILE
FEATURES_FILE = settings.FEATURES_FILE

FROZEN_SHA256: dict[str, str] = {
    "INTERIM": "cec123ceede88e1e1a37c1bdfd2651962f244c67f1e0e5e8adb561b1c7d543ad",
    "CANONICAL": "06bcacae7dbd8951d864ca0d3ea46adccceae77827e0ccc1e50a4d19fce84ee1",
    "TEAM_MATCH_LOG": "0032af2965604d556b337a5d8c1f4ce6b5ac95ca931d82b99651a4f00c03ab02",
    "FEATURES": "a18c47888a38a80585ae97930f81a4ad6fc4497315af63ef05f284352ca9b356",
}
FROZEN_PATHS: dict[str, Path] = {
    "INTERIM": INTERIM_FILE,
    "CANONICAL": CANONICAL_FILE,
    "TEAM_MATCH_LOG": TEAM_MATCH_LOG_FILE,
    "FEATURES": FEATURES_FILE,
}

# ---------------------------------------------------------------------------
# Temporadas y scopes
# ---------------------------------------------------------------------------
SEASONS_TRAIN_DESIGN = ("2021-2022", "2022-2023", "2023-2024")
SEASON_VALIDATION = "2024-2025"
SEASON_FINAL_TEST = "2025-2026"
SEASONS_DEV = SEASONS_TRAIN_DESIGN + (SEASON_VALIDATION,)
SEASONS_ALL = SEASONS_DEV + (SEASON_FINAL_TEST,)


@dataclass(frozen=True)
class Scope:
    name: str
    seasons: tuple[str, ...]
    suffix: str
    allows_target: bool        # ¿puede entregar targets / POST / MARKET?
    decision_use: str          # qué tipo de conclusiones admite


ALL_DESCRIPTIVE = Scope("ALL_DESCRIPTIVE", SEASONS_ALL, "__ALL", True,
                        "solo descripción/documentación; nunca justifica decisiones")
DEV_PREDICTORS = Scope("DEV_PREDICTORS", SEASONS_DEV, "__DEVX", False,
                       "decisiones basadas solo en predictors (sin target)")
TRAIN_TARGET = Scope("TRAIN_TARGET", SEASONS_TRAIN_DESIGN, "__TRAIN", True,
                     "decisiones target-aware")
VAL_DESCRIPTIVE = Scope("VAL_DESCRIPTIVE", (SEASON_VALIDATION,), "__VAL", True,
                        "solo descripción; su target no se usa para decisiones")
TEST_DESCRIPTIVE = Scope("TEST_DESCRIPTIVE", (SEASON_FINAL_TEST,), "__TEST", True,
                         "solo descripción (D42)")

SCOPES: dict[str, Scope] = {s.name: s for s in (ALL_DESCRIPTIVE, DEV_PREDICTORS, TRAIN_TARGET,
                                                VAL_DESCRIPTIVE, TEST_DESCRIPTIVE)}
SUFFIXES = tuple(s.suffix for s in SCOPES.values())

# ---------------------------------------------------------------------------
# Roles conceptuales de columnas (no se infieren del dtype de pandas)
# ---------------------------------------------------------------------------
CANONICAL_ROLES: dict[str, str] = {
    "match_id": "ID", "season": "ID",
    "competition_code": "AUX_CONSTANT", "source_name": "AUX_CONSTANT", "source_div": "AUX_CONSTANT",
    "source_file": "TRACE", "source_row": "TRACE",
    "match_date": "TIME", "kickoff_time": "TIME", "kickoff_datetime": "TIME",
    "match_seq_season": "AUX_ORDER",          # nunca frontera temporal (T5)
    "home_team_id": "TEAM", "away_team_id": "TEAM",
    "home_team_name": "TEAM_LABEL", "away_team_name": "TEAM_LABEL",
    "referee": "CONTEXT",
    "home_goals": "POST", "away_goals": "POST", "ht_home_goals": "POST", "ht_away_goals": "POST",
    "ht_result": "POST",
    **{c: "POST" for c in ("home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
                          "home_corners", "away_corners", "home_fouls", "away_fouls",
                          "home_yellow_cards", "away_yellow_cards", "home_red_cards", "away_red_cards")},
    "result": "TARGET", "goal_difference": "TARGET",
    **{f"mkt_avg_{w}_{o}": "MARKET" for w in ("pre", "close") for o in ("home", "draw", "away")},
    "dq_flags": "DQ",
}


def _feature_role(col: str) -> str:
    if col in ("match_id", "season"):
        return "ID"
    if col == "kickoff_datetime":
        return "TIME"
    if col.endswith("n_prev_season"):
        return "CONTROL_HISTORY"
    if col in ("result", "goal_difference"):
        return "TARGET"
    if col == "is_modeling_eligible":
        return "CONTROL_ELIGIBILITY"
    if col == "feature_version":
        return "AUX_VERSION"
    if col.startswith("diff_"):
        return "PREDICTOR_DIFF"
    return "PREDICTOR_SEASON" if col.endswith("_season") else "PREDICTOR_LAST5"


FEATURES_ROLES: dict[str, str] = {s.name: _feature_role(s.name) for s in FEATURES_SCHEMA}

TARGET_COLUMNS = ("result", "goal_difference")
FORBIDDEN_ROLES_DEVX = frozenset({"TARGET", "POST", "MARKET", "DQ"})

# Lista PERMITIDA (allow-list) para DEV_PREDICTORS: más segura que una lista de exclusión.
DEVX_FEATURES_COLUMNS: tuple[str, ...] = tuple(
    s.name for s in FEATURES_SCHEMA if FEATURES_ROLES[s.name] not in FORBIDDEN_ROLES_DEVX)
DEVX_CANONICAL_COLUMNS: tuple[str, ...] = (
    "match_id", "season", "kickoff_datetime", "home_team_id", "away_team_id")  # info pre-partido

HISTORY_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    [f"{p}_{m}" for p in ("h", "a") for m in RATE_METRICS] + [f"diff_{m}" for m in RATE_METRICS])

TML_COLUMNS: tuple[tuple[str, str], ...] = (
    ("match_id", CS.STRING), ("season", CS.STRING), ("kickoff_datetime", CS.DATETIME),
    ("team_id", CS.STRING), ("opponent_team_id", CS.STRING), ("is_home", BOOL),
    ("goals_for", CS.INT), ("goals_against", CS.INT), ("points", CS.INT),
    ("shots_on_target_for", CS.INT))

# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
class FrozenInputMismatch(RuntimeError):
    """Un artefacto congelado no coincide con su SHA-256 de D44: el EDA debe abortar."""


class ScopeViolation(RuntimeError):
    """Se pidió algo que el scope temporal no permite."""


# ---------------------------------------------------------------------------
# Integridad
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_frozen_inputs(paths: dict[str, Path] | None = None,
                         expected: dict[str, str] | None = None) -> dict[str, str]:
    """Verifica todos los artefactos; lanza FrozenInputMismatch listando TODAS las discrepancias."""
    paths = paths or FROZEN_PATHS
    expected = expected or FROZEN_SHA256
    found, errors = {}, []
    for key, exp in expected.items():
        p = paths[key]
        if not p.is_file():
            errors.append(f"{key}: archivo inexistente ({p})")
            continue
        found[key] = sha256_file(p)
        if found[key] != exp:
            errors.append(f"{key}: {found[key]} != {exp} ({p})")
    if errors:
        raise FrozenInputMismatch("ABORTAR EDA. Entradas congeladas alteradas: " + "; ".join(errors))
    return found


def _verified_bytes(key: str, path: Path | None = None, expected: str | None = None) -> bytes:
    path = path or FROZEN_PATHS[key]
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    exp = expected or FROZEN_SHA256[key]
    if digest != exp:
        raise FrozenInputMismatch(f"ABORTAR EDA. {key}: {digest} != {exp} ({path})")
    return data


# ---------------------------------------------------------------------------
# Carga tipada (tipos según el contrato, no según la inferencia de pandas)
# ---------------------------------------------------------------------------
def _typed_frame(data: bytes, spec: list[tuple[str, str, bool]]) -> pd.DataFrame:
    import io
    raw = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False, na_filter=False,
                      encoding="utf-8")
    expected_cols = [c for c, _, _ in spec]
    if list(raw.columns) != expected_cols:
        raise FrozenInputMismatch("Cabecera distinta del esquema esperado")
    out = {}
    for col, ltype, nullable in spec:
        s = raw[col]
        empty = s == ""
        if empty.any() and not nullable:
            raise ValueError(f"Valor vacío en columna no anulable {col}")
        s = s.mask(empty)
        if ltype == CS.INT:
            out[col] = pd.to_numeric(s, errors="raise").astype("Int64" if nullable else "int64")
        elif ltype == CS.FLOAT:
            out[col] = pd.to_numeric(s, errors="raise").astype("float64")
        elif ltype == BOOL:
            if not s.dropna().isin(["true", "false"]).all():
                raise ValueError(f"Booleano inválido en {col}")
            out[col] = s.map({"true": True, "false": False}).astype("bool" if not nullable else "boolean")
        elif ltype == CS.DATE:
            out[col] = pd.to_datetime(s, format="%Y-%m-%d", errors="raise")
        elif ltype == CS.DATETIME:
            out[col] = pd.to_datetime(s, format="%Y-%m-%dT%H:%M:%S", errors="raise")
        else:  # string, categorical, time -> texto
            out[col] = s.astype("string")
    return pd.DataFrame(out)


def _filter_seasons(df: pd.DataFrame, scope: Scope) -> pd.DataFrame:
    out = df[df["season"].isin(scope.seasons)].reset_index(drop=True)
    if set(out["season"].unique()) != set(scope.seasons):
        raise ScopeViolation(f"{scope.name}: faltan temporadas esperadas")
    return out


def _as_scope(scope: Scope | str) -> Scope:
    return SCOPES[scope] if isinstance(scope, str) else scope


def load_canonical(scope: Scope | str, *, path: Path | None = None,
                   expected_sha256: str | None = None) -> pd.DataFrame:
    scope = _as_scope(scope)
    data = _verified_bytes("CANONICAL", path, expected_sha256)
    df = _filter_seasons(_typed_frame(data, [(s.name, s.logical_type, s.nullable)
                                             for s in CANONICAL_SCHEMA]), scope)
    if not scope.allows_target:
        df = df.loc[:, list(DEVX_CANONICAL_COLUMNS)]
    return df


def load_features(scope: Scope | str, *, path: Path | None = None,
                  expected_sha256: str | None = None) -> pd.DataFrame:
    scope = _as_scope(scope)
    data = _verified_bytes("FEATURES", path, expected_sha256)
    df = _filter_seasons(_typed_frame(data, [(s.name, s.logical_type, s.nullable)
                                             for s in FEATURES_SCHEMA]), scope)
    if not scope.allows_target:
        df = df.loc[:, list(DEVX_FEATURES_COLUMNS)]
    return df


def load_team_match_log(scope: Scope | str, *, path: Path | None = None,
                        expected_sha256: str | None = None) -> pd.DataFrame:
    scope = _as_scope(scope)
    if not scope.allows_target:
        # goals_for/goals_against/points/shots_on_target_for son hechos POST de cada partido.
        raise ScopeViolation("team_match_log contiene hechos POST: no disponible en DEV_PREDICTORS")
    data = _verified_bytes("TEAM_MATCH_LOG", path, expected_sha256)
    return _filter_seasons(_typed_frame(data, [(c, t, False) for c, t in TML_COLUMNS]), scope)


def assert_scope_columns(df: pd.DataFrame, scope: Scope | str) -> None:
    """Comprobación defensiva para cualquier tabla antes de escribirla."""
    scope = _as_scope(scope)
    if "season" in df.columns:
        extra = set(df["season"].dropna().unique()) - set(scope.seasons) - {"ALL"}
        if extra:
            raise ScopeViolation(f"{scope.name}: temporadas fuera de scope {sorted(extra)}")
    if not scope.allows_target:
        bad = [c for c in df.columns
               if CANONICAL_ROLES.get(c) in FORBIDDEN_ROLES_DEVX or FEATURES_ROLES.get(c) in FORBIDDEN_ROLES_DEVX]
        if bad:
            raise ScopeViolation(f"{scope.name}: columnas prohibidas {bad}")


# ---------------------------------------------------------------------------
# Outputs y manifiesto
# ---------------------------------------------------------------------------
EDA_REPORTS_DIR = settings.PROJECT_ROOT / "reports" / "eda"
EDA_TABLES_DIR = EDA_REPORTS_DIR / "tables"
EDA_FIGURES_DIR = EDA_REPORTS_DIR / "figures"
MANIFEST_FILE = EDA_REPORTS_DIR / "eda_run_manifest.json"


@dataclass(frozen=True)
class OutputRecord:
    path: str          # relativo a la raíz de SCOPE
    phase: str
    scope: str
    sha256: str
    rows: int | None = None


def assert_allowed_output(path: Path) -> Path:
    """Regla única de destinos del EDA (whitelist). Se evalúa ANTES de crear carpetas o escribir.

    - dentro de SCOPE/: solo se permite escribir bajo reports/eda/;
    - fuera de SCOPE/: solo bajo el directorio temporal del sistema (tests con tempfile);
    - cualquier otro destino -> PermissionError.
    Como los artefactos congelados, data/, docs/, src/, tests/, RAW y .obsidian/ están dentro de
    SCOPE/ y fuera de reports/eda/, quedan rechazados por la propia regla (no hace falta blacklist).
    """
    rp = Path(path).resolve()
    root = settings.PROJECT_ROOT.resolve()
    if rp == root or root in rp.parents:
        if EDA_REPORTS_DIR.resolve() not in rp.parents:
            raise PermissionError(f"Destino EDA no permitido dentro de SCOPE (solo reports/eda/): {rp}")
    elif Path(tempfile.gettempdir()).resolve() not in rp.parents:
        raise PermissionError(f"Destino EDA no permitido fuera de SCOPE (solo temporales): {rp}")
    return rp


def _rel(path: Path) -> str:
    root, rp = settings.PROJECT_ROOT.resolve(), path.resolve()
    return rp.relative_to(root).as_posix() if root in rp.parents else str(rp)


def write_table(df: pd.DataFrame, name: str, *, phase: str, scope: Scope | str,
                out_root: Path | None = None) -> OutputRecord:
    """Escribe <out_root>/tables/<name><sufijo_scope>.csv (UTF-8, LF) tras validar el scope."""
    scope = _as_scope(scope)
    if any(name.endswith(s) for s in SUFFIXES) or name.endswith(".csv") or "/" in name or "\\" in name:
        raise ValueError("El nombre no debe incluir sufijo de scope, extensión ni rutas")
    path = (out_root or EDA_REPORTS_DIR) / "tables" / f"{name}{scope.suffix}.csv"
    assert_allowed_output(path)                       # antes de mkdir / open / escribir
    assert_scope_columns(df, scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return OutputRecord(_rel(path), phase, scope.name, sha256_file(path), len(df))


def register_file(path: Path, *, phase: str, scope: Scope | str) -> OutputRecord:
    scope = _as_scope(scope)
    assert_allowed_output(path)
    return OutputRecord(_rel(path), phase, scope.name, sha256_file(path))


def update_manifest(phase: str, scopes: list[str], input_hashes: dict[str, str],
                    outputs: list[OutputRecord], seed: int | None = None,
                    notes: str = "", out_root: Path | None = None) -> Path:
    """Registra (o reemplaza) la entrada de una fase en <out_root>/eda_run_manifest.json."""
    manifest_path = (out_root or EDA_REPORTS_DIR) / MANIFEST_FILE.name
    assert_allowed_output(manifest_path)              # antes de leer/crear/escribir
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"project": "SCOPE", "eda_version": "0.1", "phases": {}}
    manifest["scope_definitions"] = {s.name: {"seasons": list(s.seasons), "suffix": s.suffix,
                                              "allows_target": s.allows_target,
                                              "decision_use": s.decision_use}
                                     for s in SCOPES.values()}
    manifest["phases"][phase] = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "input_sha256": input_hashes,
        "scopes": scopes,
        "seed": seed,
        "notes": notes,
        "outputs": [o.__dict__ for o in outputs],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")
    return manifest_path
