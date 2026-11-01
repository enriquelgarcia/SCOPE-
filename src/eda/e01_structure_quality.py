"""E1 — Estructura, calidad y elegibilidad (scope ALL_DESCRIPTIVE).

Fase descriptiva: documenta el estado de los datos que consumirá el EDA.
NO analiza el target (sin distribuciones H/D/A ni goles), NO calcula correlaciones,
NO decide burn-in (P01), ventanas (P02), M1 ni M3.
"""
from __future__ import annotations

import pandas as pd

from src.config import settings
from src.data.canonical_schema import CANONICAL_SCHEMA
from src.data.features_schema import FEATURES_SCHEMA, RATE_METRICS
from src.eda import eda_io as io

PHASE = "E1"
SCOPE = io.ALL_DESCRIPTIVE
HISTORY_LEVELS = ("0", "1", "2", "3", "4", "5", "6+")
EXPECTED_DIMS = {"CANONICAL": (1900, 42), "FEATURES": (1900, 30), "TEAM_MATCH_LOG": (3800, 10)}


def _level(n: pd.Series) -> pd.Series:
    return n.clip(upper=6).astype(int).astype(str).replace("6", "6+")


# ---------------------------------------------------------------------------
def schema_missingness(can: pd.DataFrame, feat: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dataset, df, schema, roles in (("CANONICAL", can, CANONICAL_SCHEMA, io.CANONICAL_ROLES),
                                       ("FEATURES", feat, FEATURES_SCHEMA, io.FEATURES_ROLES)):
        for pos, spec in enumerate(schema, start=1):
            s = df[spec.name]
            nn = int(s.notna().sum())
            role = roles[spec.name]
            rows.append({
                "dataset": dataset, "position": pos, "column": spec.name,
                "contract_logical_type": spec.logical_type, "contract_nullable": spec.nullable,
                "physical_dtype": str(s.dtype), "conceptual_role": role,
                "non_null_count": nn, "null_count": int(len(s) - nn),
                "null_pct": round(100 * (len(s) - nn) / len(s), 4),
                "n_unique": int(s.nunique(dropna=True)),
            })
    return pd.DataFrame(rows)


def features_missingness_by_history(feat: pd.DataFrame) -> pd.DataFrame:
    """Nulos de cada feature histórica según la temporada y el historial de su lado.

    h_* se estratifica por h_n_prev_season, a_* por a_n_prev_season y diff_* por el mínimo
    de ambos (diff es nulo si cualquiera de los dos lados lo es)."""
    mn = feat[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)
    rows = []
    for col in io.HISTORY_FEATURE_COLUMNS:
        side = col.split("_", 1)[0]
        hist_name, hist = {"h": ("h_n_prev_season", feat["h_n_prev_season"]),
                           "a": ("a_n_prev_season", feat["a_n_prev_season"]),
                           "diff": ("min_n_prev_season", mn)}[side]
        grp = hist.eq(0).map({True: "0", False: ">=1"})
        for (season, g), idx in feat.groupby([feat["season"], grp]).groups.items():
            s = feat.loc[idx, col]
            rows.append({"column": col, "season": season, "history_variable": hist_name,
                         "history_group": g, "n_rows": len(s), "null_count": int(s.isna().sum()),
                         "null_pct": round(100 * s.isna().mean(), 4)})
    return pd.DataFrame(rows).sort_values(["column", "season", "history_group"]).reset_index(drop=True)


def history_eligibility(feat: pd.DataFrame) -> pd.DataFrame:
    hist = {"h_n_prev_season": feat["h_n_prev_season"], "a_n_prev_season": feat["a_n_prev_season"],
            "min_n_prev_season": feat[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)}
    rows = []
    for var, n in hist.items():
        lvl = _level(n)
        for season in list(io.SEASONS_ALL) + ["ALL"]:
            m = feat["season"].eq(season) if season != "ALL" else pd.Series(True, index=feat.index)
            for level in HISTORY_LEVELS:
                sel = m & lvl.eq(level)
                el = int(feat.loc[sel, "is_modeling_eligible"].sum())
                rows.append({"history_variable": var, "season": season, "history_level": level,
                             "n_matches": int(sel.sum()), "eligible": el, "not_eligible": int(sel.sum()) - el})
    return pd.DataFrame(rows)


def dq_flagged_rows(can: pd.DataFrame) -> pd.DataFrame:
    f = can[can["dq_flags"].notna()]
    out = f[["match_id", "season", "source_file", "source_row", "match_date", "home_team_id",
             "away_team_id", "dq_flags", "home_shots", "home_shots_on_target", "away_shots",
             "away_shots_on_target", "home_goals", "away_goals"]].copy()
    out["match_date"] = out["match_date"].dt.strftime("%Y-%m-%d")
    return out.sort_values(["season", "source_row"]).reset_index(drop=True)


def quality_summary(can, feat, tml, input_hashes) -> pd.DataFrame:
    R = []

    def add(section, metric, value, season="ALL", expected=None, note=""):
        if expected is None:
            status = "INFO"
        else:
            status = "PASS" if str(value) == str(expected) else "FAIL"
        R.append({"section": section, "metric": metric, "season": season, "value": value,
                  "expected": "" if expected is None else expected, "status": status, "note": note})

    for key, h in input_hashes.items():
        add("integrity", f"sha256_{key}", h, expected=io.FROZEN_SHA256[key], note="D44")
    for name, df in (("CANONICAL", can), ("FEATURES", feat), ("TEAM_MATCH_LOG", tml)):
        add("dimensions", f"{name}_rows", df.shape[0], expected=EXPECTED_DIMS[name][0])
        add("dimensions", f"{name}_columns", df.shape[1], expected=EXPECTED_DIMS[name][1])

    # Alineación entre artefactos (sin mirar el target)
    add("alignment", "features_match_id_equals_canonical_row_by_row",
        bool((can["match_id"].values == feat["match_id"].values).all()), expected=True)
    add("alignment", "tml_rows_equal_2x_canonical", len(tml) == 2 * len(can), expected=True)
    add("alignment", "match_id_unique_canonical", bool(can["match_id"].is_unique), expected=True)

    # Cardinalidades
    add("cardinality", "seasons", can["season"].nunique(), expected=5)
    teams = pd.concat([can["home_team_id"], can["away_team_id"]])
    add("cardinality", "team_id_distinct", teams.nunique(), expected=27, note="D27")
    add("cardinality", "referees_distinct", can["referee"].nunique(), note="sin análisis de efecto")
    for season, g in can.groupby("season"):
        add("cardinality", "matches", len(g), season=season, expected=380)
        add("cardinality", "teams", pd.concat([g["home_team_id"], g["away_team_id"]]).nunique(),
            season=season, expected=20)
        add("cardinality", "referees_distinct", g["referee"].nunique(), season=season)
        add("cardinality", "kickoff_min", g["kickoff_datetime"].min().isoformat(), season=season)
        add("cardinality", "kickoff_max", g["kickoff_datetime"].max().isoformat(), season=season)
    for season, g in feat.groupby("season"):
        add("cardinality", "features_rows", len(g), season=season, expected=380)
    # Equipos que entran/salen respecto a la temporada anterior (ascensos/descensos)
    prev = None
    for season in io.SEASONS_ALL:
        g = can[can["season"] == season]
        cur = set(g["home_team_id"])
        if prev is not None:
            add("cardinality", "teams_new_vs_previous_season", len(cur - prev), season=season,
                note=",".join(sorted(cur - prev)))
        prev = cur

    # Constantes / auxiliares
    for col in ("competition_code", "source_name", "source_div"):
        vals = sorted(can[col].unique())
        add("constants", f"{col}_n_unique", len(vals), expected=1, note=f"valor={vals}")
    vals = sorted(feat["feature_version"].unique())
    add("constants", "feature_version_n_unique", len(vals), expected=1, note=f"valor={vals}")
    add("constants", "feature_version_value", vals[0] if len(vals) == 1 else vals, expected="0.1",
        note="string")

    # dq_flags
    flags = can["dq_flags"].dropna().str.split("|").explode()
    add("dq_flags", "rows_without_flags", int(can["dq_flags"].isna().sum()), expected=1887)
    add("dq_flags", "rows_with_flags", int(can["dq_flags"].notna().sum()), expected=13)
    for code, exp in (("HST_GT_HS", 0), ("AST_GT_AS", 1), ("GOALS_GT_SOT", 12)):
        add("dq_flags", f"count_{code}", int((flags == code).sum()), expected=exp, note="registro de calidad §1")
        for season in io.SEASONS_ALL:
            n = int(can.loc[can["season"] == season, "dq_flags"].fillna("").str.split("|")
                    .apply(lambda xs: code in xs).sum())
            add("dq_flags", f"count_{code}", n, season=season)
    add("dq_flags", "rows_with_multiple_flags", int(can["dq_flags"].dropna().str.contains(r"\|").sum()))
    # Recalculo independiente (descriptivo) de cada condición sobre los valores
    add("dq_flags", "recomputed_AST_GT_AS",
        int((can["away_shots_on_target"] > can["away_shots"]).sum()), expected=1)
    add("dq_flags", "recomputed_HST_GT_HS",
        int((can["home_shots_on_target"] > can["home_shots"]).sum()), expected=0)
    add("dq_flags", "recomputed_GOALS_GT_SOT",
        int(((can["home_goals"] > can["home_shots_on_target"]) |
             (can["away_goals"] > can["away_shots_on_target"])).sum()), expected=12)

    # Missingness: regla nulo <=> n_prev = 0
    for side in ("h", "a"):
        zero = feat[f"{side}_n_prev_season"].eq(0)
        cols = [f"{side}_{m}" for m in RATE_METRICS]
        isna = feat[cols].isna()
        add("missingness", f"{side}_rows_n_prev_0", int(zero.sum()), expected=50)
        add("missingness", f"{side}_all_rate_features_null_when_n_prev_0",
            bool(isna[zero].all(axis=None)), expected=True)
        add("missingness", f"{side}_no_rate_feature_null_when_n_prev_ge_1",
            bool(~isna[~zero].any(axis=None)), expected=True)
    either = feat[["h_n_prev_season", "a_n_prev_season"]].min(axis=1).eq(0)
    dna = feat[[f"diff_{m}" for m in RATE_METRICS]].isna()
    add("missingness", "rows_min_n_prev_0", int(either.sum()), expected=50,
        note="las filas con n_prev=0 coinciden en ambos lados: 10 partidos inaugurales por temporada")
    add("missingness", "rows_both_n_prev_0",
        int((feat["h_n_prev_season"].eq(0) & feat["a_n_prev_season"].eq(0)).sum()), expected=50)
    add("missingness", "diff_null_iff_min_n_prev_0",
        bool(dna[either].all(axis=None) and not dna[~either].any(axis=None)), expected=True)
    nonhist = [c for c in feat.columns if c not in io.HISTORY_FEATURE_COLUMNS]
    add("missingness", "features_nonhistory_columns_with_nulls", int(feat[nonhist].isna().any().sum()), expected=0)
    add("missingness", "canonical_columns_with_nulls_except_dq_flags",
        int(can.drop(columns=["dq_flags"]).isna().any().sum()), expected=0)

    # Historial
    for side in ("h", "a"):
        n = feat[f"{side}_n_prev_season"]
        add("history", f"{side}_n_prev_season_min", int(n.min()), expected=0)
        add("history", f"{side}_n_prev_season_max", int(n.max()), expected=37, note="V12")
    gap = (feat["h_n_prev_season"] - feat["a_n_prev_season"]).abs()
    add("history", "max_abs_h_minus_a_n_prev", int(gap.max()),
        note="desfase de calendario entre local y visitante (aplazamientos)")
    for season, g in feat.assign(gap=gap).groupby("season"):
        add("history", "max_abs_h_minus_a_n_prev", int(g["gap"].max()), season=season)
        add("history", "rows_abs_h_minus_a_n_prev_ge_2", int((g["gap"] >= 2).sum()), season=season)

    # Elegibilidad
    mn = feat[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)
    rule = mn >= settings.ELIGIBILITY_THRESHOLD
    add("eligibility", "rule_min_n_prev_ge_3_equals_flag",
        bool((rule == feat["is_modeling_eligible"]).all()), expected=True, note="P01 provisional")
    add("eligibility", "eligible", int(feat["is_modeling_eligible"].sum()), expected=1749)
    add("eligibility", "not_eligible", int((~feat["is_modeling_eligible"]).sum()), expected=151)
    for season, g in feat.groupby("season"):
        add("eligibility", "eligible", int(g["is_modeling_eligible"].sum()), season=season,
            expected=settings.EXPECTED_ELIGIBLE[season])
        add("eligibility", "not_eligible", int((~g["is_modeling_eligible"]).sum()), season=season)
    el = feat[feat["is_modeling_eligible"]]
    add("eligibility", "eligible_rows_with_null_history_features",
        int(el[list(io.HISTORY_FEATURE_COLUMNS)].isna().any(axis=1).sum()), expected=0, note="V13")
    el_mn = el[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)
    add("eligibility", "eligible_rows_min_n_prev_le_5", int((el_mn <= 5).sum()),
        note="zona donde last5 == season al menos para un lado (M3)")
    add("eligibility", "eligible_rows_both_n_prev_le_5",
        int((el[["h_n_prev_season", "a_n_prev_season"]].max(axis=1) <= 5).sum()))
    # Elegibilidad no monótona en el tiempo: filas no elegibles después de la primera elegible
    late = 0
    for season, g in feat.sort_values(["kickoff_datetime", "match_id"]).groupby("season"):
        first_el = g.loc[g["is_modeling_eligible"], "kickoff_datetime"].min()
        late_s = int(((~g["is_modeling_eligible"]) & (g["kickoff_datetime"] > first_el)).sum())
        late += late_s
        add("eligibility", "not_eligible_after_first_eligible_kickoff", late_s, season=season,
            note="no elegibles por aplazamientos, no solo por estar al inicio")
    add("eligibility", "not_eligible_after_first_eligible_kickoff", late)
    return pd.DataFrame(R)


# ---------------------------------------------------------------------------
def run(out_root=None) -> tuple[list[io.OutputRecord], dict, dict]:
    input_hashes = io.verify_frozen_inputs()          # ABORTA ante cualquier discrepancia
    can = io.load_canonical(SCOPE)
    feat = io.load_features(SCOPE)
    tml = io.load_team_match_log(SCOPE)

    tables = {
        "e01_schema_missingness": schema_missingness(can, feat),
        "e01_features_missingness_by_history": features_missingness_by_history(feat),
        "e01_history_eligibility": history_eligibility(feat),
        "e01_quality_summary": quality_summary(can, feat, tml, input_hashes),
        "e01_dq_flagged_rows": dq_flagged_rows(can),
    }
    outputs = [io.write_table(df, name, phase=PHASE, scope=SCOPE, out_root=out_root)
               for name, df in tables.items()]
    return outputs, input_hashes, tables


if __name__ == "__main__":
    outs, _, t = run()
    qs = t["e01_quality_summary"]
    print(qs["status"].value_counts().to_dict())
    print(qs[qs["status"] == "FAIL"].to_string())
    for o in outs:
        print(o)
