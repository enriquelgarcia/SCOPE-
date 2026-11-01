"""E5 — M1: estructura algebraica de las representaciones h / a / diff (scope DEV_PREDICTORS).

PREDICTOR-ONLY (1,399 filas elegibles DEVX, 2021/22–2024/25): sin `result`, `goal_difference`,
POST ni MARKET. No compara desempeño predictivo ni entrena modelos. Solo NumPy: SVD para rango y
valores singulares, mínimos cuadrados para el R² auxiliar del VIF. Sin aleatoriedad.

Criterio de rango (documentado, NO ajustado para forzar resultados): el de numpy.linalg.matrix_rank,
    tol = σ_max · max(n_filas, n_columnas) · ε_float64,
número de valores singulares > tol.
Estandarización (solo diagnóstico de geometría, no define el escalado futuro ni se guarda):
    z = (x − media_DEVX) / DE_DEVX (ddof = 1), ajustada sobre esta misma población.
Dependencia exacta en el VIF: si SSR/SST < 1e-12 (residuo de reconstrucción a nivel de precisión
float64) la variable se reconstruye exactamente con las demás → R² = 1 y VIF = ∞ conceptualmente.
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

PHASE = "E5"
SCOPE = io.DEV_PREDICTORS
SCOPES = ["DEV_PREDICTORS"]
NOTES = ("E5 M1 predictor-only sobre DEVX elegible (1,399): identidad diff = h − a, rango (SVD, tol de "
         "numpy.linalg.matrix_rank), condition number raw/estandarizado, VIF por R² auxiliar; sin targets, "
         "sin desempeño predictivo; sin aleatoriedad (seed=null)")
EXPECTED_N = 1399
EPS = np.finfo(np.float64).eps
EXACT_SSR_RATIO = 1e-12
HA = [f"{p}_{m}" for p in ("h", "a") for m in RATE_METRICS]
DIFF = [f"diff_{m}" for m in RATE_METRICS]
REPRESENTATIONS = {"HA": HA, "DIFF": DIFF, "HADIFF": HA + DIFF}
COLORS = {"HA": "#2a78d6", "DIFF": "#eb6834", "HADIFF": "#1baf7a"}


def load():
    df = io.load_features(SCOPE)
    assert not set(io.TARGET_COLUMNS) & set(df.columns)
    el = df[df["is_modeling_eligible"]].reset_index(drop=True)
    if len(el) != EXPECTED_N:
        raise RuntimeError(f"DEVX elegible = {len(el)}, se esperaban {EXPECTED_N}")
    return el


def standardize(X):
    return (X - X.mean(axis=0)) / X.std(axis=0, ddof=1)


def svd_report(X):
    s = np.linalg.svd(X, compute_uv=False)
    tol = s.max() * max(X.shape) * EPS
    rank = int((s > tol).sum())
    assert rank == np.linalg.matrix_rank(X)           # mismo criterio que numpy
    singular = rank < X.shape[1]
    return {"n_rows": X.shape[0], "n_columns": X.shape[1], "rank": rank, "nullity": X.shape[1] - rank,
            "rank_tolerance": tol, "sigma_max": s.max(), "sigma_min": s.min(),
            "sigma_min_over_tol": s.min() / tol,
            "smallest_nonnull_sigma": s[rank - 1] if rank else np.nan,
            "condition_number_numeric": s.max() / s.min() if s.min() > 0 else np.inf,
            "condition_number_interpretable": (not singular),
            "singular": singular, "singular_values": s}


# ---------------------------------------------------------------------------
def algebraic_identity(el):
    rows = []
    for m in RATE_METRICS:
        h, a, d = el[f"h_{m}"].to_numpy(), el[f"a_{m}"].to_numpy(), el[f"diff_{m}"].to_numpy()
        err = np.abs(d - (h - a))
        rows.append({"family": "last5" if m.endswith("last5") else "season", "metric": m,
                     "h_feature": f"h_{m}", "a_feature": f"a_{m}", "diff_feature": f"diff_{m}",
                     "n_rows": len(el), "max_abs_identity_error": err.max(),
                     "n_rows_exact_equality": int((err == 0).sum()), "tolerance": 1e-12,
                     "identity_verified": bool(err.max() <= 1e-12)})
    return pd.DataFrame(rows)


def rank_by_triplet(el):
    rows = []
    for m in RATE_METRICS:
        X = el[[f"h_{m}", f"a_{m}", f"diff_{m}"]].to_numpy()
        for scaling, M in (("raw", X), ("standardized", standardize(X))):
            r = svd_report(M)
            s = r.pop("singular_values")
            rows.append({"metric": m, "family": "last5" if m.endswith("last5") else "season",
                         "scaling": scaling, **r, "sigma_1": s[0], "sigma_2": s[1], "sigma_3": s[2]})
    return pd.DataFrame(rows)


def rank_by_representation(el):
    rows, svals = [], {}
    for name, cols in REPRESENTATIONS.items():
        X = el[cols].to_numpy()
        for scaling, M in (("raw", X), ("standardized", standardize(X))):
            for intercept in (False, True):
                A = np.column_stack([np.ones(len(M)), M]) if intercept else M
                r = svd_report(A)
                s = r.pop("singular_values")
                if not intercept:
                    svals[(name, scaling)] = s
                rows.append({"representation": name, "scaling": scaling,
                             "design": "[1, X]" if intercept else "X", **r})
    return pd.DataFrame(rows), svals


def vif(el):
    rows = []
    for name, cols in REPRESENTATIONS.items():
        X = el[cols].to_numpy()
        for j, col in enumerate(cols):
            y = X[:, j]
            others = np.column_stack([np.ones(len(X)), np.delete(X, j, axis=1)])   # con intercepto
            beta, *_ = np.linalg.lstsq(others, y, rcond=None)
            resid = y - others @ beta
            ssr, sst = float(resid @ resid), float(((y - y.mean()) ** 2).sum())
            ratio = ssr / sst
            exact = ratio < EXACT_SSR_RATIO
            r2 = 1.0 if exact else 1.0 - ratio
            rows.append({"representation": name, "feature": col, "n_regressors_excl_intercept": len(cols) - 1,
                         "ssr_over_sst": ratio, "max_abs_reconstruction_residual": float(np.abs(resid).max()),
                         "aux_r2": r2, "vif": np.inf if exact else 1.0 / ratio,
                         "vif_finite": not exact,
                         "exact_linear_dependence": exact})
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


def figure_singular_values(svals, rank_tab):
    fig, ax = plt.subplots(figsize=(8.6, 4.4), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    style = {"HADIFF": dict(linewidth=4.5, ms=11, alpha=0.55, zorder=1),   # debajo: sus 14 primeros ≈ HA
             "HA": dict(linewidth=2, ms=6, alpha=1.0, zorder=3),
             "DIFF": dict(linewidth=2, ms=6, alpha=1.0, zorder=3)}
    for name in ("HADIFF", "HA", "DIFF"):
        s = svals[(name, "standardized")]
        k = np.arange(1, len(s) + 1)
        st = style[name]
        ax.plot(k, s, color=COLORS[name], linewidth=st["linewidth"], marker="o", ms=st["ms"], mec=SURFACE,
                mew=1.2, alpha=st["alpha"], zorder=st["zorder"], label=f"{name} (d = {len(s)})")
    tol = rank_tab.query("representation == 'HADIFF' and scaling == 'standardized' and design == 'X'")["rank_tolerance"].iloc[0]
    ax.axhline(tol, color=INK2, linewidth=0.9, linestyle=(0, (3, 2)))
    ax.text(21.3, tol, "tolerancia de rango\n(matrix_rank)", fontsize=7.5, color=INK2, va="center")
    ax.set_yscale("log")
    ax.set_xlim(0.5, 24.5)
    ax.set_xticks([1, 5, 7, 10, 14, 15, 21])
    ax.set_xlabel("índice del valor singular (ordenados de mayor a menor)", color=INK2, fontsize=9)
    ax.set_ylabel("valor singular (escala log)", color=INK2, fontsize=9)
    s_had = svals[("HADIFF", "standardized")]
    ax.annotate("7 valores singulares ≈ 0\n(diff = h − a, nullity 7)", xy=(18, s_had[17]), xytext=(15.2, 1e-6),
                fontsize=8.5, color=INK, arrowprops={"arrowstyle": "-", "color": INK2, "linewidth": 0.8})
    ax.set_title("Valores singulares de las representaciones (columnas estandarizadas) — DEVX elegible, n = 1,399",
                 loc="left", fontsize=10.5, color=INK, pad=26)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, labelcolor=INK)
    fig.text(0.01, 0.01, "Estandarización solo diagnóstica (media y DE de esta misma población); no define el escalado futuro. Sin targets.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def figure_vif(vt):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), facecolor=SURFACE, gridspec_kw={"width_ratios": [14, 7]})
    for ax, name in zip(axes, ("HA", "DIFF")):
        _style(ax)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        d = vt[vt["representation"] == name].iloc[::-1]
        ax.barh(d["feature"], d["vif"], color=COLORS[name], height=0.65)
        for y, v in enumerate(d["vif"]):
            ax.text(v + 0.08, y, f"{v:.1f}", va="center", fontsize=8, color=INK)
        ax.tick_params(axis="y", labelsize=8, colors=INK)
        ax.set_xlabel("VIF = 1 / (1 − R² auxiliar)", color=INK2, fontsize=9)
        ax.set_title(f"{name} (d = {len(d)})", loc="left", fontsize=10, color=INK)
        ax.set_xlim(0, d["vif"].max() * 1.18)
    fig.suptitle("VIF descriptivo en HA y DIFF — DEVX elegible (HADIFF: VIF = ∞ en las 21 columnas, no se dibuja)",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, "Sin umbral de eliminación. Parte del VIF puede reflejar la identidad season = last5 cuando n_prev ≤ 5 (no verificado aquí; M3, E6).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    el = load()
    ident = algebraic_identity(el)
    if not ident["identity_verified"].all():
        raise RuntimeError("E5: la identidad diff = h − a no se verifica; revisar antes de continuar")
    rep_tab, svals = rank_by_representation(el)
    vt = vif(el)
    tables = {
        "e05_algebraic_identity": ident,
        "e05_rank_by_triplet": rank_by_triplet(el),
        "e05_rank_by_representation": rep_tab,
        "e05_vif": vt,
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=SCOPE, out_root=out_root) for name, t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_singular_values(svals, rep_tab), "e05_singular_values_by_representation__DEVX.png"))
        if vt.query("representation in ['HA', 'DIFF']")["vif_finite"].all():
            outputs.append(_save_figure(figure_vif(vt), "e05_vif_by_representation__DEVX.png"))
    return outputs, input_hashes, tables
