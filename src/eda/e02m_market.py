"""E2m — Caracterización del benchmark de mercado 1X2 (scope ALL_DESCRIPTIVE).

Estrategia C (contrato §10, D12, D13, D39): el mercado es un BENCHMARK EXTERNO.
- Las cuotas NO son features ni predictors y no se usan para seleccionar nada.
- Pre (`mkt_avg_pre_*`, AvgH/D/A) = benchmark principal; close (`mkt_avg_close_*`, AvgCH/CD/CA) =
  secundario. No se supone que close tenga la misma información temporal que una predicción.
- Conversión D39: q_i = 1/o_i; p_i = q_i / Σ q_j; Σ p = 1 con tolerancia 1e-9. Las probabilidades
  se calculan EN MEMORIA y solo se escriben resúmenes en reports/eda/ (nunca en CANONICAL/FEATURES).
- Sin target: no se usa `result`; no hay accuracy, log loss, Brier, calibración, ROI ni comparación
  con SCOPE. Sin aleatoriedad.

Convención de tablas: `level = season` por temporada; `level = scope_total` (season = "ALL") es el
agregado de las 5 temporadas.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import COLOR, GRID, INK, INK2, SURFACE, _style  # noqa: E402  (estilo común)

PHASE = "E2m"
SCOPE = io.ALL_DESCRIPTIVE
SCOPES = ["ALL_DESCRIPTIVE"]
NOTES = ("E2m descriptivo del benchmark de mercado 1X2; cuotas no son predictors; sin target, sin "
         "accuracy/log loss/Brier/calibración; sin aleatoriedad (seed=null)")
TOL = 1e-9
OUTCOMES = ("H", "D", "A")
WINDOWS = ("pre", "close")
ODDS = {(w, o): f"mkt_avg_{w}_{n}" for w in WINDOWS for o, n in zip(OUTCOMES, ("home", "draw", "away"))}
WINDOW_COLOR = {"pre": "#2a78d6", "close": "#eb6834"}   # slots categóricos 1–2 (validados)


def market_frame() -> pd.DataFrame:
    """Cuotas + derivados en memoria (q crudas, overround, p normalizadas, movimiento)."""
    can = io.load_canonical(SCOPE)
    df = can.loc[:, ["match_id", "season", *ODDS.values()]].copy()
    for w in WINDOWS:
        for o in OUTCOMES:
            df[f"q_{w}_{o}"] = 1.0 / df[ODDS[(w, o)]]
        df[f"sum_q_{w}"] = df[[f"q_{w}_{o}" for o in OUTCOMES]].sum(axis=1)
        df[f"overround_{w}"] = df[f"sum_q_{w}"] - 1.0
        for o in OUTCOMES:
            df[f"p_{w}_{o}"] = df[f"q_{w}_{o}"] / df[f"sum_q_{w}"]
        df[f"sum_p_{w}"] = df[[f"p_{w}_{o}" for o in OUTCOMES]].sum(axis=1)
    for o in OUTCOMES:
        df[f"delta_p_{o}"] = df[f"p_close_{o}"] - df[f"p_pre_{o}"]
    df["market_move_L1"] = df[[f"delta_p_{o}" for o in OUTCOMES]].abs().sum(axis=1)
    return df


def _levels(df):
    for season, g in df.groupby("season", sort=True):
        yield "season", season, g
    yield "scope_total", "ALL", df


def _stats(s: pd.Series) -> dict:
    q = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {"n": int(s.size), "mean": s.mean(), "median": q[0.5], "std": s.std(ddof=1),
            "min": s.min(), "q05": q[0.05], "q25": q[0.25], "q75": q[0.75], "q95": q[0.95],
            "iqr": q[0.75] - q[0.25], "max": s.max()}


# ---------------------------------------------------------------------------
def market_integrity(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (w, o), col in ODDS.items():
        s = df[col]
        rows.append({"check": "odds_column", "column": col, "window": w, "outcome": o,
                     "n_rows": len(s), "null_count": int(s.isna().sum()), "min": s.min(), "max": s.max(),
                     "n_le_1": int((s <= 1.0).sum()), "status": "PASS" if (s.notna().all() and (s > 1).all()) else "FAIL"})
    for w in WINDOWS:
        dev = (df[f"sum_p_{w}"] - 1.0).abs()
        rows.append({"check": "sum_p_equals_1_tol_1e-9", "column": f"p_{w}_H+p_{w}_D+p_{w}_A", "window": w,
                     "outcome": "ALL", "n_rows": len(df), "null_count": int(df[f"sum_p_{w}"].isna().sum()),
                     "min": df[f"sum_p_{w}"].min(), "max": df[f"sum_p_{w}"].max(),
                     "n_le_1": pd.NA, "max_abs_deviation": dev.max(),
                     "rows_outside_tolerance": int((dev > TOL).sum()),
                     "status": "PASS" if (dev <= TOL).all() else "FAIL"})
        rows.append({"check": "sum_q_gt_1", "column": f"sum_q_{w}", "window": w, "outcome": "ALL",
                     "n_rows": len(df), "null_count": 0, "min": df[f"sum_q_{w}"].min(),
                     "max": df[f"sum_q_{w}"].max(), "n_le_1": int((df[f"sum_q_{w}"] <= 1).sum()),
                     "status": "INFO"})
    rows.append({"check": "rows_with_complete_6_odds", "column": "mkt_avg_*", "window": "both",
                 "outcome": "ALL", "n_rows": len(df),
                 "null_count": int(df[list(ODDS.values())].isna().any(axis=1).sum()),
                 "status": "PASS" if df[list(ODDS.values())].notna().all(axis=None) else "FAIL"})
    for season, g in df.groupby("season"):
        rows.append({"check": "rows_per_season", "column": "match_id", "window": "both", "outcome": "ALL",
                     "season": season, "n_rows": len(g), "null_count": int(g[list(ODDS.values())].isna().sum().sum()),
                     "status": "PASS" if len(g) == 380 else "FAIL"})
    return pd.DataFrame(rows)


def overround_summary(df):
    rows = []
    for w in WINDOWS:
        for level, season, g in _levels(df):
            st = _stats(g[f"overround_{w}"])
            rows.append({"window": w, "level": level, "season": season, **st,
                         "mean_pct": 100 * st["mean"], "median_pct": 100 * st["median"],
                         "min_pct": 100 * st["min"], "max_pct": 100 * st["max"],
                         "rows_overround_le_0": int((g[f"overround_{w}"] <= 0).sum())})
    return pd.DataFrame(rows)


def implied_probability_summary(df):
    rows = []
    for measure, prefix in (("q_raw", "q"), ("p_normalized", "p")):
        for w in WINDOWS:
            for o in OUTCOMES:
                for level, season, g in _levels(df):
                    rows.append({"measure": measure, "window": w, "outcome": o, "level": level,
                                 "season": season, **_stats(g[f"{prefix}_{w}_{o}"])})
    return pd.DataFrame(rows)


def _favorite(df, w):
    p = df[[f"p_{w}_{o}" for o in OUTCOMES]].to_numpy()
    o = df[[ODDS[(w, x)] for x in OUTCOMES]].to_numpy()
    # Empate exacto en el máximo: cuotas idénticas (p_i = p_j  <=>  o_i = o_j).
    n_max = (o == o.min(axis=1, keepdims=True)).sum(axis=1)
    fav = np.array(OUTCOMES)[p.argmax(axis=1)].astype(object)
    fav[n_max > 1] = "TIE"
    return pd.Series(fav, index=df.index)


def market_favorite(df):
    favs = {w: _favorite(df, w) for w in WINDOWS}
    rows = []
    for w in WINDOWS:
        for level, season, g in _levels(df):
            f = favs[w].loc[g.index]
            n = len(g)
            row = {"window": w, "level": level, "season": season, "n_matches": n}
            for c in (*OUTCOMES, "TIE"):
                row[f"n_fav_{c}"] = int((f == c).sum())
                row[f"pct_fav_{c}"] = 100 * (f == c).mean()
            row["mean_p_max"] = g[[f"p_{w}_{o}" for o in OUTCOMES]].max(axis=1).mean()
            rows.append(row)
    for level, season, g in _levels(df):
        changed = (favs["pre"].loc[g.index] != favs["close"].loc[g.index])
        rows.append({"window": "pre_to_close", "level": level, "season": season, "n_matches": len(g),
                     "n_favorite_changed": int(changed.sum()), "pct_favorite_changed": 100 * changed.mean()})
    return pd.DataFrame(rows)


def pre_close_movement(df):
    rows = []
    for var in [*(f"delta_p_{o}" for o in OUTCOMES), "market_move_L1"]:
        for level, season, g in _levels(df):
            s = g[var]
            rows.append({"variable": var, "level": level, "season": season, **_stats(s),
                         "max_abs": s.abs().max(), "mean_abs": s.abs().mean()})
    return pd.DataFrame(rows)


def market_by_season(df):
    rows = []
    for level, season, g in _levels(df):
        r = {"level": level, "season": season, "matches": len(g),
             "overround_pre_mean": g["overround_pre"].mean(), "overround_close_mean": g["overround_close"].mean(),
             "overround_pre_mean_pct": 100 * g["overround_pre"].mean(),
             "overround_close_mean_pct": 100 * g["overround_close"].mean()}
        for w in WINDOWS:
            for o in OUTCOMES:
                r[f"mean_p_{w}_{o}"] = g[f"p_{w}_{o}"].mean()
        r["market_move_L1_mean"] = g["market_move_L1"].mean()
        r["market_move_L1_median"] = g["market_move_L1"].median()
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def _save_figure(fig, filename):
    if not filename.endswith(f"{SCOPE.suffix}.png"):
        raise ValueError("La figura debe llevar el sufijo de su scope")
    path = io.EDA_FIGURES_DIR / filename
    io.assert_allowed_output(path)                    # antes de crear carpetas o escribir
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return io.register_file(path, phase=PHASE, scope=SCOPE)


def _season_label(s):
    role = {**{x: "TRAIN" for x in io.SEASONS_TRAIN_DESIGN}, io.SEASON_VALIDATION: "VAL",
            io.SEASON_FINAL_TEST: "TEST"}[s]
    return f"{s.replace('-20', '/')}\n({role})"


def figure_overround(ov):
    d = ov[ov["level"] == "season"]
    seasons = sorted(d["season"].unique())
    fig, ax = plt.subplots(figsize=(8.6, 4.0), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for k, w in enumerate(WINDOWS):
        x = np.arange(len(seasons)) + (-0.13 if w == "pre" else 0.13)
        g = d[d["window"] == w].set_index("season").loc[seasons]
        med, lo, hi = 100 * g["median"], 100 * g["q25"], 100 * g["q75"]
        ax.vlines(x, lo, hi, color=WINDOW_COLOR[w], linewidth=2)
        ax.plot(x, med, "o", ms=8, color=WINDOW_COLOR[w], mec=SURFACE, mew=2,
                label=f"{w} — mediana e IQR" + (" (benchmark principal)" if w == "pre" else " (secundario)"))
        for xi, m in zip(x, med):
            ax.text(xi + (-0.06 if w == "pre" else 0.06), m, f"{m:.1f}", fontsize=8, color=INK,
                    ha="right" if w == "pre" else "left", va="center")
    ax.set_xticks(range(len(seasons)), [_season_label(s) for s in seasons], color=INK, fontsize=9)
    ax.set_ylabel("overround = Σ(1/cuota) − 1  (%)", color=INK2, fontsize=9)
    ax.set_title("Overround de las cuotas medias 1X2 por temporada", loc="left", fontsize=10.5, color=INK, pad=26)
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9,
              handlelength=1.2, labelcolor=INK)
    fig.text(0.01, 0.01, "Scope ALL_DESCRIPTIVE: descripción del benchmark; el overround no es un margen de beneficio realizado.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def figure_probabilities(df):
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.6), facecolor=SURFACE, sharey=True)
    bins = np.linspace(0, 1, 41)
    names = {"H": "P(H) local", "D": "P(D) empate", "A": "P(A) visitante"}
    for ax, o in zip(axes, OUTCOMES):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        s = df[f"p_pre_{o}"]
        w = np.full(len(s), 100 / len(s))
        ax.hist(s, bins=bins, weights=w, color=COLOR[o], rwidth=0.85)
        ax.axvline(s.median(), color=INK, linewidth=1, linestyle=(0, (3, 2)))
        ax.set_title(f"{names[o]} — mediana {s.median():.2f}", loc="left", fontsize=9.5, color=INK)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, .25, .5, .75, 1], ["0", ".25", ".5", ".75", "1"])
    axes[0].set_ylabel("% de partidos", color=INK2, fontsize=9)
    fig.suptitle("Probabilidades implícitas normalizadas, cuotas pre (benchmark principal), 5 temporadas (n = 1,900)",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, "Línea discontinua: mediana. p_i = (1/o_i) / Σ(1/o_j) (D39). Close: ver tablas.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()          # ABORTA ante cualquier discrepancia
    df = market_frame()
    tables = {
        "e02m_market_integrity": market_integrity(df),
        "e02m_overround_summary": overround_summary(df),
        "e02m_implied_probability_summary": implied_probability_summary(df),
        "e02m_market_by_season": market_by_season(df),
        "e02m_pre_close_movement": pre_close_movement(df),
        "e02m_market_favorite": market_favorite(df),
    }
    integ = tables["e02m_market_integrity"]
    if (integ["status"] == "FAIL").any():
        raise RuntimeError("E2m: fallo de integridad del bloque mercado; revisar antes de continuar")
    outputs = [io.write_table(t, name, phase=PHASE, scope=SCOPE, out_root=out_root) for name, t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_overround(tables["e02m_overround_summary"]), "e02m_overround_by_season__ALL.png"))
        outputs.append(_save_figure(figure_probabilities(df), "e02m_implied_probabilities__ALL.png"))
    return outputs, input_hashes, tables
