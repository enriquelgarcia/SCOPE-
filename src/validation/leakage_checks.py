"""V14 (perturbación) y V15 (oráculo): defensa principal contra data leakage.

V14 trabaja sobre CANONICAL tipado y vuelve a ejecutar el builder real (búsqueda del
módulo en tiempo de llamada, para que las autopruebas puedan sustituir piezas defectuosas).
V15 es independiente del builder: lee CANONICAL y FEATURES como texto y recalcula cada
feature con filtrado explícito `kickoff < t`, sin team_match_log, shift ni rolling.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import datetime

from src.config import settings
from src.data import build_features as BF
from src.data.build_canonical import compute_dq_flags
from src.data.features_schema import DIFF_METRICS, FEATURES_COLUMNS, RATE_METRICS, TEAM_METRICS
from src.validation.features_checks import fnum, schema_guard
from src.validation.results import CheckResult

_SIDE_COLS = {p: [f"{p}_{m}" for m in TEAM_METRICS] for p in ("h", "a")}
_DIFF_COLS = [f"diff_{m}" for m in DIFF_METRICS]
_LABELS = ("result", "goal_difference")


def _sign(x: int) -> str:
    return "H" if x > 0 else "A" if x < 0 else "D"


# ================================================================== V14
def perturb_match(match: dict) -> dict:
    """Alteración internamente coherente: invierte el ganador (o rompe el empate) subiendo
    goles finales (HT ≤ FT se mantiene), suma 1 tiro y 1 tiro a puerta a cada lado y
    recalcula goal_difference, result y dq_flags."""
    m = dict(match)
    if m["result"] == "H":
        m["away_goals"] = m["home_goals"] + 1
    elif m["result"] == "A":
        m["home_goals"] = m["away_goals"] + 1
    else:
        m["home_goals"] += 1
    for side in ("home", "away"):
        m[f"{side}_shots"] += 1
        m[f"{side}_shots_on_target"] += 1
    m["goal_difference"] = m["home_goals"] - m["away_goals"]
    m["result"] = _sign(m["goal_difference"])
    m["dq_flags"] = compute_dq_flags(m)
    assert m["ht_home_goals"] <= m["home_goals"] and m["ht_away_goals"] <= m["away_goals"]
    assert m["result"] != match["result"]
    return m


def v14_sample(canonical: list[dict]) -> list[str]:
    ids = sorted(m["match_id"] for m in canonical)
    sample = set(random.Random(settings.LEAKAGE_SEED).sample(ids, settings.LEAKAGE_RANDOM_SAMPLE))
    anomalies = {m["match_id"] for m in canonical if m["dq_flags"] or
                 (m["source_file"], m["source_row"]) == ("PL_2023-2024_raw.csv", 357)}
    return sorted(sample | anomalies)


def check_v14(canonical: list[dict], baseline: list[dict] | None = None) -> CheckResult:
    r = CheckResult("V14", "Perturbación coherente: invariantes (negativos) y cambio posterior (positivo)")
    base = {x["match_id"]: x for x in (baseline or BF.build_features(canonical)[1])}
    by_id = {m["match_id"]: m for m in canonical}
    sample = v14_sample(canonical)
    neg = Counter()
    pos_applicable = pos_ok = 0
    for tid in sample:
        t = by_id[tid]
        involved = {t["home_team_id"], t["away_team_id"]}
        pert = [perturb_match(m) if m["match_id"] == tid else m for m in canonical]
        new = {x["match_id"]: x for x in BF.build_features(pert)[1]}
        next_match = {}
        for m in sorted(canonical, key=lambda m: m["kickoff_datetime"]):
            if m["season"] == t["season"] and m["kickoff_datetime"] > t["kickoff_datetime"]:
                for side, p in (("home", "h"), ("away", "a")):
                    if m[f"{side}_team_id"] in involved:
                        next_match.setdefault(m[f"{side}_team_id"], (m["match_id"], p))
        for mid, b in base.items():
            m, n = by_id[mid], new[mid]
            may = {}
            for side, p in (("home", "h"), ("away", "a")):
                may[p] = (m[f"{side}_team_id"] in involved and m["season"] == t["season"]
                          and m["kickoff_datetime"] > t["kickoff_datetime"])
            if mid == tid:
                category = "propio_t"
            elif m["season"] != t["season"]:
                category = "otras_temporadas"
            elif m["kickoff_datetime"] <= t["kickoff_datetime"]:
                category = "anteriores_o_simultaneos"
            else:
                category = "posteriores"
            checked = [c for p in ("h", "a") if not may[p] for c in _SIDE_COLS[p]]
            if not (may["h"] or may["a"]):
                checked += _DIFF_COLS + ["is_modeling_eligible"]
            if mid != tid:
                checked += list(_LABELS)
            checked += ["match_id", "season", "kickoff_datetime", "feature_version"]
            for c in checked:
                if b[c] != n[c]:
                    r.fail(f"t={tid}: {mid} {c} cambió ({b[c]!r} → {n[c]!r}) [{category}]")
            neg[category] += 1
            if category == "posteriores" and not (may["h"] or may["a"]):
                neg["posteriores_equipos_no_involucrados"] += 1
        for team, (mid, p) in next_match.items():
            pos_applicable += 1
            if any(base[mid][c] != new[mid][c] for c in _SIDE_COLS[p][1:]):
                pos_ok += 1
            else:
                r.fail(f"t={tid}: control positivo sin cambio en {mid} ({team}, lado {p})")
    r.info.append(f"Partidos perturbados: {len(sample)} (100 aleatorios con semilla "
                  f"{settings.LEAKAGE_SEED} ∪ anomalías conocidas)")
    r.info.append(f"Comparaciones de control negativo (filas×perturbación) por categoría: {dict(neg)}")
    r.info.append(f"Controles positivos aplicables: {pos_applicable}; con cambio detectado: {pos_ok}; "
                  f"no aplicables (último partido del equipo en la temporada): {2 * len(sample) - pos_applicable}")
    return r


# ================================================================== V15
class Oracle:
    """Recalcula features desde CANONICAL (texto) con filtrado explícito kickoff < t."""

    def __init__(self, canonical_rows: list[dict[str, str]]):
        self.rows = canonical_rows
        self.ko = [datetime.fromisoformat(m["kickoff_datetime"]) for m in canonical_rows]

    def team_history(self, team: str, season: str, t_ko: datetime) -> list[dict]:
        hist = []
        for m, ko in zip(self.rows, self.ko):
            if m["season"] != season or ko >= t_ko:
                continue
            if m["home_team_id"] == team:
                gf, ga, sot = int(m["home_goals"]), int(m["away_goals"]), int(m["home_shots_on_target"])
            elif m["away_team_id"] == team:
                gf, ga, sot = int(m["away_goals"]), int(m["home_goals"]), int(m["away_shots_on_target"])
            else:
                continue
            pts = 3 if gf > ga else (1 if gf == ga else 0)
            hist.append({"ko": ko, "gf": gf, "ga": ga, "pts": pts, "sot": sot})
        hist.sort(key=lambda e: e["ko"])
        return hist

    @staticmethod
    def metrics(hist: list[dict]) -> dict:
        n = len(hist)
        if n == 0:
            return {"n_prev_season": 0, **{m: None for m in RATE_METRICS}}
        k = min(settings.LAST_N, n)
        last = hist[n - k:]
        avg = lambda xs, key: sum(e[key] for e in xs) / len(xs)
        return {"n_prev_season": n,
                "ppg_season": avg(hist, "pts"), "gf_pg_season": avg(hist, "gf"), "ga_pg_season": avg(hist, "ga"),
                "ppg_last5": avg(last, "pts"), "gf_pg_last5": avg(last, "gf"), "ga_pg_last5": avg(last, "ga"),
                "sot_pg_last5": avg(last, "sot")}

    def features_for(self, m: dict[str, str]) -> dict:
        t_ko = datetime.fromisoformat(m["kickoff_datetime"])
        h = self.metrics(self.team_history(m["home_team_id"], m["season"], t_ko))
        a = self.metrics(self.team_history(m["away_team_id"], m["season"], t_ko))
        out = {f"h_{k}": v for k, v in h.items()} | {f"a_{k}": v for k, v in a.items()}
        for x in DIFF_METRICS:
            out[f"diff_{x}"] = None if h[x] is None or a[x] is None else h[x] - a[x]
        out["is_modeling_eligible"] = min(h["n_prev_season"], a["n_prev_season"]) >= settings.ELIGIBILITY_THRESHOLD
        return out


def v15_selection(canonical_rows: list[dict[str, str]], feature_rows: list[dict[str, str]]):
    """Conjunto obligatorio (a)–(e) de la especificación + muestra aleatoria (semilla 42)."""
    by_team = defaultdict(list)
    for m in canonical_rows:
        for side in ("home", "away"):
            by_team[(m["season"], m[f"{side}_team_id"])].append(m)
    for k in by_team:
        by_team[k].sort(key=lambda m: (m["kickoff_datetime"], m["match_id"]))
    feats = {x["match_id"]: x for x in feature_rows}
    can = {m["match_id"]: m for m in canonical_rows}
    subsets: dict[str, set[str]] = {}
    subsets["a_primeros_5_por_equipo_temporada"] = {m["match_id"] for v in by_team.values() for m in v[:5]}
    b = set()
    for mid, x in feats.items():
        if x["h_n_prev_season"] and x["a_n_prev_season"] and \
                abs(int(x["h_n_prev_season"]) - int(x["a_n_prev_season"])) >= 2 and mid in can:
            b.add(mid)
            m = can[mid]
            for side in ("home", "away"):
                seq = by_team[(m["season"], m[f"{side}_team_id"])]
                i = next(j for j, y in enumerate(seq) if y["match_id"] == mid)
                b |= {y["match_id"] for y in seq[max(0, i - 2):i + 3]}
    subsets["b_aplazamientos_y_vecinos"] = b
    ko_count = Counter((m["season"], m["kickoff_datetime"]) for m in canonical_rows)
    subsets["c_kickoff_simultaneo"] = {m["match_id"] for m in canonical_rows
                                       if ko_count[(m["season"], m["kickoff_datetime"])] > 1}
    subsets["d_anomalias_conocidas"] = {m["match_id"] for m in canonical_rows if m["dq_flags"] or
                                        (m["source_file"], m["source_row"]) == ("PL_2023-2024_raw.csv", "357")}
    subsets["e_inicio_y_final_de_temporada"] = {m["match_id"] for m in canonical_rows
                                                if int(m["match_seq_season"]) <= 10 or int(m["match_seq_season"]) >= 371}
    mandatory = set().union(*subsets.values())
    remaining = sorted(set(can) - mandatory)
    k = min(settings.LEAKAGE_RANDOM_SAMPLE, len(remaining))
    subsets["random_semilla_42"] = set(random.Random(settings.LEAKAGE_SEED).sample(remaining, k))
    return subsets, mandatory | subsets["random_semilla_42"]


def check_v15(canonical_rows: list[dict[str, str]], feature_rows: list[dict[str, str]]) -> CheckResult:
    r = CheckResult("V15", "Oráculo independiente (filtrado explícito kickoff < t) sobre conjunto obligatorio + muestra")
    if not feature_rows or not schema_guard(r, feature_rows[0].keys()):
        return r
    subsets, selected = v15_selection(canonical_rows, feature_rows)
    oracle = Oracle(canonical_rows)
    can = {m["match_id"]: m for m in canonical_rows}
    feats = {x["match_id"]: x for x in feature_rows}
    tol = settings.ORACLE_TOLERANCE
    compared = 0
    for mid in sorted(selected):
        x = feats.get(mid)
        if x is None:
            r.fail(f"{mid}: no existe en FEATURES")
            continue
        exp = oracle.features_for(can[mid])
        for c, e in exp.items():
            compared += 1
            got = x[c]
            if c == "is_modeling_eligible":
                ok = got == ("true" if e else "false")
            elif c.endswith("n_prev_season"):
                ok = got == str(e)
            else:
                g = fnum(got) if got != "" else None
                ok = (e is None and g is None) or (e is not None and g is not None and abs(g - e) <= tol)
            if not ok:
                r.fail(f"{mid} {c}: FEATURES={got!r} oráculo={e!r}")
    assert set(exp) | {"match_id", "season", "kickoff_datetime", "result", "goal_difference",
                       "feature_version"} == set(FEATURES_COLUMNS)
    for name, s in subsets.items():
        r.info.append(f"{name}: {len(s)} partidos")
    r.info.append(f"Conjunto obligatorio (unión a–e): {len(set().union(*(v for k, v in subsets.items() if k != 'random_semilla_42')))}; "
                  f"total distinto evaluado: {len(selected)}; valores comparados: {compared}; tolerancia {tol}")
    return r
