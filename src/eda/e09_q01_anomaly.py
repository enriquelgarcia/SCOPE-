"""E9 — Q01: anomalía AST > AS (tiros a puerta del visitante > tiros del visitante).

Caracteriza la anomalía y su propagación downstream SIN corregir nada:
  1. localiza todas las filas con AST > AS (y HST > HS) en CANONICAL y, de forma independiente,
     en los CSV RAW (lectura con la stdlib, sin el pipeline);
  2. traza el valor RAW → INTERIM → CANONICAL → team_match_log (dq_flags incluido);
  3. sigue el valor en la historia del equipo afectado y determina qué partidos posteriores lo
     contienen en la ventana de sot_pg_last5 (h_/a_ y diff_);
  4. sensibilidad diagnóstica EN MEMORIA. El par (AS, AST) es incompatible, pero la fila NO
     demuestra qué campo es erróneo. Dos reparaciones mínimas de un solo campo restauran AST ≤ AS:
       escenario A — AS asumido correcto, AST 9→8 (min(AST, AS)): cambia sot_pg_last5;
       escenario B — AST asumido correcto, AS 8→9 (max(AS, AST)): sot_pg_last5 no cambia, porque
                     la feature usa AST/HST y no AS/HS.
     Ninguno es el valor verdadero ni una corrección aprobada; no se acota el valor verdadero.
Scope ALL_DESCRIPTIVE (localización sobre el pipeline completo). No usa result, goal_difference
ni goles de ningún partido; is_modeling_eligible solo para contar filas. Nada se escribe en
RAW/INTERIM/CANONICAL/team_match_log/FEATURES: los únicos outputs son tablas bajo reports/eda/.
"""
from __future__ import annotations

import csv
import hashlib

import numpy as np
import pandas as pd

from src.config import settings
from src.eda import eda_io as io

PHASE = "E9"
SCOPES = ["ALL_DESCRIPTIVE"]
SEED = None
NOTES = ("E9 Q01 (AST > AS): localización y trazabilidad RAW→INTERIM→CANONICAL→team_match_log; "
         "propagación a sot_pg_last5 (h_/a_/diff_); sensibilidad en memoria con dos escenarios de un solo campo "
         "(A: AS correcto, AST 9→8; B: AST correcto, AS 8→9; campo erróneo desconocido); sin targets, sin modelado, sin escribir datos; sin aleatoriedad")
RAW_MANIFEST = settings.PROJECT_ROOT / "docs" / "data_dictionary" / "raw_manifest_v0.1.csv"
SRC = {"HS": "home_shots", "AS": "away_shots", "HST": "home_shots_on_target", "AST": "away_shots_on_target"}
WINDOW = settings.LAST_N                                   # 5 (D18/D20)


def data_split(season: str) -> str:
    if season in io.SEASONS_TRAIN_DESIGN:
        return "TRAIN"
    if season == io.SEASON_VALIDATION:
        return "VALIDATION"
    if season == io.SEASON_FINAL_TEST:
        return "FINAL_TEST"
    raise ValueError(season)


# ---------------------------------------------------------------------------
# RAW (solo lectura, independiente del pipeline)
def verify_raw() -> dict[str, str]:
    man = pd.read_csv(RAW_MANIFEST, dtype=str, keep_default_na=False)
    out = {}
    for r in man[man["role"] == "raw_data"].itertuples():
        h = hashlib.sha256((settings.PROJECT_ROOT / r.relative_path).read_bytes()).hexdigest()
        if h != r.sha256:
            raise RuntimeError(f"RAW alterado: {r.file_name}")
        out[r.file_name] = h
    return out


def read_raw(file_name: str) -> list[dict]:
    with open(settings.RAW_DIR / file_name, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def raw_scan(files) -> pd.DataFrame:
    rows = []
    for fn in files:
        for i, r in enumerate(read_raw(fn), start=1):        # source_row: base 1, sin cabecera
            v = {k: int(r[k]) for k in SRC}
            for code, sot, sh in (("AST_GT_AS", "AST", "AS"), ("HST_GT_HS", "HST", "HS")):
                if v[sot] > v[sh]:
                    rows.append({"source_file": fn, "source_row": i, "code": code, **{k: r[k] for k in SRC}})
    return pd.DataFrame(rows, columns=["source_file", "source_row", "code", *SRC])


# ---------------------------------------------------------------------------
def traceability(q, raw_row, interim_row, tml_rows, split):
    base = {"season": q["season"], "data_split": split}
    out = [{
        "layer": "RAW", "artifact": q["source_file"], "locator": f"source_row={q['source_row']}",
        "date": raw_row["Date"], "home_team": raw_row["HomeTeam"], "away_team": raw_row["AwayTeam"],
        **{k: int(raw_row[k]) for k in SRC}, "dq_flags": "(no existe en RAW)",
        "note": "valor fuente leído con csv de la stdlib, sin pipeline"}]
    out.append({
        "layer": "INTERIM", "artifact": io.INTERIM_FILE.name, "locator": f"source_file={q['source_file']}; source_row={q['source_row']}",
        "date": interim_row["Date"], "home_team": interim_row["HomeTeam"], "away_team": interim_row["AwayTeam"],
        **{k: int(interim_row[k]) for k in SRC}, "dq_flags": "(no existe en INTERIM)",
        "note": "shots idénticos a RAW (texto); Date tipada a ISO por interim_schema, mismo día"})
    out.append({
        "layer": "CANONICAL", "artifact": io.CANONICAL_FILE.name, "locator": f"match_id={q['match_id']}",
        "date": q["match_date"].strftime("%Y-%m-%d"), "home_team": q["home_team_name"], "away_team": q["away_team_name"],
        **{k: int(q[c]) for k, c in SRC.items()}, "dq_flags": q["dq_flags"],
        "note": "valor fuente conservado (D03); AST_GT_AS identifica la fila"})
    for t in tml_rows.itertuples():
        side = "away" if not t.is_home else "home"
        out.append({
            "layer": "team_match_log", "artifact": io.TEAM_MATCH_LOG_FILE.name,
            "locator": f"match_id={t.match_id}; team_id={t.team_id}",
            "date": t.kickoff_datetime.strftime("%Y-%m-%d"), "home_team": q["home_team_name"], "away_team": q["away_team_name"],
            "tml_team_id": t.team_id, "tml_is_home": bool(t.is_home), "tml_shots_on_target_for": int(t.shots_on_target_for),
            "tml_source_field": "AST" if side == "away" else "HST",
            "dq_flags": "(no existe en team_match_log)",
            "note": "fila del visitante: recibe AST" if side == "away" else "fila del local: recibe HST (sin anomalía)"})
    df = pd.DataFrame(out)
    df.insert(1, "season", base["season"])
    df.insert(2, "data_split", base["data_split"])
    for col in (*SRC, "tml_shots_on_target_for"):
        df[col] = df[col].astype("Int64")
    df["tml_is_home"] = df["tml_is_home"].astype("boolean")
    df["AST_minus_AS"] = df["AST"] - df["AS"]
    return df


def team_trajectory(tml, team_id, season, q_match_id, ast_value):
    """Historia cronológica del equipo y sot_pg_last5 recomputado (en memoria) con el valor AST dado."""
    e = tml[(tml["team_id"] == team_id) & (tml["season"] == season)].sort_values("kickoff_datetime").reset_index(drop=True)
    vals = e["shots_on_target_for"].astype(float).to_numpy().copy()
    p = int(np.flatnonzero(e["match_id"].to_numpy() == q_match_id)[0])
    vals[p] = ast_value
    sot = [np.mean(vals[max(0, i - WINDOW):i]) if i > 0 else np.nan for i in range(len(e))]   # shift(1)
    return e.assign(position=np.arange(1, len(e) + 1), sot_last5=sot), p


def propagation(feat, can, tml, q):
    team, season = q["away_team_id"], q["season"]
    obs, p = team_trajectory(tml, team, season, q["match_id"], q["away_shots_on_target"])
    rep, _ = team_trajectory(tml, team, season, q["match_id"], min(q["away_shots_on_target"], q["away_shots"]))
    f = feat.set_index("match_id")
    c = can.set_index("match_id")
    # comprobación: el recomputado observado reproduce FEATURES en todos los partidos del equipo
    side = np.where(obs["is_home"], "h", "a")
    feat_val = [f.loc[m, f"{s}_sot_pg_last5"] for m, s in zip(obs["match_id"], side)]
    np.testing.assert_allclose(np.asarray(feat_val, float), obs["sot_last5"].to_numpy(), rtol=0, atol=1e-12, equal_nan=True)
    in_win = [(p >= max(0, i - WINDOW)) and (p < i) for i in range(len(obs))]
    last = max([i for i, w in enumerate(in_win) if w], default=p)
    rows = []
    for i in range(p, min(last + 2, len(obs))):              # Q01, afectados y primer no afectado
        m, s = obs.loc[i, "match_id"], side[i]
        other = "a" if s == "h" else "h"
        role = ("partido Q01 (fuente)" if i == p else
                f"afectado {sum(in_win[:i + 1])}/{sum(in_win)}" if in_win[i] else "primer partido no afectado")
        d_obs = f.loc[m, "diff_sot_pg_last5"]
        sgn = 1.0 if s == "h" else -1.0
        rows.append({
            "role": role, "team_position_in_season": i + 1, "team_matches_in_season": len(obs),
            "match_id": m, "season": season, "data_split": data_split(season),
            "date": obs.loc[i, "kickoff_datetime"].strftime("%Y-%m-%d"),
            "home_team": c.loc[m, "home_team_name"], "away_team": c.loc[m, "away_team_name"],
            "affected_team_id": team, "affected_side": s,
            "affected_feature": f"{s}_sot_pg_last5", "n_prev": int(f.loc[m, f"{s}_n_prev_season"]),
            "window_positions": f"{max(1, i - WINDOW + 1)}–{i}" if i > 0 else "(vacía)",
            "q01_in_window": bool(in_win[i]),
            "sot_last5_observed": f.loc[m, f"{s}_sot_pg_last5"],
            "opponent_sot_last5": f.loc[m, f"{other}_sot_pg_last5"],
            "diff_sot_pg_last5_observed": d_obs,
            "diff_affected": bool(in_win[i]) and pd.notna(d_obs),
            "is_modeling_eligible": bool(f.loc[m, "is_modeling_eligible"]),
            "_rep": rep.loc[i, "sot_last5"], "_sgn": sgn,
        })
    # el resto de la temporada del equipo no cambia con la reparación mínima
    others = [i for i in range(len(obs)) if not in_win[i]]
    assert np.allclose(obs.loc[others, "sot_last5"], rep.loc[others, "sot_last5"], equal_nan=True)
    return pd.DataFrame(rows), obs, p


def sensitivity(prop, q):
    """Una fila por partido afectado y escenario. A: AS correcto (AST 9→8); B: AST correcto (AS 8→9)."""
    a = prop[prop["q01_in_window"]]
    ast, as_ = int(q["away_shots_on_target"]), int(q["away_shots"])
    scen = {
        "A": ("AS asumido correcto; AST reparado a min(AST, AS)", as_, min(ast, as_), a["_rep"].to_numpy()),
        # B: AST no cambia → la trayectoria de sot_pg_last5 es la observada (la feature no usa AS)
        "B": ("AST asumido correcto; AS reparado a max(AS, AST)", max(as_, ast), ast, a["sot_last5_observed"].to_numpy()),
    }
    parts = []
    for code, (assumption, as_s, ast_s, sot_s) in scen.items():
        out = pd.DataFrame({
            "scenario": code, "scenario_assumption": assumption,
            "match_id": a["match_id"].to_numpy(), "season": a["season"].to_numpy(), "data_split": a["data_split"].to_numpy(),
            "date": a["date"].to_numpy(), "affected_feature": a["affected_feature"].to_numpy(), "n_prev": a["n_prev"].to_numpy(),
            "AS_observed": as_, "AST_observed": ast, "AS_scenario": as_s, "AST_scenario": ast_s,
            "sot_last5_observed": a["sot_last5_observed"].to_numpy(), "sot_last5_scenario": sot_s,
        })
        out["delta_abs"] = out["sot_last5_scenario"] - out["sot_last5_observed"]
        out["delta_rel"] = out["delta_abs"] / out["sot_last5_observed"]
        out["diff_sot_pg_last5_observed"] = a["diff_sot_pg_last5_observed"].to_numpy()
        out["diff_sot_pg_last5_scenario"] = out["diff_sot_pg_last5_observed"] + a["_sgn"].to_numpy() * out["delta_abs"]
        out["diff_delta"] = out["diff_sot_pg_last5_scenario"] - out["diff_sot_pg_last5_observed"]
        parts.append(out)
    out = pd.concat(parts, ignore_index=True)
    assert (out.loc[out["scenario"] == "B", ["delta_abs", "diff_delta"]] == 0).all().all()
    out["scenario_note"] = ("diagnóstico en memoria condicionado a la asunción del escenario; el campo erróneo es "
                            "desconocido; no es el valor verdadero ni una corrección")
    return out


def impact_summary(can, feat, tml, raw_hits, prop, q):
    a = prop[prop["q01_in_window"]]
    split = data_split(q["season"])
    split_seasons = [s for s in io.SEASONS_ALL if data_split(s) == split]
    n_split = int(feat["season"].isin(split_seasons).sum())
    e_split = int(feat.loc[feat["season"].isin(split_seasons), "is_modeling_eligible"].sum())
    n_all, e_all = len(feat), int(feat["is_modeling_eligible"].sum())
    n_aff, e_aff = len(a), int(a["is_modeling_eligible"].sum())
    n_diff, e_diff = int(a["diff_affected"].sum()), int((a["diff_affected"] & a["is_modeling_eligible"]).sum())
    rows = [
        ("raw_rows_AST_GT_AS", int((raw_hits["code"] == "AST_GT_AS").sum()), "filas RAW (5 temporadas)", 1900),
        ("raw_rows_HST_GT_HS", int((raw_hits["code"] == "HST_GT_HS").sum()), "filas RAW (5 temporadas)", 1900),
        ("canonical_rows_AST_GT_AS", int((can["away_shots_on_target"] > can["away_shots"]).sum()), "partidos CANONICAL", n_all),
        ("canonical_rows_HST_GT_HS", int((can["home_shots_on_target"] > can["home_shots"]).sum()), "partidos CANONICAL", n_all),
        ("team_match_rows_with_anomalous_value", 1, "filas team_match_log", len(tml)),
        ("matches_h_or_a_sot_last5_affected", n_aff, "partidos totales", n_all),
        ("matches_h_or_a_sot_last5_affected_eligible", e_aff, "partidos elegibles (D48)", e_all),
        ("matches_h_or_a_sot_last5_affected_not_eligible", n_aff - e_aff, "partidos no elegibles", n_all - e_all),
        ("matches_diff_sot_last5_affected", n_diff, "partidos totales", n_all),
        ("matches_diff_sot_last5_affected_eligible", e_diff, "partidos elegibles (D48)", e_all),
        (f"matches_h_or_a_sot_last5_affected_in_{split}", n_aff, f"partidos {split}", n_split),
        (f"matches_h_or_a_sot_last5_affected_eligible_in_{split}", e_aff, f"partidos elegibles {split}", e_split),
        (f"matches_diff_sot_last5_affected_eligible_in_{split}", e_diff, f"partidos elegibles {split}", e_split),
    ]
    out = pd.DataFrame(rows, columns=["quantity", "count", "denominator_label", "denominator"])
    out["pct"] = 100 * out["count"] / out["denominator"]
    return out


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    raw_hashes = verify_raw()
    keep = ["match_id", "season", "source_file", "source_row", "match_date", "kickoff_datetime",
            "home_team_id", "away_team_id", "home_team_name", "away_team_name", *SRC.values(), "dq_flags"]
    can = io.load_canonical(io.ALL_DESCRIPTIVE)[keep]                    # sin result / goles
    feat = io.load_features(io.ALL_DESCRIPTIVE).drop(columns=list(io.TARGET_COLUMNS))
    tml = io.load_team_match_log(io.ALL_DESCRIPTIVE)[["match_id", "season", "kickoff_datetime", "team_id",
                                                     "opponent_team_id", "is_home", "shots_on_target_for"]]
    hits = can[can["away_shots_on_target"] > can["away_shots"]]
    assert len(hits) == 1 and not (can["home_shots_on_target"] > can["home_shots"]).any()
    q = hits.iloc[0]
    flagged = can[can["dq_flags"].fillna("").str.contains("AST_GT_AS")]
    assert list(flagged["match_id"]) == [q["match_id"]]

    raw_hits = raw_scan(sorted(raw_hashes))
    assert list(zip(raw_hits["source_file"], raw_hits["source_row"])) == [(q["source_file"], int(q["source_row"]))]
    raw_row = read_raw(q["source_file"])[int(q["source_row"]) - 1]
    interim = pd.read_csv(io.INTERIM_FILE, dtype=str, keep_default_na=False)
    irow = interim[(interim["source_file"] == q["source_file"]) & (interim["source_row"] == str(q["source_row"]))]
    assert len(irow) == 1
    irow = irow.iloc[0]
    for k in ("HomeTeam", "AwayTeam", *SRC):
        assert irow[k] == raw_row[k], k                                 # INTERIM == RAW, carácter a carácter
    # Date: INTERIM la tipa como fecha ISO (interim_schema: Date → DATE); mismo día, distinto formato
    assert pd.to_datetime(raw_row["Date"], format="%d/%m/%Y").strftime("%Y-%m-%d") == irow["Date"]
    for k, ccol in SRC.items():
        assert int(q[ccol]) == int(raw_row[k]), k                       # CANONICAL == RAW
    tq = tml[tml["match_id"] == q["match_id"]]
    assert len(tq) == 2
    away = tq[~tq["is_home"]].iloc[0]
    home = tq[tq["is_home"]].iloc[0]
    assert away["team_id"] == q["away_team_id"] and int(away["shots_on_target_for"]) == int(raw_row["AST"])
    assert home["team_id"] == q["home_team_id"] and int(home["shots_on_target_for"]) == int(raw_row["HST"])
    assert int((tml["match_id"].eq(q["match_id"]) & tml["shots_on_target_for"].eq(int(raw_row["AST"]))).sum()) == 1

    trace = traceability(q, raw_row, irow, tq.sort_values("is_home", ascending=False), data_split(q["season"]))
    prop, obs, p = propagation(feat, can, tml, q)
    # el propio partido Q01 no usa su valor: su ventana es vacía o anterior (shift(1))
    assert not prop.iloc[0]["q01_in_window"]
    sens = sensitivity(prop, q)
    summ = impact_summary(can, feat, tml, raw_hits, prop, q)
    prop_out = prop.drop(columns=["_rep", "_sgn"])
    tables = {
        "e09_q01_traceability": trace,
        "e09_q01_feature_propagation": prop_out,
        "e09_q01_minimal_repair_sensitivity": sens,
        "e09_q01_impact_summary": summ,
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=io.ALL_DESCRIPTIVE, out_root=out_root) for name, t in tables.items()]
    assert io.verify_frozen_inputs() == input_hashes and verify_raw() == raw_hashes
    return outputs, input_hashes, tables
