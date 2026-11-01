"""E8 — P02: evaluación de last5 como ventana de forma reciente.

E8A — DEV_PREDICTORS (2021/22–2024/25), predictor-only, formato team-match (equipo antes del
       partido): responsividad |x_t − x_(t−1)| de season y last5 dentro de cada team × season.
E8B — TRAIN_TARGET (2021/22–2023/24), diagnóstico target-aware: relaciona las features
       PRE-partido (season, last5, delta) con el resultado REALIZADO de ese mismo partido
       (team_match_log: points, goals_for, goals_against, shots_on_target_for), usado SOLO como
       outcome diagnóstico, nunca como predictor. VAL y TEST no participan.
Zona analizada: n_prev ≥ 6 (fuera de la identidad season = last5 de D47; el tramo n_prev ≤ 5 no
aporta evidencia independiente). No se construyen ventanas alternativas ni se crea FEATURES v0.2.
Convenciones: delta = last5 − season (PPG, GF); para GA, delta_ga_improvement = season − last5
(positivo = ha recibido menos goles recientemente que su media de temporada).
Bootstrap: unidad team-season (TRAIN), B = 2,000, semilla 42; IC 95 % percentil, descriptivos.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import GRID, INK, INK2, SURFACE, _style  # noqa: E402

PHASE = "E8"
SCOPES = ["DEV_PREDICTORS", "TRAIN_TARGET"]
SEED, B = 42, 2000
NOTES = ("E8 P02: E8A responsividad predictor-only en DEVX (team-match, n_prev ≥ 6); E8B diagnóstico "
         "target-aware solo TRAIN (features pre-partido vs resultado del propio partido como outcome); "
         "bootstrap por team-season B=2000 seed=42; sin modelado; sin ventanas alternativas")
METRICS = ("ppg", "gf_pg", "ga_pg")
OUTCOME = {"ppg": "points", "gf_pg": "goals_for", "ga_pg": "goals_against", "sot_pg": "shots_on_target_for"}
BINS = [("6–10", 6, 10), ("11–20", 11, 20), ("21–37", 21, 37)]
WCOL = {"season": "#2a78d6", "last5": "#eb6834"}


def ranks_corr(x, y):
    return x.rank().corr(y.rank())


def team_match(scope):
    """Formato team-match: una fila por equipo y partido, con las features PRE-partido de su lado."""
    feat = io.load_features(scope)
    teams = io.load_canonical(scope)[["match_id", "home_team_id", "away_team_id"]]
    f = feat.merge(teams, on="match_id", validate="one_to_one")
    cols = ["n_prev_season"] + [f"{m}_{w}" for m in METRICS for w in ("season", "last5")] + ["sot_pg_last5"]
    parts = []
    for side, tcol in (("h", "home_team_id"), ("a", "away_team_id")):
        x = f[["match_id", "season", "kickoff_datetime", tcol] + [f"{side}_{c}" for c in cols]].copy()
        x.columns = ["match_id", "season", "kickoff_datetime", "team_id"] + cols
        x["side"] = side
        parts.append(x)
    tm = pd.concat(parts, ignore_index=True).sort_values(["season", "team_id", "kickoff_datetime"]).reset_index(drop=True)
    assert not tm.duplicated(["match_id", "team_id"]).any()
    return tm


# ---------------------------------------------------------------------------
# E8A — DEVX
def responsiveness(tm):
    g = tm.groupby(["season", "team_id"], sort=False)
    rows = []
    for m in METRICS:
        for w in ("season", "last5"):
            col = f"{m}_{w}"
            step = g[col].diff()
            consecutive = g["n_prev_season"].diff() == 1
            for zone, lo, hi in [("n_prev ≥ 6 (fuera de identidad)", 6, 37)] + [(f"n_prev {l}", a, b) for l, a, b in BINS]:
                mask = consecutive & tm["n_prev_season"].between(lo, hi) & step.notna()
                a = step[mask].abs()
                rows.append({"metric": m, "window": w, "zone": zone, "population": "DEVX_team_match", "n": int(a.size),
                             "mean_abs_step": a.mean(), "median_abs_step": a.median(), "p75_abs_step": a.quantile(0.75),
                             "p90_abs_step": a.quantile(0.90), "zero_change_pct": 100 * (a <= 1e-12).mean(),
                             "max_abs_step": a.max()})
    out = pd.DataFrame(rows)
    piv = out.pivot_table(index=["metric", "zone"], columns="window", values="mean_abs_step")
    out["ratio_last5_over_season_mean_abs_step"] = out.apply(
        lambda r: piv.loc[(r["metric"], r["zone"]), "last5"] / piv.loc[(r["metric"], r["zone"]), "season"], axis=1)
    return out


# ---------------------------------------------------------------------------
# E8B — TRAIN
def train_frame():
    tm = team_match(io.TRAIN_TARGET)
    tml = io.load_team_match_log(io.TRAIN_TARGET)[["match_id", "team_id"] + list(OUTCOME.values())]
    d = tm.merge(tml, on=["match_id", "team_id"], validate="one_to_one")
    assert set(d["season"]) == set(io.SEASONS_TRAIN_DESIGN) and len(d) == 2 * 1140
    d = d[d["n_prev_season"] >= 6].reset_index(drop=True)        # fuera de identidad D47
    d["delta_ppg"] = d["ppg_last5"] - d["ppg_season"]
    d["delta_gf_pg"] = d["gf_pg_last5"] - d["gf_pg_season"]
    d["delta_ga_improvement"] = d["ga_pg_season"] - d["ga_pg_last5"]
    d["ts"] = d["season"] + "|" + d["team_id"]
    return d


def _boot_index(d):
    ts = d["ts"].unique()
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(ts), size=(B, len(ts)))
    groups = {t: np.flatnonzero(d["ts"].to_numpy() == t) for t in ts}
    return [np.concatenate([groups[ts[i]] for i in row]) for row in pick]


def _corr_np(x, y):
    x, y = x - x.mean(), y - y.mean()
    return float((x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum()))


def _rank(a):
    return pd.Series(a).rank().to_numpy()


def association(d, idx):
    rows, boot_rows = [], []
    for m in list(METRICS) + ["sot_pg"]:
        out = OUTCOME[m]
        windows = ("season", "last5") if m != "sot_pg" else ("last5",)
        for side in ("all", "h", "a"):
            s = d if side == "all" else d[d["side"] == side]
            for w in windows:
                x = s[f"{m}_{w}"]
                rows.append({"metric": m, "window": w, "outcome": out, "side": side,
                             "population": "TRAIN_team_match n_prev ≥ 6", "n": int(len(s)),
                             "pearson": x.corr(s[out]), "spearman": ranks_corr(x, s[out]),
                             "role": "auxiliar (sin versión season)" if m == "sot_pg" else "principal"})
        if m == "sot_pg":
            continue
        y, xs, xl = d[out].to_numpy(float), d[f"{m}_season"].to_numpy(float), d[f"{m}_last5"].to_numpy(float)
        bp_s, bp_l, bs_s, bs_l = [], [], [], []
        for ix in idx:
            yy, a, b = y[ix], xs[ix], xl[ix]
            bp_s.append(_corr_np(a, yy)); bp_l.append(_corr_np(b, yy))
            ry = _rank(yy); bs_s.append(_corr_np(_rank(a), ry)); bs_l.append(_corr_np(_rank(b), ry))
        for kind, cs, cl in (("pearson", np.array(bp_s), np.array(bp_l)), ("spearman", np.array(bs_s), np.array(bs_l))):
            full_s = d[f"{m}_season"].corr(d[out]) if kind == "pearson" else ranks_corr(d[f"{m}_season"], d[out])
            full_l = d[f"{m}_last5"].corr(d[out]) if kind == "pearson" else ranks_corr(d[f"{m}_last5"], d[out])
            dd = cl - cs
            boot_rows.append({"metric": m, "outcome": out, "coefficient": kind, "n": int(len(d)),
                              "corr_season": full_s, "corr_season_ci95_low": np.percentile(cs, 2.5), "corr_season_ci95_high": np.percentile(cs, 97.5),
                              "corr_last5": full_l, "corr_last5_ci95_low": np.percentile(cl, 2.5), "corr_last5_ci95_high": np.percentile(cl, 97.5),
                              "diff_last5_minus_season": full_l - full_s, "diff_ci95_low": np.percentile(dd, 2.5),
                              "diff_ci95_high": np.percentile(dd, 97.5), "diff_ci_contains_0": bool(np.percentile(dd, 2.5) <= 0 <= np.percentile(dd, 97.5)),
                              "bootstrap_unit": "team_season", "B": B, "seed": SEED})
    return pd.DataFrame(rows), pd.DataFrame(boot_rows)


DELTAS = [("ppg", "delta_ppg", "points", "last5 − season", "+"),
          ("gf_pg", "delta_gf_pg", "goals_for", "last5 − season", "+"),
          ("ga_pg", "delta_ga_improvement", "goals_against", "season − last5 (mejora defensiva)", "−")]


def delta_persistence(d, idx):
    rows, grows = [], []
    for m, dcol, out, conv, expected in DELTAS:
        x, y = d[dcol], d[out]
        xa, ya = x.to_numpy(float), y.to_numpy(float)
        bs = [_corr_np(_rank(xa[ix]), _rank(ya[ix])) for ix in idx]
        bp = [_corr_np(xa[ix], ya[ix]) for ix in idx]
        rows.append({"metric": m, "delta": dcol, "delta_convention": conv, "outcome": out,
                     "expected_sign_if_persistence": expected, "n": int(len(d)),
                     "pearson": x.corr(y), "pearson_ci95_low": np.percentile(bp, 2.5), "pearson_ci95_high": np.percentile(bp, 97.5),
                     "spearman": ranks_corr(x, y), "spearman_ci95_low": np.percentile(bs, 2.5), "spearman_ci95_high": np.percentile(bs, 97.5),
                     "bootstrap_unit": "team_season", "B": B, "seed": SEED})
        q1, q2 = x.quantile([1 / 3, 2 / 3])                     # cortes de terciles derivados SOLO de TRAIN
        tercile = np.where(x <= q1, "T1 (bajo)", np.where(x <= q2, "T2 (medio)", "T3 (alto)"))
        sign = np.where(x > 1e-12, "positivo", np.where(x < -1e-12, "negativo", "cero"))
        for kind, lab in (("tercil", tercile), ("signo", sign)):
            for g in sorted(set(lab)):
                s = y[lab == g]
                grows.append({"metric": m, "delta": dcol, "outcome": out, "grouping": kind, "group": g,
                              "tercile_cut_low": q1 if kind == "tercil" else np.nan,
                              "tercile_cut_high": q2 if kind == "tercil" else np.nan,
                              "n": int(s.size), "mean_outcome": s.mean(), "sd_outcome": s.std(ddof=1),
                              "mean_delta": x[lab == g].mean()})
    return pd.DataFrame(rows), pd.DataFrame(grows)


def evidence_summary(resp, boot, delta, e6_overall):
    rows = []
    o = e6_overall[(e6_overall["population"] == "A_DEVX_history") & (e6_overall["zone"].str.startswith("out_of_identity"))]
    for m, dcol, out, conv, exp in DELTAS:
        e6 = o[(o["metric"] == m) & (o["side"].isin(["h", "a"]))]
        r = resp[(resp["metric"] == m) & (resp["zone"].str.startswith("n_prev ≥ 6"))].set_index("window")
        b = boot[(boot["metric"] == m) & (boot["coefficient"] == "spearman")].iloc[0]
        dl = delta[delta["metric"] == m].iloc[0]
        rows.append({
            "metric": m,
            "devx_distinction_mae_out_of_identity_h_a": f"{e6['mae'].min():.3f}–{e6['mae'].max():.3f}",
            "devx_distinction_corr_out_of_identity_h_a": f"{e6['pearson'].min():.3f}–{e6['pearson'].max():.3f}",
            "devx_mean_abs_step_season": r.loc["season", "mean_abs_step"], "devx_mean_abs_step_last5": r.loc["last5", "mean_abs_step"],
            "devx_responsiveness_ratio": r.loc["last5", "mean_abs_step"] / r.loc["season", "mean_abs_step"],
            "train_spearman_season": b["corr_season"], "train_spearman_last5": b["corr_last5"],
            "train_spearman_diff_last5_minus_season": b["diff_last5_minus_season"],
            "train_diff_ci95": f"[{b['diff_ci95_low']:.3f}, {b['diff_ci95_high']:.3f}]",
            "train_delta_spearman": dl["spearman"], "train_delta_ci95": f"[{dl['spearman_ci95_low']:.3f}, {dl['spearman_ci95_high']:.3f}]",
            "train_delta_expected_sign": exp,
        })
    out = pd.DataFrame(rows)

    def interp(r):
        s = []
        s.append("distinta de season fuera de identidad (D47/E6)")
        s.append(f"≈{r['devx_responsiveness_ratio']:.1f}× más responsiva")
        lo, hi = [float(v) for v in r["train_diff_ci95"].strip("[]").split(",")]
        s.append("asociación con el partido siguiente menor que season" if hi < 0 else
                 "asociación mayor que season" if lo > 0 else "asociación no distinguible de season")
        dlo, dhi = [float(v) for v in r["train_delta_ci95"].strip("[]").split(",")]
        want_pos = r["train_delta_expected_sign"] == "+"
        if dlo <= 0 <= dhi:
            s.append("sin señal de persistencia del delta distinguible de 0")
        elif (dlo > 0) == want_pos:
            s.append("delta con señal de persistencia en el sentido esperado")
        else:
            s.append("delta con señal en sentido contrario al de persistencia")
        return "; ".join(s)
    out["descriptive_interpretation"] = out.apply(interp, axis=1)
    return out


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


def figure_responsiveness(resp):
    labels = [l for l, _, _ in BINS]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.9), facecolor=SURFACE, sharey=True)
    for ax, m in zip(axes, METRICS):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for w in ("season", "last5"):
            t = resp[(resp["metric"] == m) & (resp["window"] == w)].set_index("zone").loc[[f"n_prev {l}" for l in labels]]
            ax.plot(range(3), t["mean_abs_step"], color=WCOL[w], linewidth=2, marker="o", ms=7, mec=SURFACE, mew=1.5, label=w)
            for i, v in enumerate(t["mean_abs_step"]):
                ax.text(i, v, f"{v:.3f}", fontsize=7.5, color=INK, ha="center", va="bottom")
        ax.set_xticks(range(3), labels, fontsize=9, color=INK)
        ax.set_xlim(-0.4, 2.4)
        ax.set_title(m, loc="left", fontsize=10, color=INK)
        ax.set_xlabel("n_prev del equipo", color=INK2, fontsize=8.5)
    axes[0].set_ylabel("media de |x_t − x_(t−1)|", color=INK2, fontsize=9)
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=2, loc="upper left", bbox_to_anchor=(0.01, 0.93), frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle("Responsividad: cambio partido a partido de season vs last5 — DEVX team-match (predictor-only)", x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, "Más movimiento = más responsividad, no más capacidad predictiva. season pierde movimiento al crecer n (memoria completa); last5 lo mantiene (ventana de 5).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    return fig


def figure_association(boot):
    b = boot[boot["coefficient"] == "spearman"].set_index("metric").loc[list(METRICS)]
    fig, ax = plt.subplots(figsize=(8.4, 3.6), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ylab = {"ppg": "ppg → puntos del partido", "gf_pg": "gf_pg → goles a favor", "ga_pg": "ga_pg → goles en contra"}
    for i, m in enumerate(METRICS):
        for w, off in (("season", -0.13), ("last5", 0.13)):
            v, lo, hi = b.loc[m, f"corr_{w}"], b.loc[m, f"corr_{w}_ci95_low"], b.loc[m, f"corr_{w}_ci95_high"]
            ax.hlines(i + off, lo, hi, color=WCOL[w], linewidth=2)
            ax.plot(v, i + off, "o", ms=8, color=WCOL[w], mec=SURFACE, mew=1.5, label=w if i == 0 else None)
            ax.text(hi + 0.005, i + off, f"{v:.3f}", fontsize=8, color=INK, va="center")
    ax.axvline(0, color=INK2, linewidth=0.8)
    ax.set_yticks(range(3), [ylab[m] for m in METRICS], fontsize=9, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("Spearman con el resultado del propio partido (IC 95 % bootstrap por team-season)", color=INK2, fontsize=8.5)
    ax.set_title("season vs last5 (pre-partido) y desempeño en ese partido — TRAIN, n_prev ≥ 6",
                 loc="left", fontsize=10.5, color=INK, pad=24)
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, labelcolor=INK)
    fig.text(0.01, 0.01, "Asociación univariada descriptiva: no es rendimiento predictivo ni valor incremental. GA: signo positivo esperado (más GA previos ↔ más GA).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


def figure_delta(groups):
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.7), facecolor=SURFACE)
    lab = {"ppg": "delta_ppg → puntos", "gf_pg": "delta_gf → goles a favor", "ga_pg": "delta_ga_improvement → goles en contra"}
    for ax, m in zip(axes, METRICS):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        g = groups[(groups["metric"] == m) & (groups["grouping"] == "tercil")].sort_values("group")
        se = g["sd_outcome"] / np.sqrt(g["n"])
        ax.bar(range(3), g["mean_outcome"], color="#2a78d6", width=0.6)
        ax.errorbar(range(3), g["mean_outcome"], yerr=1.96 * se, fmt="none", ecolor=INK2, capsize=3, linewidth=1)
        for i, v in enumerate(g["mean_outcome"]):
            ax.text(i, v / 2, f"{v:.2f}", color="white", ha="center", va="center", fontsize=8.5)
        ax.set_xticks(range(3), ["T1 bajo", "T2 medio", "T3 alto"], fontsize=8.5, color=INK)
        ax.set_title(lab[m], loc="left", fontsize=9, color=INK)
    axes[0].set_ylabel("outcome medio en el partido", color=INK2, fontsize=8.5)
    fig.suptitle("Resultado del partido según el tercil de la desviación reciente (last5 vs season) — solo TRAIN, n_prev ≥ 6",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, "Terciles derivados solo de TRAIN. Barras de error: ±1.96·EE ingenuo (ignora la dependencia entre partidos; solo orientativo). Descriptivo, no causal.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    dev = team_match(io.DEV_PREDICTORS)
    assert not set(io.TARGET_COLUMNS) & set(dev.columns)
    resp = responsiveness(dev)
    d = train_frame()
    idx = _boot_index(d)
    assoc, boot = association(d, idx)
    delta, groups = delta_persistence(d, idx)
    e6 = pd.read_csv(io.EDA_TABLES_DIR / "e06_season_last5_overall__DEVX.csv")   # resultado aprobado de E6 (D47)
    summ = evidence_summary(resp, boot, delta, e6)
    tables = {
        ("e08_responsiveness", io.DEV_PREDICTORS): resp,
        ("e08_next_match_association", io.TRAIN_TARGET): assoc,
        ("e08_association_bootstrap", io.TRAIN_TARGET): boot,
        ("e08_delta_persistence", io.TRAIN_TARGET): delta,
        ("e08_delta_groups", io.TRAIN_TARGET): groups,
        ("e08_window_evidence_summary", io.TRAIN_TARGET): summ,
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=scope, out_root=out_root) for (name, scope), t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_responsiveness(resp), "e08_responsiveness_season_vs_last5__DEVX.png", io.DEV_PREDICTORS))
        outputs.append(_save_figure(figure_association(boot), "e08_next_match_association__TRAIN.png", io.TRAIN_TARGET))
        outputs.append(_save_figure(figure_delta(groups), "e08_delta_persistence__TRAIN.png", io.TRAIN_TARGET))
    return outputs, input_hashes, {k[0]: v for k, v in tables.items()}
