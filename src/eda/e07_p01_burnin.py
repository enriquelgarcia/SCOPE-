"""E7 — P01: evaluación del burn-in (umbral mínimo de historial previo).

Regla evaluada: un partido es elegible si min(h_n_prev_season, a_n_prev_season) ≥ k, k = 1…6
(k = 3 es la regla provisional actual y se trata igual que las demás). Sin modelado.

E7A — DEV_PREDICTORS (2021/22–2024/25), predictor-only: coste en filas por k, dispersión y extremos
       de las features de equipo según su n_prev (lado propio). Sin targets.
E7B — TRAIN_TARGET (2021/22–2023/24), ANÁLISIS RETROSPECTIVO DE ESTABILIDAD: compara la estimación
       disponible tras n partidos (valor de FEATURES) con una referencia de temporada completa
       (38 partidos, calculada desde team_match_log). La referencia usa información FUTURA a
       propósito; NO es una feature, NO se guarda en FEATURES y NO se usa en VAL ni TEST. No es un
       "valor verdadero": es una referencia retrospectiva más estable.
Unidades: elegibilidad de PARTIDOS → min(h_n, a_n); estabilidad de una feature de EQUIPO → n_prev
de su lado. Por D47, para n_prev ≤ 5 las features last5 de PPG/GF/GA son idénticas a las season y no
aportan evidencia independiente; sot_pg_last5 sí (no tiene versión season).
Bootstrap: unidad = team-season completo (TRAIN, 60), B = 2,000, semilla 42; IC 95 % percentil,
descriptivos y condicionados a los team-seasons observados.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import GRID, INK, INK2, SURFACE, _style  # noqa: E402
from src.eda.e03_univariate import fences  # noqa: E402  (misma regla de extremos que E3)

PHASE = "E7"
SCOPES = ["DEV_PREDICTORS", "TRAIN_TARGET"]
SEED, B = 42, 2000
NOTES = ("E7 P01: E7A predictor-only en DEVX (coste por k = 1…6, dispersión por n_prev); E7B retrospectivo "
         "solo TRAIN (estimación tras n partidos vs referencia de temporada completa, solo diagnóstico, nunca "
         "feature); bootstrap por team-season B=2000 seed=42; sin modelado; VAL/TEST excluidos de E7B")
KS = (1, 2, 3, 4, 5, 6)
EXACT = (1, 2, 3, 4, 5)
MATURE = [("6–10", 6, 10), ("11–20", 11, 20), ("21–37", 21, 37)]
SEASON_M = ("ppg_season", "gf_pg_season", "ga_pg_season")
LAST5_M = ("ppg_last5", "gf_pg_last5", "ga_pg_last5", "sot_pg_last5")
REF = {"ppg": ("points", "ppg_season"), "gf_pg": ("goals_for", "gf_pg_season"),
       "ga_pg": ("goals_against", "ga_pg_season"), "sot_pg": ("shots_on_target_for", "sot_pg_last5")}
COL = {"ppg": "#2a78d6", "gf_pg": "#eb6834", "ga_pg": "#1baf7a", "sot_pg": "#eda100"}


def _levels():
    return [(str(n), n, n) for n in EXACT] + MATURE


# ---------------------------------------------------------------------------
# E7A — DEVX predictor-only
def retention(dev):
    mn = dev[["h_n_prev_season", "a_n_prev_season"]].min(axis=1)
    rows = []
    groups = [("season", s, dev["season"] == s) for s in io.SEASONS_DEV]
    groups += [("TRAIN_seasons_total", "ALL", dev["season"].isin(io.SEASONS_TRAIN_DESIGN)),
               ("DEVX_total", "ALL", pd.Series(True, index=dev.index))]
    for gtype, season, g in groups:
        total = int(g.sum())
        prev = None
        for k in KS:
            el = int((g & (mn >= k)).sum())
            rows.append({"group": gtype, "season": season, "k": k, "is_current_rule": k == 3, "matches_total": total,
                         "eligible": el, "excluded": total - el, "pct_retained": 100 * el / total,
                         "pct_lost": 100 * (total - el) / total,
                         "marginal_lost_vs_k_minus_1": (prev - el) if prev is not None else total - el})
            prev = el
    return pd.DataFrame(rows)


def stability(dev):
    el = dev[dev["is_modeling_eligible"]]
    rows = []
    for side in ("h", "a"):
        n = dev[f"{side}_n_prev_season"]
        for m in SEASON_M + LAST5_M:
            col = f"{side}_{m}"
            lo, hi = fences(el[col])                       # vallas de Tukey de E3 (DEVX elegible)
            for lab, a, b in _levels():
                s = dev.loc[n.between(a, b), col]
                q = s.quantile([0.05, 0.25, 0.75, 0.95])
                rows.append({"feature": col, "side": side, "metric": m,
                             "window": "last5" if m.endswith("last5") else "season",
                             "identical_to_season_by_D47": (m != "sot_pg_last5" and m.endswith("last5") and b <= 5),
                             "n_prev_level": lab, "population": "DEVX_all_rows_with_history", "n": int(s.size),
                             "mean": s.mean(), "std": s.std(ddof=1), "iqr": q[0.75] - q[0.25], "p5": q[0.05],
                             "p95": q[0.95], "pct_beyond_e3_tukey": 100 * ((s < lo) | (s > hi)).mean()})
    return pd.DataFrame(rows)


def dispersion_increments(stab):
    rows = []
    for (col, side, m), g in stab.groupby(["feature", "side", "metric"]):
        g = g.set_index("n_prev_level")
        for a, b in zip(EXACT[:-1], EXACT[1:]):
            r = {"feature": col, "side": side, "metric": m, "step": f"{a}→{b}",
                 "identical_to_season_by_D47": bool(g.loc[str(b), "identical_to_season_by_D47"])}
            for stat in ("std", "iqr", "pct_beyond_e3_tukey"):
                x0, x1 = g.loc[str(a), stat], g.loc[str(b), stat]
                r[f"{stat}_from"], r[f"{stat}_to"] = x0, x1
                r[f"{stat}_change_pct"] = 100 * (x1 - x0) / x0 if x0 else np.nan
            r["std_at_21_37"] = g.loc["21–37", "std"]
            rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E7B — TRAIN retrospectivo
def early_vs_final_frame():
    """Una fila por team-season × n_prev (1–5 y 10 como referencia de madurez)."""
    feat = io.load_features(io.TRAIN_TARGET)
    teams = io.load_canonical(io.TRAIN_TARGET)[["match_id", "home_team_id", "away_team_id"]]
    tml = io.load_team_match_log(io.TRAIN_TARGET)
    assert set(feat["season"]) == set(tml["season"]) == set(io.SEASONS_TRAIN_DESIGN)
    f = feat.merge(teams, on="match_id", validate="one_to_one")
    long = []
    for side, tcol in (("h", "home_team_id"), ("a", "away_team_id")):
        x = f[["season", tcol, f"{side}_n_prev_season"] + [f"{side}_{v}" for _, v in REF.values()]].copy()
        x.columns = ["season", "team_id", "n_prev"] + [v for _, v in REF.values()]
        long.append(x)
    early = pd.concat(long, ignore_index=True)
    levels = EXACT + (10,)
    early = early[early["n_prev"].isin(levels)]
    assert not early.duplicated(["season", "team_id", "n_prev"]).any()      # un valor por team-season y n
    # Referencia retrospectiva de temporada completa (38 partidos) y control: recomputar la estimación temprana
    tml = tml.sort_values(["season", "team_id", "kickoff_datetime"])
    tml["k"] = tml.groupby(["season", "team_id"]).cumcount() + 1
    final = tml.groupby(["season", "team_id"]).agg(n_matches=("k", "max"),
                                                   **{f"final_{m}": (src, "mean") for m, (src, _) in REF.items()})
    assert (final["n_matches"] == 38).all()
    for m, (src, fcol) in REF.items():
        cum = tml.groupby(["season", "team_id"])[src].cumsum() / tml["k"]
        tml[f"cum_{m}"] = cum
    chk = early.merge(tml.assign(n_prev=tml["k"])[["season", "team_id", "n_prev"] + [f"cum_{m}" for m in REF]],
                      on=["season", "team_id", "n_prev"])
    for m, (_, fcol) in REF.items():
        if m == "sot_pg":
            chk_mask = chk["n_prev"] <= 5          # sot_pg_last5 = media de todos los previos solo si n ≤ 5
        else:
            chk_mask = pd.Series(True, index=chk.index)
        err = (chk.loc[chk_mask, fcol] - chk.loc[chk_mask, f"cum_{m}"]).abs().max()
        assert err <= 1e-12, f"control de estimación temprana falla para {m}: {err}"
    out = early.merge(final.reset_index(), on=["season", "team_id"], validate="many_to_one")
    for m, (_, fcol) in REF.items():
        out[f"err_{m}"] = out[fcol] - out[f"final_{m}"]
    out.loc[out["n_prev"] > 5, "err_sot_pg"] = np.nan    # sot_last5 deja de ser acumulado tras n = 5
    return out


def early_vs_final(ev):
    rows = []
    for m in REF:
        for n in EXACT + (10,):
            e = ev.loc[ev["n_prev"] == n, f"err_{m}"].dropna()
            if e.empty:
                continue
            a = e.abs()
            rows.append({"metric": m, "estimate_feature": REF[m][1], "n_prev": n,
                         "role": "nivel temprano" if n <= 5 else "referencia de madurez",
                         "team_seasons": int(e.size), "overlap_with_reference_pct": 100 * n / 38,
                         "bias_mean": e.mean(), "mae": a.mean(), "rmse": float(np.sqrt((e ** 2).mean())),
                         "median_abs": a.median(), "q1_abs": a.quantile(0.25), "q3_abs": a.quantile(0.75),
                         "p90_abs": a.quantile(0.90), "p95_abs": a.quantile(0.95)})
    return pd.DataFrame(rows)


def bootstrap_tradeoff(ev, ret_train):
    rng = np.random.default_rng(SEED)
    ts = ev[["season", "team_id"]].drop_duplicates().reset_index(drop=True)
    idx = rng.integers(0, len(ts), size=(B, len(ts)))
    cost = ret_train.set_index("k")
    rows = []
    for m in REF:
        wide = ev[ev["n_prev"].isin(EXACT)].pivot_table(index=["season", "team_id"], columns="n_prev",
                                                        values=f"err_{m}").reindex(pd.MultiIndex.from_frame(ts))
        A = wide.abs().to_numpy()                        # team-seasons × n(1..5)
        boot = A[idx].mean(axis=1)                       # B × 5 (MAE por réplica)
        mae = A.mean(axis=0)
        for j, (a, b) in enumerate(zip(EXACT[:-1], EXACT[1:])):
            imp = boot[:, j] - boot[:, j + 1]
            rows.append({"metric": m, "step": f"{a}→{b}", "threshold_change": f"k={a} → k={b}",
                         "mae_from": mae[j], "mae_to": mae[j + 1],
                         "mae_from_ci95_low": np.percentile(boot[:, j], 2.5), "mae_from_ci95_high": np.percentile(boot[:, j], 97.5),
                         "mae_to_ci95_low": np.percentile(boot[:, j + 1], 2.5), "mae_to_ci95_high": np.percentile(boot[:, j + 1], 97.5),
                         "mae_improvement": mae[j] - mae[j + 1], "mae_improvement_pct": 100 * (mae[j] - mae[j + 1]) / mae[j],
                         "improvement_ci95_low": np.percentile(imp, 2.5), "improvement_ci95_high": np.percentile(imp, 97.5),
                         "share_boot_improvement_gt_0": float((imp > 0).mean()),
                         "train_matches_lost_by_step": int(cost.loc[b, "marginal_lost_vs_k_minus_1"]),
                         "train_eligible_after_step": int(cost.loc[b, "eligible"]),
                         "bootstrap_unit": "team_season", "B": B, "seed": SEED})
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


def figure_stability(stab):
    labels = [l for l, _, _ in _levels()]
    sel = [("h_ppg_season", "ppg"), ("h_gf_pg_season", "gf_pg"), ("h_ga_pg_season", "ga_pg"), ("h_sot_pg_last5", "sot_pg")]
    fig, ax = plt.subplots(figsize=(9, 4.3), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    x = np.arange(len(labels))
    for col, m in sel:
        t = stab[stab["feature"] == col].set_index("n_prev_level").loc[labels]
        idx = t["std"] / t.loc["21–37", "std"]
        ax.plot(x, idx, color=COL[m], linewidth=2, marker="o", ms=7, mec=SURFACE, mew=1.5, label=col)
    ax.axhline(1, color=INK2, linewidth=0.8)
    ax.axvspan(-0.4, 4.4, color=GRID, alpha=0.35, zorder=0)
    ax.text(2, ax.get_ylim()[1] * 0.97, "niveles exactos 1–5", ha="center", va="top", fontsize=8, color=INK2)
    ax.set_xticks(x, labels, fontsize=9, color=INK)
    ax.set_xlabel("partidos previos del equipo en la temporada (n_prev de su lado)", color=INK2, fontsize=9)
    ax.set_ylabel("DE del nivel / DE con 21–37 partidos", color=INK2, fontsize=9)
    ax.set_title("Dispersión entre equipos de las features según historial — DEVX (todas las filas con historial; lado h)",
                 loc="left", fontsize=10.5, color=INK, pad=26)
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=8.5, labelcolor=INK)
    fig.text(0.01, 0.01, "Predictor-only. Con n_prev ≤ 5, ppg/gf/ga last5 = season (D47): no se dibujan aparte. Lado a casi idéntico (ver tabla).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def figure_mae(boot, evf):
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.9), facecolor=SURFACE)
    for ax, m in zip(axes, REF):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        b = boot[boot["metric"] == m]
        mae = [b["mae_from"].iloc[0]] + list(b["mae_to"])
        lo = [b["mae_from_ci95_low"].iloc[0]] + list(b["mae_to_ci95_low"])
        hi = [b["mae_from_ci95_high"].iloc[0]] + list(b["mae_to_ci95_high"])
        x = np.array(EXACT)
        ax.fill_between(x, lo, hi, color=COL[m], alpha=0.18, linewidth=0)
        ax.plot(x, mae, color=COL[m], linewidth=2, marker="o", ms=7, mec=SURFACE, mew=1.5)
        for xi, v in zip(x, mae):
            ax.text(xi, v, f"{v:.2f}", fontsize=7.5, color=INK, ha="center", va="bottom")
        r10 = evf[(evf["metric"] == m) & (evf["n_prev"] == 10)]
        if len(r10):
            ax.axhline(r10["mae"].iloc[0], color=INK2, linewidth=0.8, linestyle=(0, (3, 2)))
            ax.text(5.1, r10["mae"].iloc[0], "n = 10", fontsize=7.5, color=INK2, va="bottom", ha="right")
        ax.set_xticks(x)
        ax.set_ylim(0, None)
        ax.set_title(f"{REF[m][1]}", loc="left", fontsize=9.5, color=INK)
        ax.set_xlabel("n_prev", color=INK2, fontsize=8.5)
    axes[0].set_ylabel("MAE vs referencia de temporada completa", color=INK2, fontsize=8.5)
    fig.suptitle("Error de la estimación tras n partidos frente a la referencia retrospectiva de 38 partidos — solo TRAIN (60 team-seasons)",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, "Análisis retrospectivo de estabilidad (usa información futura; nunca es feature). Banda: IC 95 % bootstrap por team-season "
             "(B = 2,000, seed 42). La referencia no es un 'valor verdadero'.", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    dev = io.load_features(io.DEV_PREDICTORS)
    assert not set(io.TARGET_COLUMNS) & set(dev.columns)
    if int(dev["is_modeling_eligible"].sum()) != 1399:
        raise RuntimeError("DEVX elegible ≠ 1,399")
    ret = retention(dev)
    stab = stability(dev)
    ev = early_vs_final_frame()                      # TRAIN únicamente
    evf = early_vs_final(ev)
    ret_train = ret[ret["group"] == "TRAIN_seasons_total"]
    boot = bootstrap_tradeoff(ev, ret_train)
    tables = {
        ("e07_burnin_retention", io.DEV_PREDICTORS): ret,
        ("e07_feature_stability_by_n_prev", io.DEV_PREDICTORS): stab,
        ("e07_dispersion_increments", io.DEV_PREDICTORS): dispersion_increments(stab),
        ("e07_early_vs_final_stability", io.TRAIN_TARGET): evf,
        ("e07_incremental_tradeoff", io.TRAIN_TARGET): boot,
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=scope, out_root=out_root) for (name, scope), t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_stability(stab), "e07_stability_by_n_prev__DEVX.png", io.DEV_PREDICTORS))
        outputs.append(_save_figure(figure_mae(boot, evf), "e07_early_vs_final_mae__TRAIN.png", io.TRAIN_TARGET))
    return outputs, input_hashes, {k[0]: v for k, v in tables.items()}
