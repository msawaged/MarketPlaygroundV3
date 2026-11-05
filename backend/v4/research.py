"""
Ranker research: which way of choosing the #1 pick for a belief actually works on calls it has never seen?

Walk-forward by market date (the as-of date of each belief), with a 90-day embargo between training and test so no
training outcome overlaps a test period. For each candidate ranker we report, on the test calls only:
  - beat:  how often its #1 pick beat the S&P 500 (in the belief's direction) 90 days later
  - avg:   average excess return of its #1 pick
  - lift:  #1 pick vs the average idea for the same belief (the part that is skill, not the belief being right)
Results go to kv_cache["research:ranker"]; the brain uses none of this automatically.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import numpy as np

from . import db

DAYS = 90
FEATS = ("mom20", "mom60", "mom250", "rs60", "dist_high", "vol20", "vol60", "log_price", "is_etf", "same_dir",
         "claude_rank_frac", "log_horizon", "conviction",
         # volume profile: where the price sits versus where the stock actually traded (see market.volume_profile)
         "vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value", "rvol",
         # 12-1 momentum: past year skipping the latest month (Jegadeesh & Titman 1993)
         "mom_12_1",
         # frog in the pan (Da, Gurun & Warachka 2014): was the 12-1 move steady (-1) or a few jumps (+1)? not directional
         "fip_id",
         # residual momentum (Blitz, Huij & Martens 2011): 12-1 return SPY-beta can't explain, per unit of residual risk
         "resid_mom",
         # market beta vs SPY over the past year (as of the pick's date); betting against beta (Frazzini & Pedersen 2014)
         "beta",
         # MuLine (MuLabs' trend line): which way it points, how far price is from it, how long since it turned, how choppy
         "mu_dist", "mu_slope", "mu_up", "mu_age", "mu_flips")
# beta is directional: in a bearish call the low-alpha side is the high-beta stock (short it), so -z_beta reads
# "low beta for longs, high beta for shorts", the betting-against-beta trade in either direction
DIRECTIONAL = {"mom20", "mom60", "mom250", "rs60", "dist_high", "mom_12_1", "resid_mom", "beta",
               "vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value",
               "mu_dist", "mu_slope", "mu_up"}
VP_KEYS = ("vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value", "rvol")
# market regime (same for every idea of a belief, so it only matters through interactions with the styles)
REG_KEYS = ("reg_trend", "reg_crisis", "reg_calm")
INTERACTIONS = (("mom60", "reg_trend"), ("mom250", "reg_trend"), ("vol60", "reg_crisis"), ("dist_high", "reg_crisis"),
                ("mom60", "reg_calm"), ("vp_above_value", "reg_trend"))
XKEYS = tuple(f"zx_{a}_{b}" for a, b in INTERACTIONS)
KEY = "research:ranker"
NEUTRAL = {"rvol": 1.0, "beta": 1.0}  # value for a feature a pick never stored (anything else: 0)


def _with_derived(num: dict) -> dict:
    """Fill features that can be computed exactly from what each pick already stored (as of its own date, so no
    look-ahead): mom_12_1 = (1 + mom250) / (1 + mom20) - 1 for picks made before it was saved directly."""
    if "mom_12_1" not in num and num.get("mom250") not in (None, 0, 0.0):
        m20 = float(num.get("mom20", 0.0) or 0.0)
        if 1.0 + m20 > 1e-6:
            num = {**num, "mom_12_1": (1.0 + float(num["mom250"])) / (1.0 + m20) - 1.0}
    return num


def enrich(limit: int = 300) -> dict:
    """Add newer features (volume profile, regime, trend line) to older graded picks that were made before they
    existed, computed with data up to each pick's own date only. Runs in batches from the hourly job."""
    from . import market
    # filter in SQL so the database only sends the few rows still missing features (not every graded pick)
    rows = db.query(
        """SELECT p.id, p.ticker, p.features, b.as_of_date FROM picks p JOIN beliefs b ON b.id = p.belief_id
           WHERE EXISTS (SELECT 1 FROM outcomes o WHERE o.pick_id = p.id AND o.checkpoint_days = ?)
             AND (p.features NOT LIKE '%reg_trend%' OR p.features NOT LIKE '%vp_poc_dist%'
                  OR p.features NOT LIKE '%mu_dist%' OR p.features NOT LIKE '%fip_id%'
                  OR p.features NOT LIKE '%resid_mom%' OR p.features NOT LIKE '%"beta"%')
           LIMIT ?""", (DAYS, max(1, limit) * 2))
    def _need(r):
        num = (db.loads(r["features"], {}) or {}).get("num") or {}
        return "vp_poc_dist" not in num or "reg_trend" not in num or "mu_dist" not in num or "fip_id" not in num \
            or "resid_mom" not in num or "beta" not in num
    missing = [r for r in rows if _need(r)]
    todo = missing[:limit]
    done = 0
    for r in todo:
        f = db.loads(r["features"], {}) or {}
        try:
            d0 = date.fromisoformat(str(r["as_of_date"])[:10])
            market.daily_closes(r["ticker"])  # a data outage skips the pick (retried next hour), never stores zeros
            have = f.get("num") or {}
            vp = {}
            if "vp_poc_dist" not in have or "reg_trend" not in have or "mu_dist" not in have:
                vp.update({**market.vp_features(r["ticker"], d0), **market.regime_features(d0),
                           **market.trend_features(r["ticker"], d0)})
            if "fip_id" not in have:
                vp.update(market.fip_features(r["ticker"], d0))
            if "resid_mom" not in have or "beta" not in have:
                vp.update(market.resid_features(r["ticker"], d0))
        except Exception:
            continue
        f.setdefault("num", {}).update(vp)
        db.execute("UPDATE picks SET features = ? WHERE id = ?", (db.dumps(f), r["id"]))
        done += 1
    return {"enriched": done, "remaining": max(0, len(missing) - done)}


class FeatRow:
    """One candidate's numbers in a single float array behind a shared name->slot map. Reads like a dict
    (row["z_mom60"]); takes a fraction of the memory of a dict of Python floats, which matters with tens of
    thousands of graded calls on a 512 MB job."""
    __slots__ = ("v",)
    KEYS: tuple = ()
    IDX: dict = {}

    def __init__(self, d: dict):
        self.v = np.fromiter((d.get(k, 0.0) for k in FeatRow.KEYS), dtype=np.float64, count=len(FeatRow.KEYS))

    def __getitem__(self, k: str) -> float:
        return float(self.v[FeatRow.IDX[k]])

    def get(self, k: str, default: float = 0.0) -> float:
        i = FeatRow.IDX.get(k)
        return default if i is None else float(self.v[i])

    def __contains__(self, k: str) -> bool:
        return k in FeatRow.IDX


def _set_keys() -> None:
    keys = tuple(FEATS) + ("bearish",) + tuple(REG_KEYS) + tuple("z_" + k for k in FEATS) + tuple(XKEYS)
    FeatRow.KEYS, FeatRow.IDX = keys, {k: i for i, k in enumerate(keys)}


def directional(direction) -> bool:
    """Ranker v2 compares ideas on directional excess vs the S&P. 'volatile' ideas are graded on |move| - |S&P move|,
    which is positive ~75% of the time for any single stock, so mixing them into the same comparison made 'pick the
    volatile idea' look like skill (on 2026-11-05 data: about 45% of gbm's raw lift and its whole beat-rate edge over
    the app). They are left out of training and evaluation, and the ranker never reorders them."""
    return str(direction).lower() in ("bullish", "bearish")


def load() -> list[dict]:
    """One dict per belief: {date, cands: [{f: {...}, ex, top}]}."""
    rows = db.query(
        """SELECT p.belief_id, p.direction, p.features, p.final_rank, o.dir_excess, o.ret, o.spy_ret, b.as_of_date
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.checkpoint_days = ?""", (DAYS,))
    by: dict[str, dict] = {}
    for r in rows:
        if not directional(r["direction"]):
            continue  # graded on |move| (see grader), not comparable with the others' directional excess
        num = _with_derived((db.loads(r["features"], {}) or {}).get("num", {}))
        sign = -1.0 if str(r["direction"]).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, NEUTRAL.get(k, 0.0)) or 0.0) * (sign if k in DIRECTIONAL else 1.0) for k in FEATS}
        f["bearish"] = 1.0 if sign < 0 else 0.0
        for k in REG_KEYS:
            f[k] = float(num.get(k, 0.0) or 0.0)
        b = by.setdefault(r["belief_id"], {"date": str(r["as_of_date"])[:10], "cands": []})
        ex = float(r["dir_excess"])
        # risk-matched outcome: beat what the S&P would have done at this stock's own beta (as of the pick's date).
        # Without a stored beta (older picks not yet backfilled) it equals the plain outcome.
        beta = num.get("beta")
        exa = ex if beta is None or r["ret"] is None or r["spy_ret"] is None else \
            sign * (float(r["ret"]) - float(beta) * float(r["spy_ret"]))
        b["cands"].append({"f": f, "ex": ex, "exa": exa, "has_beta": beta is not None, "top": r["final_rank"] == 1})
    _set_keys()
    del rows  # the raw rows (full feature JSON) are the biggest thing in memory; drop them before building more
    out = [b for b in by.values() if len(b["cands"]) >= 2]
    for b in out:  # within-belief versions: selection is a choice among this belief's ideas
        for k in FEATS:
            vals = np.array([c["f"][k] for c in b["cands"]])
            mu, sd = vals.mean(), vals.std()
            for c, z in zip(b["cands"], (vals - mu) / (sd if sd > 1e-9 else 1.0)):
                c["f"]["z_" + k] = float(z)
        for c in b["cands"]:
            for a, g in INTERACTIONS:
                c["f"][f"zx_{a}_{g}"] = c["f"]["z_" + a] * c["f"][g]
        mean_ex = float(np.mean([c["ex"] for c in b["cands"]]))
        mean_exa = float(np.mean([c["exa"] for c in b["cands"]]))
        for c in b["cands"]:
            c["rel"] = c["ex"] - mean_ex
            c["rela"] = c["exa"] - mean_exa
            c["f"] = FeatRow(c["f"])  # compact from here on
    out.sort(key=lambda b: b["date"])
    return out


def _metrics(picks: list[tuple]) -> dict:
    """picks: [(ex of chosen, belief mean ex, risk-matched ex of chosen, belief mean risk-matched ex)].
    beat/lift: against the S&P 500. beat_adj/lift_adj: against the S&P scaled to each stock's beta, so leaning on
    riskier stocks in a rising market doesn't count as skill."""
    if not picks:
        return {"n": 0}
    def tstat(x):
        se = x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else 0.0
        return round(float(x.mean() / se), 2) if se > 0 else 0.0
    ex = np.array([p[0] for p in picks]); lift = np.array([p[0] - p[1] for p in picks])
    out = {"n": len(picks), "beat": round(float((ex > 0).mean()), 4), "avg": round(float(ex.mean()), 4),
           "lift": round(float(lift.mean()), 4), "lift_t": tstat(lift)}
    if len(picks[0]) >= 4:
        exa = np.array([p[2] for p in picks]); lifta = np.array([p[2] - p[3] for p in picks])
        out.update({"beat_adj": round(float((exa > 0).mean()), 4), "avg_adj": round(float(exa.mean()), 4),
                    "lift_adj": round(float(lifta.mean()), 4), "lift_adj_t": tstat(lifta)})
    return out


def _choose(b: dict, score: Callable[[dict], float]) -> tuple[float, float, float, float]:
    best = max(b["cands"], key=lambda c: score(c["f"]))
    return _pick(b, best)


def _pick(b: dict, c: dict) -> tuple[float, float, float, float]:
    return (c["ex"], float(np.mean([x["ex"] for x in b["cands"]])),
            c["exa"], float(np.mean([x["exa"] for x in b["cands"]])))


def _fit_ridge(train: list[dict], keys: list[str], alpha: float = 5.0):
    x = np.array([[c["f"][k] for k in keys] for b in train for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in train for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + alpha * np.eye(len(keys)), xs.T @ y)
    return lambda f: float(((np.array([f[k] for k in keys]) - mu) / sd) @ w), dict(zip(keys, np.round(w, 4).tolist()))


def _fit_gbm(train: list[dict], keys: list[str], label: str = "rel"):
    from sklearn.ensemble import HistGradientBoostingRegressor
    x = np.array([[c["f"][k] for k in keys] for b in train for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c[label])) for b in train for c in b["cands"]])
    m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                      l2_regularization=1.0, random_state=7).fit(x, y)
    return lambda f: float(m.predict(np.array([[f[k] for k in keys]]))[0])


def run(folds: int = 5, data: list[dict] | None = None) -> dict:
    data = load() if data is None else data
    dates = sorted({b["date"] for b in data})
    if len(data) < 150:
        return {"error": f"only {len(data)} graded beliefs"}
    fixed = {
        "app (current #1)": None,
        "momentum (z_mom60)": lambda f: f["z_mom60"],
        "rel strength (z_rs60)": lambda f: f["z_rs60"],
        "1y trend (z_mom250)": lambda f: f["z_mom250"],
        # idea log (docs/research_ideas.md), added 2026-11-02: Jegadeesh & Titman 12-1 momentum
        "12-1 momentum (z_mom_12_1)": lambda f: f["z_mom_12_1"],
        # idea log, added 2026-11-03: frog in the pan — 12-1 momentum that arrived steadily, not in jumps
        "smooth 12-1 momentum (frog in the pan)": lambda f: f["z_mom_12_1"] - f["z_fip_id"],
        # idea log, added 2026-11-04: residual momentum — 12-1 move beyond what the stock's SPY beta explains
        "residual 12-1 momentum (z_resid_mom)": lambda f: f["z_resid_mom"],
        # idea log, added 2026-11-05: betting against beta — low-beta stock for a long, high-beta for a short
        "betting against beta (-z_beta)": lambda f: -f["z_beta"],
        "near highs (z_dist_high)": lambda f: f["z_dist_high"],
        "high vol (z_vol60)": lambda f: f["z_vol60"],
        "low vol (-z_vol60)": lambda f: -f["z_vol60"],
        "mom+rs blend": lambda f: f["z_mom60"] + f["z_rs60"] + 0.5 * f["z_mom20"],
        "accepted above value (vp)": lambda f: f["z_vp_above_value"] + 0.5 * f["z_vp_vah_dist"],
        "near most-traded price (vp)": lambda f: -abs(f["z_vp_poc_dist"]),
        "heavy recent volume (rvol)": lambda f: f["z_rvol"],
        "MuLine agrees with the call": lambda f: f["z_mu_up"] + 0.5 * f["z_mu_slope"],
        "fresh MuLine trend, not choppy": lambda f: f["z_mu_up"] * (1 - f["mu_age"]) - 0.5 * f["z_mu_flips"],
        "regime-aware styles": lambda f: f["z_mom60"] * (f["reg_trend"] + 0.5 * f["reg_calm"]) - f["z_vol60"] * f["reg_crisis"]
                                         + 0.5 * f["z_mom250"] * f["reg_trend"],
    }
    zkeys = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"] + list(XKEYS)
    res = {k: [] for k in list(fixed) + ["ridge (learned)", "gbm (learned)", "gbm (risk-adjusted)"]}
    # test blocks: the last 60% of dates split into `folds`; train on everything 90+ days before each block
    start = int(len(dates) * 0.4)
    blocks = np.array_split(np.array(dates[start:]), folds)
    weights = None
    for blk in blocks:
        lo, hi = blk[0], blk[-1]
        cutoff = (date.fromisoformat(lo) - timedelta(days=DAYS)).isoformat()
        train = [b for b in data if b["date"] < cutoff]
        test = [b for b in data if lo <= b["date"] <= hi]
        if len(train) < 80 or not test:
            continue
        for name, fn in fixed.items():
            if fn is None:
                res[name] += [_pick(b, next((c for c in b["cands"] if c["top"]), b["cands"][0])) for b in test]
            else:
                res[name] += [_choose(b, fn) for b in test]
        ridge, weights = _fit_ridge(train, zkeys)
        res["ridge (learned)"] += [_choose(b, ridge) for b in test]
        try:
            gbm = _fit_gbm(train, zkeys)
            res["gbm (learned)"] += [_choose(b, gbm) for b in test]
            gbma = _fit_gbm(train, zkeys, label="rela")  # learns from risk-matched outcomes, not raw ones
            res["gbm (risk-adjusted)"] += [_choose(b, gbma) for b in test]
        except Exception:
            pass
    out = {"at": datetime.now(timezone.utc).isoformat(), "beliefs": len(data), "days": DAYS,
           "test_from": dates[start], "results": {k: _metrics(v) for k, v in res.items()},
           "ridge_weights_last": weights,
           "beta_coverage": round(float(np.mean([c["has_beta"] for b in data for c in b["cands"]])), 3),
           "random_beat": round(float(np.mean([np.mean([c["ex"] > 0 for c in b["cands"]]) for b in data[start:]])), 4)}
    db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (KEY, json.dumps(out), out["at"]))
    return out


def run_background() -> None:
    """Run once a few minutes after the web service starts (cheap: a few thousand rows, no Claude)."""
    import threading
    import time

    def go():
        time.sleep(150)
        try:
            fit_production(run())
        except Exception as e:
            db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
            db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                       (KEY, json.dumps({"error": f"{type(e).__name__}: {e}"}), datetime.now(timezone.utc).isoformat()))
        try:  # the MuLine vs ALMA vs 20-day average race on real histories, refreshed at most once a day
            from . import trendlab
            last = trendlab.latest()
            if not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last["at"])).total_seconds() > 86400:
                trendlab.run_and_store()
        except Exception:
            pass

    threading.Thread(target=go, name="research", daemon=True).start()


# ---------------------------------------------------------------------------------------------------------------
# Production ranker ("ranker v2"): the ridge model above, refit on every graded call, used to help choose the #1 pick
# ONLY while its walk-forward test (calls it never saw, 90-day embargo) shows a real edge over the app's old ranking.

RANKER_KEY = "ranker:v2"
ZKEYS = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"] + list(XKEYS)
MIN_LIFT, MIN_T = 0.005, 1.5
WEIGHT = 0.5


GBM_KEY = "ranker:v2:gbm"


MIN_T_ADJ = 1.0       # once betas are in: the edge must also survive scoring against a risk-matched S&P
RISK_COVERAGE = 0.8   # share of graded picks that need a stored beta before that extra check applies


def _passes(m: dict, app: dict, risk: bool = False) -> bool:
    ok = m.get("lift", 0) >= MIN_LIFT and m.get("lift_t", 0) >= MIN_T and m.get("beat", 0) >= app.get("beat", 1)
    if risk:  # stricter, never looser: leaning on riskier stocks in a rising market isn't an edge
        ok = ok and m.get("lift_adj", 0) > 0 and m.get("lift_adj_t", 0) >= MIN_T_ADJ
    return bool(ok)


def fit_production(results: dict | None = None) -> dict:
    """Refit the production ranker on every graded call. Two candidates, both judged on the walk-forward test (calls
    they never saw): a ridge model and a gradient-boosted tree model. The one with the bigger out-of-sample edge goes
    live, but only if it clears the gate; otherwise nothing changes the ranking."""
    data = load()
    if len(data) < 150:
        return {"active": False, "reason": "not enough graded calls"}
    full = results or run(data=data)  # reuse the same data: loading it twice ran the nightly job out of memory
    res = full["results"]
    risk = float(full.get("beta_coverage", 0) or 0) >= RISK_COVERAGE
    app = res.get("app (current #1)", {})
    cands = {"ridge": (res.get("ridge (learned)", {}), "rel"), "gbm": (res.get("gbm (learned)", {}), "rel"),
             "gbm_adj": (res.get("gbm (risk-adjusted)", {}), "rela")}
    x = np.array([[c["f"][k] for k in ZKEYS] for b in data for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in data for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + 5.0 * np.eye(len(ZKEYS)), xs.T @ y)
    # the candidate with the biggest out-of-sample edge (risk-matched once betas are in) among those clearing the gate
    edge = "lift_adj" if risk else "lift"
    passing = [k for k, (m, _) in cands.items() if _passes(m, app, risk)]
    best = max(passing, key=lambda k: cands[k][0].get(edge, 0)) if passing else "ridge"
    kind, (oos, label) = ("ridge" if best == "ridge" else "gbm"), cands[best]
    if kind == "gbm":
        try:
            import base64
            import pickle
            from sklearn.ensemble import HistGradientBoostingRegressor
            yy = np.array([max(-0.5, min(0.5, c[label])) for b in data for c in b["cands"]])
            m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                              l2_regularization=1.0, random_state=7).fit(x, yy)
            blob = base64.b64encode(pickle.dumps(m)).decode()
            db.execute("DELETE FROM kv_cache WHERE k = ?", (GBM_KEY,))
            db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (GBM_KEY, blob, datetime.now(timezone.utc).isoformat()))
        except Exception:
            best, kind, (oos, label) = "ridge", "ridge", cands["ridge"]
    active = _passes(oos, app, risk)
    out = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "model": best, "keys": ZKEYS, "mu": mu.tolist(),
           "sd": sd.tolist(), "w": w.tolist(), "oos": oos, "old": app, "active": active, "trained_on": len(data),
           "risk_check": risk, "beta_coverage": full.get("beta_coverage"),
           "candidates": {k: m for k, (m, _) in cands.items()}}
    db.execute("DELETE FROM kv_cache WHERE k = ?", (RANKER_KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (RANKER_KEY, json.dumps(out), out["at"]))
    _cache["v"], _cache["at"] = out, datetime.now(timezone.utc).timestamp()
    _gbm["at"] = None
    return out


_gbm = {"at": None, "m": None}


def _gbm_model(at: str):
    if _gbm["at"] != at:
        import base64
        import pickle
        row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (GBM_KEY,))
        _gbm["m"] = pickle.loads(base64.b64decode(row["v"])) if row else None
        _gbm["at"] = at
    return _gbm["m"]


_cache = {"v": None, "at": 0.0}


def ranker() -> dict | None:
    import time
    if _cache["v"] is None or time.time() - _cache["at"] > 600:
        row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (RANKER_KEY,))
        _cache["v"], _cache["at"] = (db.loads(row["v"], None) if row else None), time.time()
    return _cache["v"]


def score_candidates(nums: list[dict], directions: list[str]) -> list[float] | None:
    """Ranker v2 scores for one belief's candidates (None when the ranker isn't active)."""
    r = ranker()
    if not r or not r.get("active") or len(nums) < 2:
        return None
    keep = [i for i, d in enumerate(directions) if directional(d)]
    if len(keep) < 2:
        return None
    if len(keep) < len(nums):  # score the directional ideas among themselves; others get their average (no reorder)
        sub = score_candidates([nums[i] for i in keep], [directions[i] for i in keep])
        if sub is None:
            return None
        out = [float(np.mean(sub))] * len(nums)
        for i, v in zip(keep, sub):
            out[i] = v
        return out
    rows = []
    for num, d in zip(nums, directions):
        num = _with_derived(num or {})
        sign = -1.0 if str(d).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, 1.0 if k == "beta" else 0.0) or 0.0) * (sign if k in DIRECTIONAL else 1.0)
             for k in FEATS}
        f["bearish"] = 1.0 if sign < 0 else 0.0
        for k in REG_KEYS:
            f[k] = float(num.get(k, 0.0) or 0.0)
        rows.append(f)
    for k in FEATS:
        vals = np.array([f[k] for f in rows]); m, s_ = vals.mean(), vals.std()
        for f, z in zip(rows, (vals - m) / (s_ if s_ > 1e-9 else 1.0)):
            f["z_" + k] = float(z)
    for f in rows:
        for a, g in INTERACTIONS:
            f[f"zx_{a}_{g}"] = f.get("z_" + a, 0.0) * f.get(g, 0.0)
    if r.get("kind") == "gbm":
        try:
            m = _gbm_model(r["at"])
            if m is not None:
                return [float(v) for v in m.predict(np.array([[f.get(k, 0.0) for k in r["keys"]] for f in rows]))]
        except Exception:
            pass  # fall back to the ridge weights fitted alongside it
    mu, sd, w = np.array(r["mu"]), np.array(r["sd"]), np.array(r["w"])
    return [float(((np.array([f.get(k, 0.0) for k in r["keys"]]) - mu) / sd) @ w) for f in rows]
