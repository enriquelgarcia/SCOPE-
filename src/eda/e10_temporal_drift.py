"""E10 — Drift temporal y estabilidad entre temporadas (predictor-only).

Pregunta: ¿cuánto cambian las distribuciones de las features PRE-partido entre temporadas y entre
los bloques TRAIN (2021/22–2023/24), VALIDATION (2024/25) y FINAL TEST (2025/26)?

Población principal: filas elegibles (D48, min(h_n_prev, a_n_prev) ≥ 3). Features: las 21 de
historia (season h/a/diff de PPG, GF/PG, GA/PG; last5 h/a/diff de PPG, GF/PG, GA/PG, SOT/PG) más
h_/a_n_prev_season. Nunca se usan result, goal_difference, goles, POST ni MARKET.

Medidas (descriptivas, sin p-values ni umbrales):
  SMD = (mean_B − mean_A) / s_p,  s_p = sqrt(((n_A−1)s_A² + (n_B−1)s_B²) / (n_A + n_B − 2))
  KS  = max_x |F_A(x) − F_B(x)|, con F las ECDF empíricas (continuas por la derecha), evaluadas en
        la unión de los valores observados (implementación propia con NumPy, comprobada con casos
        simples en ks_selfcheck()).
Scopes: tablas por temporada y pares en ALL_DESCRIPTIVE; TRAIN→VAL desde DEV_PREDICTORS (__DEVX,
VAL contrastado con VAL_DESCRIPTIVE); TRAIN→TEST con TEST_DESCRIPTIVE (__TEST),
decision_use = DESCRIPTIVE_ONLY. Nada de TEST modifica features, burn-in ni ningún diseño.
Sin aleatoriedad (seed = null).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.eda import eda_io as io  # noqa: E402
from src.eda.e02_targets import GRID, INK, INK2, SURFACE, _style  # noqa: E402

PHASE = "E10"
SCOPES = ["ALL_DESCRIPTIVE", "DEV_PREDICTORS", "VAL_DESCRIPTIVE", "TEST_DESCRIPTIVE"]
SEED = None
NOTES = ("E10 drift temporal predictor-only (filas elegibles D48): resumen por temporada, SMD (s pooled) y "
         "KS propio entre temporadas consecutivas, TRAIN→VAL (DEVX) y TRAIN→TEST (DESCRIPTIVE_ONLY); familias; "
         "composición de equipos y sensibilidad con equipos comunes; cobertura de columnas fuente. Sin targets, "
         "sin umbrales, sin modelado; TEST no genera decisiones")
TRAIN, VAL, TEST = list(io.SEASONS_TRAIN_DESIGN), io.SEASON_VALIDATION, io.SEASON_FINAL_TEST
SEASONS = list(io.SEASONS_ALL)
METRICS = {"season": ("ppg", "gf_pg", "ga_pg"), "last5": ("ppg", "gf_pg", "ga_pg", "sot_pg")}
FEATURES = ([f"{s}_{m}_{w}" for w, ms in METRICS.items() for m in ms for s in ("h", "a", "diff")]
            + ["h_n_prev_season", "a_n_prev_season"])
SOURCE_FIELDS = ("Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HST", "AST")
WCOL = {"season": "#2a78d6", "last5": "#eb6834", "history": "#1baf7a"}


def meta(feature: str) -> dict:
    side, rest = feature.split("_", 1)
    if rest == "n_prev_season":
        return {"metric": "n_prev", "window": "history", "side": side}
    metric, window = rest.rsplit("_", 1)
    return {"metric": metric, "window": window, "side": side}


# ---------------------------------------------------------------------------
def ks(a, b) -> float:
    a, b = np.sort(np.asarray(a, float)), np.sort(np.asarray(b, float))
    grid = np.union1d(a, b)
    fa = np.searchsorted(a, grid, side="right") / len(a)
    fb = np.searchsorted(b, grid, side="right") / len(b)
    return float(np.max(np.abs(fa - fb)))


def ks_selfcheck() -> None:
    assert ks([1, 2, 3], [3, 2, 1]) == 0.0                      # idénticas
    assert ks([0, 0], [1, 1]) == 1.0                            # soporte disjunto
    assert ks([1, 2, 3, 4], [3, 4, 5, 6]) == 0.5                # desplazamiento parcial
    assert abs(ks([1, 1, 2], [1, 2, 2]) - 1 / 3) < 1e-12        # empates
    assert ks([5.0], [1, 2, 3, 4, 5]) == 0.8                    # tamaños distintos


def smd(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return float((b.mean() - a.mean()) / sp) if sp > 0 else 0.0


def describe(x: pd.Series) -> dict:
    q = x.quantile([0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95])
    return {"n": int(x.size), "mean": x.mean(), "median": q[0.5], "sd": x.std(ddof=1), "q1": q[0.25], "q3": q[0.75],
            "iqr": q[0.75] - q[0.25], "p5": q[0.05], "p10": q[0.10], "p90": q[0.90], "p95": q[0.95],
            "min": x.min(), "max": x.max()}


def compare(feature, label, a: pd.Series, b: pd.Series, decision_use: str) -> dict:
    return {"feature": feature, **meta(feature), "comparison": label, "decision_use": decision_use,
            "n_A": int(a.size), "n_B": int(b.size), "mean_A": a.mean(), "mean_B": b.mean(),
            "sd_A": a.std(ddof=1), "sd_B": b.std(ddof=1), "SMD": smd(a, b), "abs_SMD": abs(smd(a, b)), "KS": ks(a, b),
            "median_A": a.median(), "median_B": b.median(),
            "IQR_A": a.quantile(0.75) - a.quantile(0.25), "IQR_B": b.quantile(0.75) - b.quantile(0.25)}


# ---------------------------------------------------------------------------
def eligible(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["is_modeling_eligible"]].copy()
    assert out[FEATURES].notna().all().all()
    return out


def summary_by_season(el: pd.DataFrame) -> pd.DataFrame:
    rows = [{"feature": f, **meta(f), "season": s, "data_split": split_of(s), **describe(el.loc[el["season"] == s, f])}
            for f in FEATURES for s in SEASONS]
    return pd.DataFrame(rows)


def split_of(season: str) -> str:
    return "TRAIN" if season in TRAIN else "VALIDATION" if season == VAL else "FINAL_TEST"


def pairwise(el: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for f in FEATURES:
        for a, b in zip(SEASONS[:-1], SEASONS[1:]):
            use = "DESCRIPTIVE_ONLY" if TEST in (a, b) else "DEVELOPMENT_DESCRIPTIVE"
            rows.append(compare(f, f"{a}→{b}", el.loc[el["season"] == a, f], el.loc[el["season"] == b, f], use))
        tr = el.loc[el["season"].isin(TRAIN), f]
        rows.append(compare(f, "TRAIN→VALIDATION", tr, el.loc[el["season"] == VAL, f], "DEVELOPMENT_DESCRIPTIVE"))
        rows.append(compare(f, "TRAIN→FINAL_TEST", tr, el.loc[el["season"] == TEST, f], "DESCRIPTIVE_ONLY"))
    return pd.DataFrame(rows)


def block_table(train: pd.DataFrame, other: pd.DataFrame, label: str, use: str) -> pd.DataFrame:
    t = pd.DataFrame([compare(f, label, train[f], other[f], use) for f in FEATURES])
    t["rank_abs_SMD"] = t["abs_SMD"].rank(ascending=False, method="min").astype(int)
    t["rank_KS"] = t["KS"].rank(ascending=False, method="min").astype(int)
    t["top10_abs_SMD"] = t["rank_abs_SMD"] <= 10
    t["top10_KS"] = t["rank_KS"] <= 10
    return t.sort_values("rank_abs_SMD").reset_index(drop=True)


def family_summary(pw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    hist = pw[pw["window"] != "history"]
    for comp, g in hist.groupby("comparison", sort=False):
        for dim in ("metric", "window", "side"):
            for val, h in g.groupby(dim, sort=False):
                rows.append({"comparison": comp, "decision_use": h["decision_use"].iloc[0], "dimension": dim, "family": val,
                             "n_features": len(h), "median_abs_SMD": h["abs_SMD"].median(), "max_abs_SMD": h["abs_SMD"].max(),
                             "median_KS": h["KS"].median(), "max_KS": h["KS"].max()})
    return pd.DataFrame(rows)


def team_composition(can: pd.DataFrame, feat: pd.DataFrame) -> pd.DataFrame:
    teams = {s: set(can.loc[can["season"] == s, "home_team_id"]) | set(can.loc[can["season"] == s, "away_team_id"]) for s in SEASONS}
    rows = []
    for i, s in enumerate(SEASONS):
        prev = teams[SEASONS[i - 1]] if i else None
        rows.append({"season": s, "data_split": split_of(s), "n_teams": len(teams[s]),
                     "n_matches": int((feat["season"] == s).sum()), "n_eligible": int(feat.loc[feat["season"] == s, "is_modeling_eligible"].sum()),
                     "shared_with_previous": len(teams[s] & prev) if prev else None,
                     "entering": len(teams[s] - prev) if prev else None, "leaving": len(prev - teams[s]) if prev else None,
                     "entering_teams": "|".join(sorted(teams[s] - prev)) if prev else "",
                     "leaving_teams": "|".join(sorted(prev - teams[s])) if prev else ""})
    return pd.DataFrame(rows), teams


def team_match(el: pd.DataFrame, can: pd.DataFrame) -> pd.DataFrame:
    f = el.merge(can[["match_id", "home_team_id", "away_team_id"]], on="match_id", validate="one_to_one")
    cols = ["ppg_season", "gf_pg_season", "ga_pg_season", "sot_pg_last5"]
    parts = []
    for side, tcol in (("h", "home_team_id"), ("a", "away_team_id")):
        x = f[["season", tcol] + [f"{side}_{c}" for c in cols]].copy()
        x.columns = ["season", "team_id"] + cols
        parts.append(x)
    return pd.concat(parts, ignore_index=True), cols


def common_teams(tm, cols, teams) -> pd.DataFrame:
    rows = []
    for a, b in zip(SEASONS[:-1], SEASONS[1:]):
        common = teams[a] & teams[b]
        use = "DESCRIPTIVE_ONLY" if TEST in (a, b) else "DEVELOPMENT_DESCRIPTIVE"
        for c in cols:
            A, B = tm[tm["season"] == a], tm[tm["season"] == b]
            Ac, Bc = A[A["team_id"].isin(common)], B[B["team_id"].isin(common)]
            rows.append({"comparison": f"{a}→{b}", "decision_use": use, "feature_team_level": c, "n_common_teams": len(common),
                         "n_A_all": len(A), "n_B_all": len(B), "SMD_all": smd(A[c], B[c]), "KS_all": ks(A[c], B[c]),
                         "n_A_common": len(Ac), "n_B_common": len(Bc), "SMD_common": smd(Ac[c], Bc[c]), "KS_common": ks(Ac[c], Bc[c])})
    return pd.DataFrame(rows)


def source_coverage() -> pd.DataFrame:
    interim = pd.read_csv(io.INTERIM_FILE, dtype=str, keep_default_na=False)     # solo lectura
    rows = []
    for s, g in interim.groupby("season", sort=True):
        nonempty_cols = int((g != "").any().sum())
        rows.append({"season": s, "data_split": split_of(s), "rows": len(g), "interim_columns_nonempty": nonempty_cols,
                     **{f"empty_{c}": int((g[c] == "").sum()) for c in SOURCE_FIELDS}})
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


def figure_means(el):
    panels = [("ppg", "season"), ("gf_pg", "season"), ("ga_pg", "season"), ("sot_pg", "last5")]
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.9), facecolor=SURFACE, sharey=True)
    x = np.arange(len(SEASONS))
    tr = el[el["season"].isin(TRAIN)]
    for ax, (m, w) in zip(axes, panels):
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.axvspan(3.5, 4.5, color=GRID, alpha=0.6, linewidth=0)
        ax.axhline(0, color=INK2, linewidth=0.8)
        for side, col, mk in (("h", "#2a78d6", "o"), ("a", "#eb6834", "s")):
            f = f"{side}_{m}_{w}"
            z = [(el.loc[el["season"] == s, f].mean() - tr[f].mean()) / tr[f].std(ddof=1) for s in SEASONS]
            ax.plot(x, z, color=col, linewidth=2, marker=mk, ms=6, mec=SURFACE, mew=1.2, label="local (h_)" if side == "h" else "visitante (a_)")
        ax.set_xticks(x, [s[2:4] + "/" + s[7:] for s in SEASONS], fontsize=8.5, color=INK)
        ax.set_title(f"{m}_{w}", loc="left", fontsize=10, color=INK)
    axes[0].set_ylabel("(media temporada − media TRAIN) / DE TRAIN", color=INK2, fontsize=8.5)
    for ax in axes:
        lo, hi = ax.get_ylim()
        ax.text(4, hi - 0.03 * (hi - lo), "TEST\n(descriptivo)", ha="center", va="top", fontsize=7.5, color=INK2)
    fig.legend(*axes[0].get_legend_handles_labels(), ncol=2, loc="upper left", bbox_to_anchor=(0.01, 0.92), frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle("Media por temporada de features representativas, en unidades de DE de TRAIN — filas elegibles (D48)", x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.text(0.01, 0.01, "Estandarización solo para visualización (referencia TRAIN). 2025/26 = FINAL TEST: descriptivo, no decisional. Sin targets.", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    return fig


AX_MAX = (0.32, 0.17)        # ejes comunes a las dos figuras de dispersión (comparables entre sí)


def figure_scatter(t, title, footer, n_label=5):
    fig, ax = plt.subplots(figsize=(7.6, 4.6), facecolor=SURFACE)
    _style(ax)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for w in ("season", "last5", "history"):
        g = t[t["window"] == w]
        ax.scatter(g["abs_SMD"], g["KS"], s=42, color=WCOL[w], edgecolor=SURFACE, linewidth=1, label=w, zorder=3)
    lab = t[(t["rank_abs_SMD"] <= n_label) | (t["rank_KS"] <= n_label)].sort_values("KS", ascending=False)
    placed = []
    for r in lab.itertuples():                       # separa etiquetas de puntos cercanos
        dy = 3
        while any(abs(r.abs_SMD - x) < 0.06 and abs(r.KS + dy / 900 - y) < 0.006 for x, y in placed):
            dy -= 9
        placed.append((r.abs_SMD, r.KS + dy / 900))
        ax.annotate(r.feature, (r.abs_SMD, r.KS), xytext=(5, dy), textcoords="offset points", fontsize=7.5, color=INK)
    ax.set_xlim(0, AX_MAX[0])
    ax.set_ylim(0, AX_MAX[1])
    ax.set_xlabel("|SMD| (diferencia de medias en DE pooled)", color=INK2, fontsize=9)
    ax.set_ylabel("KS = max |F_A − F_B|", color=INK2, fontsize=9)
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=22)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=8.5, labelcolor=INK)
    fig.text(0.01, 0.01, footer, fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


# ---------------------------------------------------------------------------
def run(out_root=None):
    input_hashes = io.verify_frozen_inputs()
    ks_selfcheck()
    drop = list(io.TARGET_COLUMNS)
    feat_all = io.load_features(io.ALL_DESCRIPTIVE).drop(columns=drop)
    can = io.load_canonical(io.ALL_DESCRIPTIVE)[["match_id", "season", "home_team_id", "away_team_id"]]
    el = eligible(feat_all)
    # scopes específicos
    devx = eligible(io.load_features(io.DEV_PREDICTORS))
    val_d = eligible(io.load_features(io.VAL_DESCRIPTIVE).drop(columns=drop))
    test_d = eligible(io.load_features(io.TEST_DESCRIPTIVE).drop(columns=drop))
    assert set(devx["season"]) == set(TRAIN) | {VAL}
    dv_val = devx[devx["season"] == VAL].set_index("match_id")[FEATURES].sort_index()
    pd.testing.assert_frame_equal(dv_val, val_d.set_index("match_id")[FEATURES].sort_index())
    tr_dev = devx[devx["season"].isin(TRAIN)]

    summ = summary_by_season(el)
    pw = pairwise(el)
    tv = block_table(tr_dev, devx[devx["season"] == VAL], "TRAIN→VALIDATION", "DEVELOPMENT_DESCRIPTIVE")
    tt = block_table(tr_dev, test_d, "TRAIN→FINAL_TEST", "DESCRIPTIVE_ONLY")
    for t in (tv, tt):                                   # coherencia con la tabla ALL
        ref = pw[pw["comparison"] == t["comparison"].iloc[0]].set_index("feature").loc[t["feature"]]
        assert np.allclose(ref[["SMD", "KS"]].to_numpy(float), t[["SMD", "KS"]].to_numpy(float))
    fam = family_summary(pw)
    comp, teams = team_composition(can, feat_all)
    tm, cols = team_match(el, can)
    common = common_teams(tm, cols, teams)
    cov = source_coverage()

    tables = {
        ("e10_feature_summary_by_season", io.ALL_DESCRIPTIVE): summ,
        ("e10_pairwise_drift", io.ALL_DESCRIPTIVE): pw,
        ("e10_train_val_drift", io.DEV_PREDICTORS): tv,
        ("e10_train_test_drift", io.TEST_DESCRIPTIVE): tt,
        ("e10_family_drift_summary", io.ALL_DESCRIPTIVE): fam,
        ("e10_team_composition_by_season", io.ALL_DESCRIPTIVE): comp,
        ("e10_common_teams_sensitivity", io.ALL_DESCRIPTIVE): common,
        ("e10_source_coverage", io.ALL_DESCRIPTIVE): cov,
    }
    outputs = [io.write_table(t, name, phase=PHASE, scope=scope, out_root=out_root) for (name, scope), t in tables.items()]
    if out_root is None:
        outputs.append(_save_figure(figure_means(el), "e10_feature_means_by_season__ALL.png", io.ALL_DESCRIPTIVE))
        outputs.append(_save_figure(figure_scatter(
            tv, "TRAIN (2021/22–2023/24) → VALIDATION (2024/25): |SMD| vs KS por feature",
            "Filas elegibles (D48), predictor-only (DEVX). Ejes comunes con TRAIN→TEST. Sin umbrales ni p-values. Etiquetas: top 3.", n_label=3),
            "e10_train_val_drift__DEVX.png", io.DEV_PREDICTORS))
        outputs.append(_save_figure(figure_scatter(
            tt, "DESCRIPTIVE ONLY — FINAL TEST · TRAIN → 2025/26: |SMD| vs KS por feature",
            "Solo documentación: no modifica features, burn-in, selección, modelos ni calibración. Ejes comunes con TRAIN→VAL."),
            "e10_train_test_drift__TEST.png", io.TEST_DESCRIPTIVE))
    assert io.verify_frozen_inputs() == input_hashes
    return outputs, input_hashes, {k[0]: v for k, v in tables.items()}
