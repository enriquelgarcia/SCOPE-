"""E2 — Análisis de targets (result H/D/A y goal_difference) y goles.

Fase DESCRIPTIVA. Scopes: ALL_DESCRIPTIVE (5 temporadas), TRAIN_TARGET (2021/22–2023/24);
VAL (2024/25) y TEST (2025/26) solo aparecen como filas descriptivas separadas.
NO selecciona modelos, métricas, class weights, resampling, transformaciones ni features.
NO analiza MARKET ni usa estadísticas POST como predictores. Sin aleatoriedad.

Convenciones:
- En cada tabla, `level = season` son filas por temporada y `level = scope_total` es el
  agregado de TODAS las temporadas del scope del archivo (season = "ALL").
- Intervalos de Wilson al 95 % (z = 1.959964); suponen partidos independientes, lo que es
  una aproximación (los equipos se repiten), por lo que se leen como descriptivos.
- Varianza y desviación estándar muestrales (ddof = 1); asimetría y curtosis en exceso con
  los estimadores ajustados de pandas (skew / kurt).
"""
from __future__ import annotations

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.eda import eda_io as io  # noqa: E402

PHASE = "E2"
SCOPES = ["ALL_DESCRIPTIVE", "TRAIN_TARGET"]
NOTES = ("E2 descriptivo de targets; sin aleatoriedad (seed=null); VAL y TEST solo como filas "
         "descriptivas separadas; sin decisiones de modelado")
CLASSES = ("H", "D", "A")
CLASS_LABEL = {"H": "Victoria local (H)", "D": "Empate (D)", "A": "Victoria visitante (A)"}
Z95 = 1.959963984540054
TARGET_COLS = ["match_id", "season", "home_goals", "away_goals", "result", "goal_difference"]

# Paleta categórica de referencia (dataviz), validada: slots 1–3 en orden fijo.
COLOR = {"H": "#2a78d6", "D": "#eb6834", "A": "#1baf7a"}
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (centre - half, centre + half)


def _targets(scope) -> pd.DataFrame:
    df = io.load_canonical(scope).loc[:, TARGET_COLS].copy()
    df["total_goals"] = df["home_goals"] + df["away_goals"]
    return df


def _levels(df: pd.DataFrame):
    """Filas por temporada y agregado del scope."""
    for season, g in df.groupby("season", sort=True):
        yield "season", season, g
    yield "scope_total", "ALL", df


# ---------------------------------------------------------------------------
def result_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for level, season, g in _levels(df):
        n = len(g)
        counts = g["result"].value_counts()
        for c in CLASSES:
            k = int(counts.get(c, 0))
            lo, hi = wilson(k, n)
            rows.append({"level": level, "season": season, "result": c, "n_matches": n,
                         "count": k, "proportion": k / n, "wilson95_low": lo, "wilson95_high": hi})
    return pd.DataFrame(rows)


def _describe(s: pd.Series) -> dict:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return {"n": int(s.size), "mean": s.mean(), "median": s.median(), "std": s.std(ddof=1),
            "variance": s.var(ddof=1), "min": int(s.min()), "q1": q1, "q3": q3, "iqr": q3 - q1,
            "max": int(s.max()), "skewness": s.skew(), "excess_kurtosis": s.kurt()}


def goal_difference_summary(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"level": lv, "season": s, **_describe(g["goal_difference"])}
                         for lv, s, g in _levels(df)])


def goal_difference_frequency(df: pd.DataFrame) -> pd.DataFrame:
    lo, hi = int(df["goal_difference"].min()), int(df["goal_difference"].max())
    rows = []
    for level, season, g in _levels(df):
        vc = g["goal_difference"].value_counts()
        for v in range(lo, hi + 1):
            k = int(vc.get(v, 0))
            rows.append({"level": level, "season": season, "goal_difference": v,
                         "count": k, "proportion": k / len(g)})
    return pd.DataFrame(rows)


def goals_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for level, season, g in _levels(df):
        for var in ("home_goals", "away_goals", "total_goals"):
            s = g[var]
            mean, var_ = s.mean(), s.var(ddof=1)
            ratio = var_ / mean
            rows.append({
                "level": level, "season": season, "variable": var, "n": int(s.size),
                "mean": mean, "median": s.median(), "variance": var_, "std": s.std(ddof=1),
                "min": int(s.min()), "q10": s.quantile(0.10), "q25": s.quantile(0.25),
                "q75": s.quantile(0.75), "q90": s.quantile(0.90), "max": int(s.max()),
                "variance_mean_ratio": ratio,
                "dispersion_description": ("sobredispersión aparente" if ratio > 1 else
                                           "subdispersión aparente" if ratio < 1 else "equidispersión"),
            })
    return pd.DataFrame(rows)


def season_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for level, season, g in _levels(df):
        n = len(g)
        c = g["result"].value_counts()
        gd = g["goal_difference"]
        consistent = bool(((gd > 0) == (g["result"] == "H")).all() and
                          ((gd == 0) == (g["result"] == "D")).all() and
                          ((gd < 0) == (g["result"] == "A")).all())
        rows.append({
            "level": level, "season": season, "matches": n,
            "H": int(c.get("H", 0)), "D": int(c.get("D", 0)), "A": int(c.get("A", 0)),
            "pct_H": 100 * c.get("H", 0) / n, "pct_D": 100 * c.get("D", 0) / n,
            "pct_A": 100 * c.get("A", 0) / n,
            "mean_home_goals": g["home_goals"].mean(), "mean_away_goals": g["away_goals"].mean(),
            "mean_total_goals": g["total_goals"].mean(), "mean_goal_difference": gd.mean(),
            "std_goal_difference": gd.std(ddof=1),
            "result_sign_consistent_with_goal_difference": consistent,
        })
    return pd.DataFrame(rows)


def home_advantage(groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, g in groups.items():
        n = len(g)
        kH, kA = int((g["result"] == "H").sum()), int((g["result"] == "A").sum())
        hl, hh = wilson(kH, n)
        al, ah = wilson(kA, n)
        rows.append({
            "group": name, "seasons": ",".join(sorted(g["season"].unique())), "matches": n,
            "pct_home_win": 100 * kH / n, "pct_home_win_wilson95_low": 100 * hl,
            "pct_home_win_wilson95_high": 100 * hh,
            "pct_away_win": 100 * kA / n, "pct_away_win_wilson95_low": 100 * al,
            "pct_away_win_wilson95_high": 100 * ah,
            "home_minus_away_win_pct_points": 100 * (kH - kA) / n,
            "mean_home_goals": g["home_goals"].mean(), "mean_away_goals": g["away_goals"].mean(),
            "mean_goal_difference": g["goal_difference"].mean(),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def _save_figure(fig, filename: str, scope) -> io.OutputRecord:
    scope = io._as_scope(scope)
    if not filename.endswith(f"{scope.suffix}.png"):
        raise ValueError("La figura debe llevar el sufijo de su scope")
    path = io.EDA_FIGURES_DIR / filename
    io.assert_allowed_output(path)                    # antes de crear carpetas o escribir
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return io.register_file(path, phase=PHASE, scope=scope)


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)


def figure_result_by_season(dist: pd.DataFrame) -> plt.Figure:
    d = dist[dist["level"] == "season"].pivot(index="season", columns="result", values="proportion")
    d = d.loc[sorted(d.index, reverse=True), list(CLASSES)]
    role = {s: "TRAIN" for s in io.SEASONS_TRAIN_DESIGN}
    role[io.SEASON_VALIDATION], role[io.SEASON_FINAL_TEST] = "VAL", "TEST"
    fig, ax = plt.subplots(figsize=(8.6, 3.8), facecolor=SURFACE)
    _style(ax)
    gap = 0.004                                       # separación visual entre segmentos
    for i, season in enumerate(d.index):
        left = 0.0
        for c in CLASSES:
            w = d.loc[season, c]
            ax.barh(i, w - gap, left=left + gap / 2, height=0.62, color=COLOR[c],
                    label=CLASS_LABEL[c] if i == 0 else None)
            ax.text(left + w / 2, i, f"{100 * w:.1f} %", ha="center", va="center",
                    fontsize=9, color="white" if c != "A" else INK, fontweight="medium")
            left += w
    ax.set_yticks(range(len(d.index)),
                  [f"{s.replace('-20', '/')}  ({role[s]})" for s in d.index], color=INK)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, .25, .5, .75, 1], ["0 %", "25 %", "50 %", "75 %", "100 %"])
    ax.set_title("Resultado H / D / A por temporada (proporción de partidos, n = 380 por temporada)",
                 loc="left", fontsize=10.5, color=INK, pad=26)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9,
              handlelength=1.2, labelcolor=INK)
    fig.text(0.01, 0.01, "Scope ALL_DESCRIPTIVE: solo descripción. VAL y TEST no se usan para decisiones (D42).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def figure_goal_difference_train(freq: pd.DataFrame) -> plt.Figure:
    f = freq[freq["level"] == "scope_total"]
    f = f[f["count"] > 0]
    n = int(f["count"].sum())
    fig, ax = plt.subplots(figsize=(8.6, 3.8), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    cols = [COLOR["H"] if v > 0 else COLOR["D"] if v == 0 else COLOR["A"] for v in f["goal_difference"]]
    ax.bar(f["goal_difference"], 100 * f["proportion"], width=0.78, color=cols)
    for v, p, k in zip(f["goal_difference"], f["proportion"], f["count"]):
        if p >= 0.04:                                 # etiquetas selectivas (barras principales)
            ax.text(v, 100 * p + 0.4, f"{100 * p:.1f} %", ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(range(int(f["goal_difference"].min()), int(f["goal_difference"].max()) + 1))
    ax.set_xlabel("goal_difference = home_goals − away_goals", color=INK2, fontsize=9)
    ax.set_ylabel("% de partidos", color=INK2, fontsize=9)
    ax.set_title(f"Distribución de goal_difference — TRAIN 2021/22–2023/24 (n = {n})",
                 loc="left", fontsize=10.5, color=INK, pad=26)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLOR[c]) for c in ("A", "D", "H")]
    ax.legend(handles, ["< 0 → A", "= 0 → D", "> 0 → H"], ncol=3, loc="lower left",
              bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, handlelength=1.2, labelcolor=INK)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None) -> tuple[list[io.OutputRecord], dict, dict]:
    input_hashes = io.verify_frozen_inputs()          # ABORTA ante cualquier discrepancia
    all_df = _targets(io.ALL_DESCRIPTIVE)
    train = _targets(io.TRAIN_TARGET)
    val = _targets(io.VAL_DESCRIPTIVE)
    test = _targets(io.TEST_DESCRIPTIVE)

    tables = {
        ("e02_result_distribution", "ALL_DESCRIPTIVE"): result_distribution(all_df),
        ("e02_result_distribution", "TRAIN_TARGET"): result_distribution(train),
        ("e02_goal_difference_summary", "ALL_DESCRIPTIVE"): goal_difference_summary(all_df),
        ("e02_goal_difference_summary", "TRAIN_TARGET"): goal_difference_summary(train),
        ("e02_goal_difference_frequency", "ALL_DESCRIPTIVE"): goal_difference_frequency(all_df),
        ("e02_goal_difference_frequency", "TRAIN_TARGET"): goal_difference_frequency(train),
        ("e02_goals_summary", "ALL_DESCRIPTIVE"): goals_summary(all_df),
        ("e02_goals_summary", "TRAIN_TARGET"): goals_summary(train),
        ("e02_season_summary", "ALL_DESCRIPTIVE"): season_summary(all_df),
        ("e02_home_advantage", "ALL_DESCRIPTIVE"): home_advantage(
            {"ALL": all_df, "TRAIN": train, "VAL": val, "TEST": test}),
    }
    outputs = [io.write_table(df, name, phase=PHASE, scope=scope, out_root=out_root)
               for (name, scope), df in tables.items()]
    if out_root is None:                              # figuras solo en la ejecución real
        outputs.append(_save_figure(figure_result_by_season(tables[("e02_result_distribution", "ALL_DESCRIPTIVE")]),
                                    "e02_result_distribution_by_season__ALL.png", io.ALL_DESCRIPTIVE))
        outputs.append(_save_figure(figure_goal_difference_train(tables[("e02_goal_difference_frequency", "TRAIN_TARGET")]),
                                    "e02_goal_difference_distribution__TRAIN.png", io.TRAIN_TARGET))
    return outputs, input_hashes, tables
