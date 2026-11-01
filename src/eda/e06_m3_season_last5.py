"""E6 — M3: relación estructural y redundancia season vs last5 (scope DEV_PREDICTORS).

PREDICTOR-ONLY (2021/22–2024/25): sin `result`, `goal_difference`, POST ni MARKET. No decide P02
(ventana) ni qué features usar. `sot_pg_last5` queda fuera: no existe `sot_pg_season`.

Poblaciones (siempre etiquetadas):
  A_DEVX_history  — todas las filas DEVX donde la tasa existe (lado: n_prev ≥ 1; diff: ambos ≥ 1).
  B_DEVX_eligible — filas con is_modeling_eligible = true (1,399).
Convención: delta = last5 − season (calculada solo en memoria; nunca se guarda en FEATURES).
Zonas:
  h/a:  identidad  n_prev ≤ 5  |  fuera de identidad  n_prev ≥ 6.
  diff: identidad garantizada si max(h_n, a_n) ≤ 5 (ambos lados idénticos) | mixta si exactamente un
        lado ≤ 5 | plenamente fuera si min(h_n, a_n) ≥ 6.
Sin aleatoriedad (no se genera la figura opcional de dispersión, que requeriría muestreo).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import GRID, INK, INK2, SURFACE, _style  # noqa: E402
from src.eda.e04_relationships import spearman  # noqa: E402
from src.eda.e05_m1_linear_dependence import standardize, svd_report  # noqa: E402

PHASE = "E6"
SCOPE = io.DEV_PREDICTORS
SCOPES = ["DEV_PREDICTORS"]
NOTES = ("E6 M3 predictor-only (DEVX 2021/22–2024/25): identidad season = last5 con n_prev ≤ 5, "
         "divergencia por historial, VIF season+last5; delta = last5 − season; sin targets; sin decidir P02; "
         "sin aleatoriedad (seed=null)")
EXPECTED_ELIGIBLE = 1399
TOL = 1e-12
METRICS = ("ppg", "gf_pg", "ga_pg")
SIDES = ("h", "a", "diff")
BINS_A = [(1, 5), (6, 10), (11, 20), (21, 37)]
BINS_B = [(3, 5), (6, 10), (11, 20), (21, 37)]
COL = {"ppg": "#2a78d6", "gf_pg": "#eb6834", "ga_pg": "#1baf7a"}


def load():
    df = io.load_features(SCOPE)
    assert not set(io.TARGET_COLUMNS) & set(df.columns)
    el = df["is_modeling_eligible"]
    if int(el.sum()) != EXPECTED_ELIGIBLE:
        raise RuntimeError(f"DEVX elegible = {int(el.sum())}, se esperaban {EXPECTED_ELIGIBLE}")
    df = df.copy()
    df["min_n_prev"] = df[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)
    df["max_n_prev"] = df[["h_n_prev_season", "a_n_prev_season"]].max(axis=1)
    return df


def pair(side, m):
    return f"{side}_{m}_season", f"{side}_{m}_last5"


def hist_var(df, side):
    """Historial usado para bins: lado propio para h/a; mínimo de ambos para diff."""
    return df[f"{side}_n_prev_season"] if side in ("h", "a") else df["min_n_prev"]


def population(df, side, name):
    has = (df["min_n_prev"] >= 1) if side == "diff" else (df[f"{side}_n_prev_season"] >= 1)
    if name == "A_DEVX_history":
        return df[has]
    return df[df["is_modeling_eligible"]]


def stats(s, l):
    d = l - s
    exact = (d.abs() <= TOL)
    q = d.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    out = {"n": int(len(d)), "exact_match_n": int(exact.sum()), "exact_match_pct": 100 * exact.mean() if len(d) else np.nan,
           "delta_mean": d.mean(), "delta_median": q[0.5], "delta_sd": d.std(ddof=1), "mae": d.abs().mean(),
           "rmse": float(np.sqrt((d ** 2).mean())), "delta_q1": q[0.25], "delta_q3": q[0.75], "delta_p5": q[0.05],
           "delta_p95": q[0.95], "max_abs_delta": d.abs().max()}
    if len(d) > 2 and s.std() > 0 and l.std() > 0:
        out["pearson"], out["spearman"] = s.corr(l), spearman(s, l)
    else:
        out["pearson"] = out["spearman"] = np.nan
    return out


# ---------------------------------------------------------------------------
def identity_table(df):
    rows = []
    A = df
    for m in METRICS:
        for side in ("h", "a"):
            s, l = pair(side, m)
            n = A[f"{side}_n_prev_season"]
            for zone, mask in (("n_prev 1–5 (identidad por construcción)", n.between(1, 5)),
                               ("n_prev ≥ 6 (control)", n >= 6)):
                d = (A.loc[mask, l] - A.loc[mask, s]).abs()
                rows.append({"population": "A_DEVX_history", "side": side, "metric": m, "season_feature": s,
                             "last5_feature": l, "condition": zone, "rows_evaluated": int(mask.sum()),
                             "rows_identical": int((d <= TOL).sum()), "pct_identical": 100 * (d <= TOL).mean(),
                             "max_abs_error": d.max(), "tolerance": TOL})
        s, l = pair("diff", m)
        hn, an = A["h_n_prev_season"], A["a_n_prev_season"]
        zones = (("ambos lados 1–5: max(h_n, a_n) ≤ 5 (identidad por construcción)", (A["min_n_prev"] >= 1) & (A["max_n_prev"] <= 5)),
                 ("un solo lado ≤ 5 (zona mixta; identidad no garantizada)", (A["min_n_prev"].between(1, 5)) & (A["max_n_prev"] >= 6)),
                 ("ambos lados ≥ 6: min(h_n, a_n) ≥ 6", A["min_n_prev"] >= 6))
        for zone, mask in zones:
            d = (A.loc[mask, l] - A.loc[mask, s]).abs()
            rows.append({"population": "A_DEVX_history", "side": "diff", "metric": m, "season_feature": s,
                         "last5_feature": l, "condition": zone, "rows_evaluated": int(mask.sum()),
                         "rows_identical": int((d <= TOL).sum()),
                         "pct_identical": 100 * (d <= TOL).mean() if mask.any() else np.nan,
                         "max_abs_error": d.max() if mask.any() else np.nan, "tolerance": TOL})
    return pd.DataFrame(rows)


def mixed_zone_detail(df):
    """Casos diff con un lado ≤ 5 y el otro ≥ 6 (documentación exigida en §6)."""
    mask = df["min_n_prev"].between(1, 5) & (df["max_n_prev"] >= 6)
    x = df.loc[mask, ["match_id", "season", "h_n_prev_season", "a_n_prev_season", "is_modeling_eligible"]].copy()
    for m in METRICS:
        s, l = pair("diff", m)
        x[f"{m}_diff_identical"] = (df.loc[mask, l] - df.loc[mask, s]).abs() <= TOL
    return x.reset_index(drop=True)


def overall(df):
    rows = []
    for popn in ("A_DEVX_history", "B_DEVX_eligible"):
        for side in SIDES:
            P = population(df, side, popn)
            h = hist_var(P, side)
            if side == "diff":
                zones = (("all", pd.Series(True, index=P.index)),
                         ("identity_zone: max(h_n, a_n) ≤ 5", P["max_n_prev"] <= 5),
                         ("out_of_identity: min(h_n, a_n) ≥ 6", P["min_n_prev"] >= 6))
            else:
                zones = (("all", pd.Series(True, index=P.index)), ("identity_zone: n_prev ≤ 5", h <= 5),
                         ("out_of_identity: n_prev ≥ 6", h >= 6))
            for m in METRICS:
                s, l = pair(side, m)
                for zone, mask in zones:
                    rows.append({"population": popn, "side": side, "metric": m, "zone": zone,
                                 **stats(P.loc[mask, s], P.loc[mask, l])})
    return pd.DataFrame(rows)


def by_history(df):
    rows = []
    for popn, bins in (("A_DEVX_history", BINS_A), ("B_DEVX_eligible", BINS_B)):
        for side in SIDES:
            P = population(df, side, popn)
            h = hist_var(P, side)
            for m in METRICS:
                s, l = pair(side, m)
                for a, b in bins:
                    mask = h.between(a, b)
                    st = stats(P.loc[mask, s], P.loc[mask, l])
                    rows.append({"population": popn, "side": side, "metric": m,
                                 "history_variable": "min_n_prev" if side == "diff" else f"{side}_n_prev_season",
                                 "history_bin": f"{a}–{b}", **{k: st[k] for k in ("n", "pearson", "spearman", "mae", "rmse",
                                 "exact_match_pct", "delta_sd", "delta_mean")}})
    return pd.DataFrame(rows)


def collinearity(df):
    E = df[df["is_modeling_eligible"]]
    reps = {"HA_season+last5": [c for side in ("h", "a") for m in METRICS for c in pair(side, m)],
            "DIFF_season+last5": [c for m in METRICS for c in pair("diff", m)]}
    subsets = {"B_eligible_all (n_prev ≥ 3)": E, "B_eligible min(h_n, a_n) ≥ 6": E[E["min_n_prev"] >= 6],
               "B_eligible min(h_n, a_n) ≥ 11": E[E["min_n_prev"] >= 11]}
    rows = []
    for sub_name, S in subsets.items():
        for rep, cols in reps.items():
            X = S[cols].to_numpy()
            r = svd_report(standardize(X))
            r.pop("singular_values")
            base = {"subset": sub_name, "representation": rep, "n_rows": len(S), "n_columns": len(cols),
                    "rank": r["rank"], "condition_number_standardized": r["condition_number_numeric"]}
            for j, col in enumerate(cols):
                y = X[:, j]
                Z = np.column_stack([np.ones(len(X)), np.delete(X, j, axis=1)])
                beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
                ratio = float(((y - Z @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum())
                rows.append({**base, "feature": col, "aux_r2": 1 - ratio, "vif": 1 / ratio})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def _save_figure(fig, filename):
    if not filename.endswith(f"{SCOPE.suffix}.png"):
        raise ValueError("La figura debe llevar el sufijo de su scope")
    path = io.EDA_FIGURES_DIR / filename
    io.assert_allowed_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return io.register_file(path, phase=PHASE, scope=SCOPE)


def _figure_by_history(bh, value, ylabel, title, note, ylim=None):
    d = bh[bh["population"] == "A_DEVX_history"]
    labels = [f"{a}–{b}" for a, b in BINS_A]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.0), facecolor=SURFACE, sharey=True)
    names = {"h": "h_ (local; historial h_n_prev)", "a": "a_ (visitante; historial a_n_prev)",
             "diff": "diff_ (historial min(h_n, a_n))"}
    for ax, side in zip(axes, SIDES):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for m in METRICS:
            t = d[(d["side"] == side) & (d["metric"] == m)].set_index("history_bin").loc[labels]
            ax.plot(range(4), t[value], color=COL[m], linewidth=2, marker="o", ms=7, mec=SURFACE, mew=1.5, label=m)
        ax.set_xticks(range(4), labels, fontsize=8.5, color=INK)
        ax.set_xlim(-0.3, 3.3)
        ax.set_title(names[side], loc="left", fontsize=9, color=INK)
        ax.set_xlabel("partidos previos en la temporada", color=INK2, fontsize=8.5)
        if ylim:
            ax.set_ylim(*ylim)
    axes[0].set_ylabel(ylabel, color=INK2, fontsize=9)
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=3, loc="upper left", bbox_to_anchor=(0.01, 0.93),
               frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle(title, x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, note, fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    df = load()
    ident = identity_table(df)
    bad = ident[ident["condition"].str.contains("identidad por construcción") & (ident["pct_identical"] < 100)]
    if len(bad):
        raise RuntimeError("E6: la identidad season = last5 no se cumple en su dominio; revisar antes de continuar")
    bh = by_history(df)
    tables = {
        "e06_identity_season_last5": ident,
        "e06_diff_mixed_zone_cases": mixed_zone_detail(df),
        "e06_season_last5_overall": overall(df),
        "e06_season_last5_by_history": bh,
        "e06_collinearity_season_last5": collinearity(df),
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=SCOPE, out_root=out_root) for name, t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(_figure_by_history(
            bh, "pearson", "Pearson season ↔ last5", "Correlación season ↔ last5 según historial disponible — DEVX (población A, n_prev ≥ 1)",
            "Tramo 1–5: idénticas por construcción (r = 1). Después dejan de ser idénticas. Correlación ≠ equivalencia. Sin targets.",
            ylim=(0, 1.05)), "e06_season_last5_correlation_by_history__DEVX.png"))
        outputs.append(_save_figure(_figure_by_history(
            bh, "mae", "MAE |last5 − season|", "Diferencia absoluta media entre last5 y season según historial — DEVX (población A)",
            "MAE = media de |last5 − season| en las unidades de cada métrica (puntos o goles por partido). Tramo 1–5: MAE = 0 por construcción."),
            "e06_season_last5_mae_by_history__DEVX.png"))
    return outputs, input_hashes, tables
