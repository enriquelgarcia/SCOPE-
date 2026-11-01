"""E3 — Análisis univariado de features pre-partido (scope DEV_PREDICTORS, 2021/22–2024/25).

PREDICTOR-ONLY: el cargador DEV_PREDICTORS no entrega `result`, `goal_difference`, POST ni MARKET,
y este módulo además lo comprueba. No hay correlaciones entre features (E4), relación con targets,
selección, transformación, winsorización ni escalado. Sin aleatoriedad.

Población principal: filas con `is_modeling_eligible = true` (sin missingness en features).
Estratificación por historial (secundaria, etiquetada): h_* por `h_n_prev_season`, a_* por
`a_n_prev_season`, diff_* por min(h, a). Tramos 3–5, 6–10, 11–20, 21–37.
Valores extremos: regla de Tukey (fuera de [Q1 − 1.5·IQR, Q3 + 1.5·IQR]) calculada sobre la
población principal; un extremo es una observación poco frecuente, NO un error. Los errores se
comprueban aparte contra el dominio del contrato (§5.4).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.data.features_schema import RATE_METRICS  # noqa: E402
from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import GRID, INK, INK2, SURFACE, _style  # noqa: E402

PHASE = "E3"
SCOPE = io.DEV_PREDICTORS
SCOPES = ["DEV_PREDICTORS"]
NOTES = ("E3 univariado predictor-only sobre DEVX elegible (2021/22–2024/25); sin targets, sin "
         "correlaciones, sin transformaciones; sin aleatoriedad (seed=null)")
SIDE_COLS = [f"{p}_{m}" for p in ("h", "a") for m in RATE_METRICS]
DIFF_COLS = [f"diff_{m}" for m in RATE_METRICS]
RATE_COLS = SIDE_COLS + DIFF_COLS
CONTROL_COLS = ["h_n_prev_season", "a_n_prev_season"]
BINS = [(3, 5), (6, 10), (11, 20), (21, 37)]
BIN_LABELS = [f"{a}–{b}" for a, b in BINS]
SEASON_METRICS = ("ppg", "gf_pg", "ga_pg")       # sot solo existe en last5
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"


# ---------------------------------------------------------------------------
def load() -> pd.DataFrame:
    feat = io.load_features(SCOPE)
    teams = io.load_canonical(SCOPE)[["match_id", "home_team_id", "away_team_id"]]
    df = feat.merge(teams, on="match_id", how="left", validate="one_to_one")
    forbidden = set(io.TARGET_COLUMNS) | {c for c, r in io.CANONICAL_ROLES.items()
                                          if r in io.FORBIDDEN_ROLES_DEVX}
    assert not (set(df.columns) & forbidden), "E3 no puede recibir targets/POST/MARKET"
    assert set(df["season"].unique()) == set(io.SEASONS_DEV)
    return df


def eligible(df):
    return df[df["is_modeling_eligible"]].reset_index(drop=True)


def feature_meta(col: str) -> dict:
    if col in CONTROL_COLS:
        return {"family": "control", "window": "season", "side": col[0], "metric": "n_prev_season"}
    side, metric = ("diff", col[5:]) if col.startswith("diff_") else (col[0], col[2:])
    window = "last5" if metric.endswith("last5") else "season"
    return {"family": "diff" if side == "diff" else "team", "window": window, "side": side,
            "metric": metric.rsplit("_", 1)[0]}


def history_for(df, col) -> pd.Series:
    if col.startswith("h_"):
        return df["h_n_prev_season"]
    if col.startswith("a_"):
        return df["a_n_prev_season"]
    return df[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)


def _bin(n: pd.Series) -> pd.Series:
    out = pd.Series(pd.NA, index=n.index, dtype="object")
    for (a, b), lab in zip(BINS, BIN_LABELS):
        out[(n >= a) & (n <= b)] = lab
    return out


def describe(s: pd.Series) -> dict:
    q = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {"n": int(s.size), "mean": s.mean(), "median": q[0.5], "std": s.std(ddof=1),
            "variance": s.var(ddof=1), "min": s.min(), "max": s.max(), "q1": q[0.25], "q3": q[0.75],
            "iqr": q[0.75] - q[0.25], "p5": q[0.05], "p95": q[0.95], "skewness": s.skew(),
            "excess_kurtosis": s.kurt(), "n_unique": int(s.nunique())}


def fences(s):
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)


# ---------------------------------------------------------------------------
def univariate_summary(el):
    rows = []
    for col in CONTROL_COLS + RATE_COLS:
        s = el[col].astype(float)
        lo, hi = fences(s)
        rows.append({"feature": col, **feature_meta(col), "population": "DEVX_eligible", **describe(s),
                     "tukey_low": lo, "tukey_high": hi, "n_below_tukey": int((s < lo).sum()),
                     "n_above_tukey": int((s > hi).sum()),
                     "pct_beyond_tukey": 100 * ((s < lo) | (s > hi)).mean()})
    return pd.DataFrame(rows)


def by_season(el):
    rows = []
    for col in CONTROL_COLS + RATE_COLS:
        for season, g in el.groupby("season", sort=True):
            s = g[col].astype(float)
            rows.append({"feature": col, "season": season, "population": "DEVX_eligible", "n": int(s.size),
                         "mean": s.mean(), "median": s.median(), "std": s.std(ddof=1),
                         "q1": s.quantile(0.25), "q3": s.quantile(0.75),
                         "min": s.min(), "max": s.max()})
    return pd.DataFrame(rows)


def by_history(el, summary):
    fz = summary.set_index("feature")[["tukey_low", "tukey_high"]]
    rows = []
    for col in RATE_COLS:
        b = _bin(history_for(el, col))
        lo, hi = fz.loc[col]
        for lab in BIN_LABELS:
            s = el.loc[b == lab, col]
            st = describe(s)
            rows.append({"feature": col, "history_variable": "min_n_prev_season" if col.startswith("diff_")
                         else f"{col[0]}_n_prev_season", "history_bin": lab, "population": "DEVX_eligible",
                         **{k: st[k] for k in ("n", "mean", "median", "std", "q1", "q3", "iqr", "p5", "p95",
                                               "min", "max", "n_unique")},
                         "n_beyond_global_tukey": int(((s < lo) | (s > hi)).sum()),
                         "pct_beyond_global_tukey": 100 * ((s < lo) | (s > hi)).mean()})
    return pd.DataFrame(rows)


DOMAIN = {"ppg": (0.0, 3.0)}   # contrato §5.4: ppg ∈ [0, 3]; resto ≥ 0


def extreme_values(el, summary):
    fz = summary.set_index("feature")
    rows = []
    for col in RATE_COLS:
        lo, hi = fz.loc[col, "tukey_low"], fz.loc[col, "tukey_high"]
        s = el[col]
        hit = el[(s < lo) | (s > hi)]
        meta = feature_meta(col)
        for _, r in hit.iterrows():
            v = r[col]
            if meta["side"] == "diff":
                valid = True        # diff = h − a; su validez se hereda de h y a (V16)
            else:
                dlo, dhi = DOMAIN.get(meta["metric"], (0.0, np.inf))
                valid = bool(dlo <= v <= dhi)
            rows.append({"feature": col, "match_id": r["match_id"], "season": r["season"],
                         "kickoff_datetime": r["kickoff_datetime"].strftime("%Y-%m-%dT%H:%M:%S"),
                         "home_team_id": r["home_team_id"], "away_team_id": r["away_team_id"],
                         "value": v, "direction": "low" if v < lo else "high",
                         "tukey_low": lo, "tukey_high": hi,
                         "h_n_prev_season": int(r["h_n_prev_season"]), "a_n_prev_season": int(r["a_n_prev_season"]),
                         "history_bin": _bin(pd.Series([history_for(r.to_frame().T.astype({"h_n_prev_season": int, "a_n_prev_season": int}), col).iloc[0]])).iloc[0],
                         "rule": "tukey_1.5_iqr", "within_contract_domain": valid,
                         "classification": "valor extremo (no error)" if valid else "violación de dominio"})
    return pd.DataFrame(rows)


def granularity(el):
    rows = []
    for metric in SEASON_METRICS + ("sot_pg",):
        for window in ("season", "last5"):
            if metric == "sot_pg" and window == "season":
                continue
            for side in ("h", "a", "diff"):
                col = f"{side}_{metric}_{window}"
                s = el[col]
                vals = np.sort(s.unique())
                gaps = np.diff(vals)
                vc = s.value_counts(normalize=True)
                rows.append({"metric": metric, "window": window, "side": side, "feature": col,
                             "population": "DEVX_eligible", "n": int(s.size), "n_unique": int(vals.size),
                             "unique_per_100_rows": 100 * vals.size / s.size,
                             "min_gap_between_values": gaps.min() if gaps.size else np.nan,
                             "median_gap_between_values": np.median(gaps) if gaps.size else np.nan,
                             "top_value": vc.index[0], "top_value_share_pct": 100 * vc.iloc[0],
                             "top5_values_share_pct": 100 * vc.iloc[:5].sum(),
                             "in_season_comparison": metric in SEASON_METRICS})
    return pd.DataFrame(rows)


def home_away(el):
    rows = []
    for m in RATE_METRICS:
        h, a = el[f"h_{m}"], el[f"a_{m}"]
        dh, da = describe(h), describe(a)
        for stat in ("mean", "median", "std", "q1", "q3", "p5", "p95", "skewness", "excess_kurtosis", "n_unique"):
            rows.append({"metric": m, "statistic": stat, "h": dh[stat], "a": da[stat], "h_minus_a": dh[stat] - da[stat]})
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


def _note(fig, text):
    fig.text(0.01, 0.01, text, fontsize=7.5, color=INK2)


def figure_diff(el):
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.4), facecolor=SURFACE)
    axes = axes.ravel()
    for ax, col in zip(axes, DIFF_COLS):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        s = el[col]
        span = max(abs(s.min()), abs(s.max()))
        nb = 40 if "season" in col else min(40, s.nunique())
        ax.hist(s, bins=np.linspace(-span, span, nb + 1), weights=np.full(len(s), 100 / len(s)),
                color=BLUE, rwidth=0.88)
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.axvline(s.median(), color=INK, linewidth=1, linestyle=(0, (3, 2)))
        ax.set_title(f"{col}\nmediana {s.median():+.2f} · DE {s.std():.2f}", loc="left", fontsize=8.8, color=INK)
    axes[-1].axis("off")
    axes[-1].text(0, 0.6, "diff_x = h_x − a_x\n\n> 0: el valor del local es mayor.\nEn ga_pg, mayor = recibe más\ngoles (no es \"ventaja\").",
                  fontsize=8.5, color=INK2, va="top")
    for ax in axes[[0, 4]]:
        ax.set_ylabel("% de partidos", color=INK2, fontsize=8.5)
    fig.suptitle("Distribución de las siete diff_* — DEVX elegible 2021/22–2024/25 (n = 1,399)",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    _note(fig, "Línea gris: 0. Discontinua: mediana. Sin targets; descriptivo (scope DEV_PREDICTORS).")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    return fig


def figure_season_vs_last5(el):
    """Valores h_ y a_ agrupados (cada fila aporta dos valores de equipo). Solo distribución, sin correlación."""
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.4), facecolor=SURFACE, sharex="col")
    names = {"ppg": "puntos por partido", "gf_pg": "goles a favor por partido", "ga_pg": "goles en contra por partido"}
    for j, m in enumerate(SEASON_METRICS):
        hi = 3.0 if m == "ppg" else max(el[f"h_{m}_last5"].max(), el[f"a_{m}_last5"].max(),
                                         el[f"h_{m}_season"].max(), el[f"a_{m}_season"].max())
        for i, (window, color) in enumerate((("season", BLUE), ("last5", ORANGE))):
            ax = axes[i, j]
            _style(ax)
            ax.grid(axis="y", color=GRID, linewidth=0.8)
            ax.set_axisbelow(True)
            v = pd.concat([el[f"h_{m}_{window}"], el[f"a_{m}_{window}"]])
            ax.hist(v, bins=np.linspace(0, hi, 121), weights=np.full(len(v), 100 / len(v)), color=color)
            ax.set_title(f"{m}_{window} — {v.nunique()} valores distintos", loc="left", fontsize=8.8, color=INK)
            if j == 0:
                ax.set_ylabel("% de valores", color=INK2, fontsize=8.5)
        axes[1, j].set_xlabel(names[m], color=INK2, fontsize=8.5)
    fig.suptitle("Granularidad univariada: season (arriba) vs last5 (abajo) — DEVX elegible, valores h_ y a_ agrupados",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    _note(fig, "Bins de ancho fijo (120 por panel). last5 promedia como máximo 5 partidos: valores en una rejilla fina de fracciones. Sin correlación season–last5 (E6).")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return fig


def figure_dispersion(hist_tab):
    sel = [("h_ppg_season", BLUE), ("h_ppg_last5", ORANGE), ("h_sot_pg_last5", AQUA), ("diff_ppg_season", YELLOW)]
    fig, ax = plt.subplots(figsize=(8.6, 4.2), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    x = np.arange(len(BIN_LABELS))
    for col, color in sel:
        t = hist_tab[hist_tab["feature"] == col].set_index("history_bin").loc[BIN_LABELS]
        idx = t["std"] / t.loc["21–37", "std"]
        ax.plot(x, idx, color=color, linewidth=2, marker="o", ms=8, mec=SURFACE, mew=2, label=col)
        # Etiqueta directa al inicio: en 21–37 todas valen 1 por construcción del índice.
        ax.text(x[0] - 0.1, idx.iloc[0], f"{col}  {idx.iloc[0]:.2f}", fontsize=8.5, color=INK,
                va="center", ha="right")
    ax.axhline(1, color=INK2, linewidth=0.8)
    ax.set_xticks(x, [f"{b} partidos previos" for b in BIN_LABELS], color=INK, fontsize=9)
    ax.set_xlim(-1.45, len(x) - 0.6)
    ax.set_ylabel("DE del tramo / DE del tramo 21–37", color=INK2, fontsize=9)
    ax.set_title("Dispersión de features seleccionadas según historial disponible (DEVX elegible)",
                 loc="left", fontsize=10.5, color=INK, pad=26)
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=8.5, handlelength=1.4,
              labelcolor=INK)
    _note(fig, "Índice = 1 si la dispersión iguala la del tramo 21–37. Descriptivo: no selecciona burn-in (P01, E7). Detalle completo en e03_univariate_by_history__DEVX.csv.")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    el = eligible(load())
    summary = univariate_summary(el)
    hist = by_history(el, summary)
    tables = {
        "e03_univariate_summary": summary,
        "e03_univariate_by_season": by_season(el),
        "e03_univariate_by_history": hist,
        "e03_extreme_values": extreme_values(el, summary),
        "e03_granularity": granularity(el),
        "e03_home_away_comparison": home_away(el),
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=SCOPE, out_root=out_root) for name, t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_diff(el), "e03_diff_feature_distributions__DEVX.png"))
        outputs.append(_save_figure(figure_season_vs_last5(el), "e03_season_vs_last5_univariate__DEVX.png"))
        outputs.append(_save_figure(figure_dispersion(hist), "e03_feature_dispersion_by_history__DEVX.png"))
    return outputs, input_hashes, tables
