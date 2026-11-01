"""E4 — Relaciones entre features (E4A, DEVX) y relación descriptiva con targets (E4B, TRAIN).

E4A — predictor ↔ predictor: scope DEV_PREDICTORS (2021/22–2024/25), filas elegibles (1,399).
       El cargador no entrega targets, POST ni MARKET.
E4B — predictor ↔ target: scope TRAIN_TARGET (2021/22–2023/24), filas elegibles (1,049).
       Único bloque con `result` y `goal_difference`. VAL y TEST no participan.

NO: VIF, condition number, rango, regresiones auxiliares (E5/M1); análisis condicionado al
historial season–last5 (E6/M3); selección, eliminación o transformación; tests inferenciales.
`result` es nominal: nunca se codifica numéricamente. Spearman = Pearson sobre rangos (pandas,
rangos medios para empates). Sin aleatoriedad.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from src.data.features_schema import RATE_METRICS  # noqa: E402
from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import CLASSES, COLOR, GRID, INK, INK2, SURFACE, _style  # noqa: E402

PHASE = "E4"
SCOPES = ["DEV_PREDICTORS", "TRAIN_TARGET"]
NOTES = ("E4A predictor↔predictor en DEVX elegible (1,399); E4B predictor↔target solo en TRAIN elegible "
         "(1,049). Sin VIF/condition number/rango; sin selección; sin tests; sin aleatoriedad (seed=null)")
EXPECTED_N = {"DEV_PREDICTORS": 1399, "TRAIN_TARGET": 1049}

SEASON_M = ("ppg_season", "gf_pg_season", "ga_pg_season")
LAST5_M = ("ppg_last5", "gf_pg_last5", "ga_pg_last5", "sot_pg_last5")
ORDER = ([f"{s}_{m}" for s in ("h", "a", "diff") for m in SEASON_M] +
         [f"{s}_{m}" for s in ("h", "a", "diff") for m in LAST5_M])   # 21, agrupadas por bloque
assert sorted(ORDER) == sorted([f"{p}_{m}" for p in ("h", "a", "diff") for m in RATE_METRICS])
DIV_CMAP = LinearSegmentedColormap.from_list("scope_div", ["#184f95", "#86b6ef", "#f0efec", "#f0a3a2", "#b52f2f"])


def spearman(x: pd.Series, y: pd.Series) -> float:
    """Spearman = Pearson sobre rangos medios (empates promediados). Evita depender de scipy."""
    return x.rank(method="average").corr(y.rank(method="average"))


def eligible(scope):
    df = io.load_features(scope)
    el = df[df["is_modeling_eligible"]].reset_index(drop=True)
    if len(el) != EXPECTED_N[scope.name]:
        raise RuntimeError(f"{scope.name}: {len(el)} filas elegibles, se esperaban {EXPECTED_N[scope.name]}")
    return el


# ---------------------------------------------------------------------------
# E4A
def corr_matrix(el, method):
    data = el[ORDER].rank(method="average") if method == "spearman" else el[ORDER]
    m = data.corr(method="pearson")
    out = m.reset_index().rename(columns={"index": "feature"})
    out.insert(1, "method", method)
    return out


def _pair_rows(el, pairs):
    rows = []
    for f1, f2, family, relation in pairs:
        rows.append({"feature_1": f1, "feature_2": f2, "family": family, "relation": relation,
                     "n": len(el), "pearson": el[f1].corr(el[f2]),
                     "spearman": spearman(el[f1], el[f2])})
    return rows


def pairwise(el):
    pairs = []
    for m in RATE_METRICS:
        pairs += [(f"h_{m}", f"a_{m}", "h_a_diff_definicional", "mismo indicador, equipo local vs visitante"),
                  (f"h_{m}", f"diff_{m}", "h_a_diff_definicional", "diff = h − a (algebraica)"),
                  (f"a_{m}", f"diff_{m}", "h_a_diff_definicional", "diff = h − a (algebraica)")]
    for side in ("h", "a", "diff"):
        for base in ("ppg", "gf_pg", "ga_pg"):
            pairs.append((f"{side}_{base}_season", f"{side}_{base}_last5", "season_vs_last5",
                          "misma métrica, ventana season vs last5 (idénticas si n_prev ≤ 5)"))
        for w in ("season", "last5"):
            pairs += [(f"{side}_ppg_{w}", f"{side}_gf_pg_{w}", "conceptual", "PPG ↔ GF/PG"),
                      (f"{side}_ppg_{w}", f"{side}_ga_pg_{w}", "conceptual", "PPG ↔ GA/PG"),
                      (f"{side}_gf_pg_{w}", f"{side}_ga_pg_{w}", "conceptual", "GF/PG ↔ GA/PG")]
        pairs += [(f"{side}_sot_pg_last5", f"{side}_gf_pg_last5", "conceptual", "SOT last5 ↔ GF last5"),
                  (f"{side}_sot_pg_last5", f"{side}_ppg_last5", "conceptual", "SOT last5 ↔ PPG last5")]
    out = pd.DataFrame(_pair_rows(el, pairs))
    out["pearson_minus_spearman"] = out["pearson"] - out["spearman"]
    return out


def identity_share(el):
    """Cuántas filas elegibles tienen last5 == season por construcción (n_prev ≤ 5), por lado."""
    rows = []
    for side in ("h", "a"):
        n5 = el[f"{side}_n_prev_season"] <= 5
        rows.append({"side": side, "rows_n_prev_le_5": int(n5.sum()), "pct": 100 * n5.mean()})
    mn = el[["h_n_prev_season", "a_n_prev_season"]].min(axis=1) <= 5
    rows.append({"side": "diff (min)", "rows_n_prev_le_5": int(mn.sum()), "pct": 100 * mn.mean()})
    return rows


# ---------------------------------------------------------------------------
# E4B
def gd_relationships(tr):
    rows = [{"feature": f, "n": len(tr), "pearson": tr[f].corr(tr["goal_difference"]),
             "spearman": spearman(tr[f], tr["goal_difference"])} for f in ORDER]
    out = pd.DataFrame(rows)
    out["abs_pearson"] = out["pearson"].abs()
    out = out.sort_values("abs_pearson", ascending=False).reset_index(drop=True)
    out.insert(0, "order_by_abs_pearson", range(1, len(out) + 1))   # solo para lectura
    return out


def by_result(tr):
    rows = []
    for f in ORDER:
        for c in CLASSES:
            s = tr.loc[tr["result"] == c, f]
            rows.append({"feature": f, "result": c, "n": int(s.size), "mean": s.mean(), "median": s.median(),
                         "std": s.std(ddof=1), "q1": s.quantile(0.25), "q3": s.quantile(0.75),
                         "mean_abs_value": s.abs().mean()})
    return pd.DataFrame(rows)


def separation(tr):
    """Diferencia de medias estandarizada (d con DE combinada) entre pares de clases. Descriptiva."""
    rows = []
    for f in ORDER:
        g = {c: tr.loc[tr["result"] == c, f] for c in CLASSES}
        for a, b in (("H", "A"), ("H", "D"), ("D", "A")):
            na, nb = len(g[a]), len(g[b])
            sp = np.sqrt(((na - 1) * g[a].var() + (nb - 1) * g[b].var()) / (na + nb - 2))
            rows.append({"feature": f, "class_1": a, "class_2": b, "n_1": na, "n_2": nb,
                         "mean_1_minus_mean_2": g[a].mean() - g[b].mean(), "pooled_std": sp,
                         "standardized_mean_difference": (g[a].mean() - g[b].mean()) / sp})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def _save_figure(fig, filename, scope):
    if not filename.endswith(f"{scope.suffix}.png"):
        raise ValueError("La figura debe llevar el sufijo de su scope")
    path = io.EDA_FIGURES_DIR / filename
    io.assert_allowed_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return io.register_file(path, phase=PHASE, scope=scope)


def figure_heatmap(mat, method_label, n):
    m = mat.set_index("feature")[ORDER].loc[ORDER].to_numpy()
    fig, ax = plt.subplots(figsize=(11, 10), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    im = ax.imshow(m, cmap=DIV_CMAP, vmin=-1, vmax=1)
    for i in range(len(ORDER)):
        for j in range(len(ORDER)):
            v = m[i, j]
            ax.text(j, i, f"{v:.2f}".replace("0.", ".").replace("-.", "−."), ha="center", va="center", fontsize=6.3,
                    color="white" if abs(v) > 0.7 else INK)
    for b in (2.5, 5.5, 11.5, 15.5):          # separadores h/a/diff dentro de cada bloque
        ax.axhline(b, color=SURFACE, linewidth=1.5); ax.axvline(b, color=SURFACE, linewidth=1.5)
    ax.axhline(8.5, color=INK, linewidth=1.6); ax.axvline(8.5, color=INK, linewidth=1.6)   # season | last5
    ax.set_xticks(range(len(ORDER)), ORDER, rotation=90, fontsize=7.5, color=INK)
    ax.set_yticks(range(len(ORDER)), ORDER, fontsize=7.5, color=INK)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.ax.tick_params(labelsize=8, colors=INK2)
    cb.outline.set_visible(False)
    ax.set_title(f"Correlación de {method_label} entre las 21 features de tasa — DEVX elegible (n = {n:,})",
                 loc="left", fontsize=10.5, color=INK, pad=12)
    fig.text(0.01, 0.012, "Bloques: season (arriba/izquierda) | last5; dentro de cada uno h_, a_, diff_. "
             "diff_x = h_x − a_x por definición: sus correlaciones con h_x y a_x son en parte algebraicas (M1, E5). "
             "season y last5 son idénticas si n_prev ≤ 5 (M3, E6). Sin targets.", fontsize=7.3, color=INK2, wrap=True)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    return fig


def figure_diff_by_result(tr):
    diffs = [f for f in ORDER if f.startswith("diff_")]
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.8), facecolor=SURFACE)
    axes = axes.ravel()
    for ax, f in zip(axes, diffs):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        data = [tr.loc[tr["result"] == c, f] for c in CLASSES]
        bp = ax.boxplot(data, whis=(5, 95), showfliers=False, widths=0.55, patch_artist=True,
                        medianprops={"color": INK, "linewidth": 1.4},
                        whiskerprops={"color": INK2}, capprops={"color": INK2})
        for patch, c in zip(bp["boxes"], CLASSES):
            patch.set_facecolor(COLOR[c]); patch.set_edgecolor(SURFACE); patch.set_linewidth(1.5)
        ax.axhline(0, color=INK2, linewidth=0.8, linestyle=(0, (3, 2)))
        ax.set_xticks([1, 2, 3], ["H", "D", "A"], color=INK, fontsize=9)
        meds = [d.median() for d in data]
        ax.set_title(f"{f}\nmedianas H {meds[0]:+.2f} · D {meds[1]:+.2f} · A {meds[2]:+.2f}",
                     loc="left", fontsize=8.3, color=INK)
    axes[-1].axis("off")
    n = {c: int((tr["result"] == c).sum()) for c in CLASSES}
    axes[-1].text(0, 0.75, f"TRAIN elegible 2021/22–2023/24\nH n = {n['H']} · D n = {n['D']} · A n = {n['A']}\n\n"
                  "Caja: Q1–Q3; línea: mediana;\nbigotes: P5–P95.\n\ndiff_ga > 0: el local recibe\nmás goles que el visitante.",
                  fontsize=8.5, color=INK2, va="top")
    fig.suptitle("Distribución de las diff_* según el resultado (H / D / A) — solo TRAIN; descriptivo, no predictivo",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    dev = eligible(io.DEV_PREDICTORS)                        # E4A: sin targets por construcción
    assert not set(io.TARGET_COLUMNS) & set(dev.columns)
    tr = eligible(io.TRAIN_TARGET)                           # E4B: único bloque con targets
    assert set(tr["season"].unique()) == set(io.SEASONS_TRAIN_DESIGN)

    pear, spear = corr_matrix(dev, "pearson"), corr_matrix(dev, "spearman")
    tables = {
        ("e04_pearson_predictors", io.DEV_PREDICTORS): pear,
        ("e04_spearman_predictors", io.DEV_PREDICTORS): spear,
        ("e04_pairwise_relationships", io.DEV_PREDICTORS): pairwise(dev),
        ("e04_goal_difference_relationships", io.TRAIN_TARGET): gd_relationships(tr),
        ("e04_features_by_result", io.TRAIN_TARGET): by_result(tr),
        ("e04_result_separation", io.TRAIN_TARGET): separation(tr),
    }
    diff_ps = (pear.set_index("feature")[ORDER] - spear.set_index("feature")[ORDER]).abs().to_numpy()
    meta = {"max_abs_pearson_minus_spearman": float(np.nanmax(diff_ps)),
            "mean_abs_pearson_minus_spearman": float(diff_ps[np.triu_indices(len(ORDER), 1)].mean()),
            "identity_share": identity_share(dev)}
    outputs = [io.write_table(t, name, phase=PHASE, scope=scope, out_root=out_root)
               for (name, scope), t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_heatmap(pear, "Pearson", len(dev)),
                                    "e04_feature_correlation_heatmap__DEVX.png", io.DEV_PREDICTORS))
        if meta["max_abs_pearson_minus_spearman"] >= 0.05:   # solo si Spearman aporta algo distinto
            outputs.append(_save_figure(figure_heatmap(spear, "Spearman", len(dev)),
                                        "e04_spearman_correlation_heatmap__DEVX.png", io.DEV_PREDICTORS))
        outputs.append(_save_figure(figure_diff_by_result(tr), "e04_diff_features_by_result__TRAIN.png",
                                    io.TRAIN_TARGET))
    return outputs, input_hashes, {**{k[0]: v for k, v in tables.items()}, "_meta": meta}
