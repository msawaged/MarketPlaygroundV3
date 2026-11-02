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
         "mom_12_1")
DIRECTIONAL = {"mom20", "mom60", "mom250", "rs60", "dist_high", "mom_12_1",
               "vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value"}
VP_KEYS = ("vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value", "rvol")
# market regime (same for every idea of a belief, so it only matters through interactions with the styles)
REG_KEYS = ("reg_trend", "reg_crisis", "reg_calm")
INTERACTIONS = (("mom60", "reg_trend"), ("mom250", "reg_trend"), ("vol60", "reg_crisis"), ("dist_high", "reg_crisis"),
                ("mom60", "reg_calm"), ("vp_above_value", "reg_trend"))
XKEYS = tuple(f"zx_{a}_{b}" for a, b in INTERACTIONS)
KEY = "research:ranker"


def _with_derived(num: dict) -> dict:
    """Fill features that can be computed exactly from what each pick already stored (as of its own date, so no
    look-ahead): mom_12_1 = (1 + mom250) / (1 + mom20) - 1 for picks made before it was saved directly."""
    if "mom_12_1" not in num and num.get("mom250") not in (None, 0, 0.0):
        m20 = float(num.get("mom20", 0.0) or 0.0)
        if 1.0 + m20 > 1e-6:
            num = {**num, "mom_12_1": (1.0 + float(num["mom250"])) / (1.0 + m20) - 1.0}
    return num


def enrich(limit: int = 300) -> dict:
    """Add volume-profile features to older graded picks that were made before they existed (computed with data
    up to each pick's own date only). Runs in small batches from the hourly job."""
    from . import market
    # filter in SQL so the database only sends the few rows still missing features (not every graded pick)
    rows = db.query(
        """SELECT p.id, p.ticker, p.features, b.as_of_date FROM picks p JOIN beliefs b ON b.id = p.belief_id
           WHERE EXISTS (SELECT 1 FROM outcomes o WHERE o.pick_id = p.id AND o.checkpoint_days = ?)
             AND (p.features NOT LIKE '%reg_trend%' OR p.features NOT LIKE '%vp_poc_dist%')
           LIMIT ?""", (DAYS, max(1, limit) * 2))
    def _need(r):
        num = (db.loads(r["features"], {}) or {}).get("num") or {}
        return "vp_poc_dist" not in num or "reg_trend" not in num
    missing = [r for r in rows if _need(r)]
    todo = missing[:limit]
    done = 0
    for r in todo:
        f = db.loads(r["features"], {}) or {}
        try:
            d0 = date.fromisoformat(str(r["as_of_date"])[:10])
            vp = {**market.vp_features(r["ticker"], d0), **market.regime_features(d0)}
        except Exception:
            continue
        f.setdefault("num", {}).update(vp)
        db.execute("UPDATE picks SET features = ? WHERE id = ?", (db.dumps(f), r["id"]))
        done += 1
    return {"enriched": done, "remaining": max(0, len(missing) - done)}


def load() -> list[dict]:
    """One dict per belief: {date, cands: [{f: {...}, ex, top}]}."""
    rows = db.query(
        """SELECT p.belief_id, p.direction, p.features, p.final_rank, o.dir_excess, b.as_of_date
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.checkpoint_days = ?""", (DAYS,))
    by: dict[str, dict] = {}
    for r in rows:
        num = _with_derived((db.loads(r["features"], {}) or {}).get("num", {}))
        sign = -1.0 if str(r["direction"]).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, 1.0 if k == "rvol" else 0.0) or 0.0) * (sign if k in DIRECTIONAL else 1.0) for k in FEATS}
        f["bearish"] = 1.0 if sign < 0 else 0.0
        for k in REG_KEYS:
            f[k] = float(num.get(k, 0.0) or 0.0)
        b = by.setdefault(r["belief_id"], {"date": str(r["as_of_date"])[:10], "cands": []})
        b["cands"].append({"f": f, "ex": float(r["dir_excess"]), "top": r["final_rank"] == 1})
    out = [b for b in by.values() if len(b["cands"]) >= 2]
    for b in out:  # within-belief versions: selection is a choice among this belief's ideas
        for k in FEATS:
            vals = np.array([c["f"][k] for c in b["cands"]])
            mu, sd = vals.mean(), vals.std()
            order = vals.argsort().argsort() / max(1, len(vals) - 1)
            for c, z, rk in zip(b["cands"], (vals - mu) / (sd if sd > 1e-9 else 1.0), order):
                c["f"]["z_" + k] = float(z)
                c["f"]["r_" + k] = float(rk)
        for c in b["cands"]:
            for a, g in INTERACTIONS:
                c["f"][f"zx_{a}_{g}"] = c["f"]["z_" + a] * c["f"][g]
        mean_ex = float(np.mean([c["ex"] for c in b["cands"]]))
        for c in b["cands"]:
            c["rel"] = c["ex"] - mean_ex
    out.sort(key=lambda b: b["date"])
    return out


def _metrics(picks: list[tuple[float, float]]) -> dict:
    """picks: [(ex of chosen, belief mean ex)]"""
    if not picks:
        return {"n": 0}
    ex = np.array([p[0] for p in picks]); lift = np.array([p[0] - p[1] for p in picks])
    se = lift.std(ddof=1) / math.sqrt(len(lift)) if len(lift) > 1 else 0.0
    return {"n": len(picks), "beat": round(float((ex > 0).mean()), 4), "avg": round(float(ex.mean()), 4),
            "lift": round(float(lift.mean()), 4), "lift_t": round(float(lift.mean() / se), 2) if se > 0 else 0.0}


def _choose(b: dict, score: Callable[[dict], float]) -> tuple[float, float]:
    best = max(b["cands"], key=lambda c: score(c["f"]))
    return best["ex"], float(np.mean([c["ex"] for c in b["cands"]]))


def _fit_ridge(train: list[dict], keys: list[str], alpha: float = 5.0):
    x = np.array([[c["f"][k] for k in keys] for b in train for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in train for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + alpha * np.eye(len(keys)), xs.T @ y)
    return lambda f: float(((np.array([f[k] for k in keys]) - mu) / sd) @ w), dict(zip(keys, np.round(w, 4).tolist()))


def _fit_gbm(train: list[dict], keys: list[str]):
    from sklearn.ensemble import HistGradientBoostingRegressor
    x = np.array([[c["f"][k] for k in keys] for b in train for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in train for c in b["cands"]])
    m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                      l2_regularization=1.0, random_state=7).fit(x, y)
    return lambda f: float(m.predict(np.array([[f[k] for k in keys]]))[0])


def run(folds: int = 5) -> dict:
    data = load()
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
        "near highs (z_dist_high)": lambda f: f["z_dist_high"],
        "high vol (z_vol60)": lambda f: f["z_vol60"],
        "low vol (-z_vol60)": lambda f: -f["z_vol60"],
        "mom+rs blend": lambda f: f["z_mom60"] + f["z_rs60"] + 0.5 * f["z_mom20"],
        "accepted above value (vp)": lambda f: f["z_vp_above_value"] + 0.5 * f["z_vp_vah_dist"],
        "near most-traded price (vp)": lambda f: -abs(f["z_vp_poc_dist"]),
        "heavy recent volume (rvol)": lambda f: f["z_rvol"],
        "regime-aware styles": lambda f: f["z_mom60"] * (f["reg_trend"] + 0.5 * f["reg_calm"]) - f["z_vol60"] * f["reg_crisis"]
                                         + 0.5 * f["z_mom250"] * f["reg_trend"],
    }
    zkeys = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"] + list(XKEYS)
    res = {k: [] for k in list(fixed) + ["ridge (learned)", "gbm (learned)"]}
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
                res[name] += [(next((c["ex"] for c in b["cands"] if c["top"]), b["cands"][0]["ex"]),
                               float(np.mean([c["ex"] for c in b["cands"]]))) for b in test]
            else:
                res[name] += [_choose(b, fn) for b in test]
        ridge, weights = _fit_ridge(train, zkeys)
        res["ridge (learned)"] += [_choose(b, ridge) for b in test]
        try:
            gbm = _fit_gbm(train, zkeys)
            res["gbm (learned)"] += [_choose(b, gbm) for b in test]
        except Exception:
            pass
    out = {"at": datetime.now(timezone.utc).isoformat(), "beliefs": len(data), "days": DAYS,
           "test_from": dates[start], "results": {k: _metrics(v) for k, v in res.items()},
           "ridge_weights_last": weights,
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

    threading.Thread(target=go, name="research", daemon=True).start()


# ---------------------------------------------------------------------------------------------------------------
# Production ranker ("ranker v2"): the ridge model above, refit on every graded call, used to help choose the #1 pick
# ONLY while its walk-forward test (calls it never saw, 90-day embargo) shows a real edge over the app's old ranking.

RANKER_KEY = "ranker:v2"
ZKEYS = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"] + list(XKEYS)
MIN_LIFT, MIN_T = 0.005, 1.5
WEIGHT = 0.5


GBM_KEY = "ranker:v2:gbm"


def _passes(m: dict, app: dict) -> bool:
    return bool(m.get("lift", 0) >= MIN_LIFT and m.get("lift_t", 0) >= MIN_T and m.get("beat", 0) >= app.get("beat", 1))


def fit_production(results: dict | None = None) -> dict:
    """Refit the production ranker on every graded call. Two candidates, both judged on the walk-forward test (calls
    they never saw): a ridge model and a gradient-boosted tree model. The one with the bigger out-of-sample edge goes
    live, but only if it clears the gate; otherwise nothing changes the ranking."""
    data = load()
    if len(data) < 150:
        return {"active": False, "reason": "not enough graded calls"}
    res = (results or run())["results"]
    app = res.get("app (current #1)", {})
    ridge_oos, gbm_oos = res.get("ridge (learned)", {}), res.get("gbm (learned)", {})
    x = np.array([[c["f"][k] for k in ZKEYS] for b in data for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in data for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + 5.0 * np.eye(len(ZKEYS)), xs.T @ y)
    kind, oos = "ridge", ridge_oos
    if _passes(gbm_oos, app) and gbm_oos.get("lift", 0) > ridge_oos.get("lift", 0):
        try:
            import base64
            import pickle
            from sklearn.ensemble import HistGradientBoostingRegressor
            m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                              l2_regularization=1.0, random_state=7).fit(x, y)
            blob = base64.b64encode(pickle.dumps(m)).decode()
            db.execute("DELETE FROM kv_cache WHERE k = ?", (GBM_KEY,))
            db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (GBM_KEY, blob, datetime.now(timezone.utc).isoformat()))
            kind, oos = "gbm", gbm_oos
        except Exception:
            kind, oos = "ridge", ridge_oos
    active = _passes(oos, app)
    out = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "keys": ZKEYS, "mu": mu.tolist(), "sd": sd.tolist(),
           "w": w.tolist(), "oos": oos, "old": app, "active": active, "trained_on": len(data),
           "candidates": {"ridge": ridge_oos, "gbm": gbm_oos}}
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
    rows = []
    for num, d in zip(nums, directions):
        num = _with_derived(num or {})
        sign = -1.0 if str(d).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, 0.0) or 0.0) * (sign if k in DIRECTIONAL else 1.0) for k in FEATS}
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
