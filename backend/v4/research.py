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
         "claude_rank_frac", "log_horizon", "conviction")
DIRECTIONAL = {"mom20", "mom60", "mom250", "rs60", "dist_high"}
KEY = "research:ranker"


def load() -> list[dict]:
    """One dict per belief: {date, cands: [{f: {...}, ex, top}]}."""
    rows = db.query(
        """SELECT p.belief_id, p.direction, p.features, p.final_rank, o.dir_excess, b.as_of_date
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.checkpoint_days = ?""", (DAYS,))
    by: dict[str, dict] = {}
    for r in rows:
        num = (db.loads(r["features"], {}) or {}).get("num", {})
        sign = -1.0 if str(r["direction"]).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, 0.0) or 0.0) * (sign if k in DIRECTIONAL else 1.0) for k in FEATS}
        f["bearish"] = 1.0 if sign < 0 else 0.0
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
        "near highs (z_dist_high)": lambda f: f["z_dist_high"],
        "high vol (z_vol60)": lambda f: f["z_vol60"],
        "low vol (-z_vol60)": lambda f: -f["z_vol60"],
        "mom+rs blend": lambda f: f["z_mom60"] + f["z_rs60"] + 0.5 * f["z_mom20"],
    }
    zkeys = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"]
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
ZKEYS = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"]
MIN_LIFT, MIN_T = 0.005, 1.5
WEIGHT = 0.5


def fit_production(results: dict | None = None) -> dict:
    data = load()
    if len(data) < 150:
        return {"active": False, "reason": "not enough graded calls"}
    res = (results or run())["results"]
    oos, app = res.get("ridge (learned)", {}), res.get("app (current #1)", {})
    x = np.array([[c["f"][k] for k in ZKEYS] for b in data for c in b["cands"]])
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in data for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + 5.0 * np.eye(len(ZKEYS)), xs.T @ y)
    active = bool(oos.get("lift", 0) >= MIN_LIFT and oos.get("lift_t", 0) >= MIN_T and oos.get("beat", 0) >= app.get("beat", 1))
    out = {"at": datetime.now(timezone.utc).isoformat(), "keys": ZKEYS, "mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(),
           "oos": oos, "old": app, "active": active, "trained_on": len(data)}
    db.execute("DELETE FROM kv_cache WHERE k = ?", (RANKER_KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (RANKER_KEY, json.dumps(out), out["at"]))
    _cache["v"], _cache["at"] = out, datetime.now(timezone.utc).timestamp()
    return out


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
        sign = -1.0 if str(d).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, 0.0) or 0.0) * (sign if k in DIRECTIONAL else 1.0) for k in FEATS}
        f["bearish"] = 1.0 if sign < 0 else 0.0
        rows.append(f)
    for k in FEATS:
        vals = np.array([f[k] for f in rows]); m, s_ = vals.mean(), vals.std()
        for f, z in zip(rows, (vals - m) / (s_ if s_ > 1e-9 else 1.0)):
            f["z_" + k] = float(z)
    mu, sd, w = np.array(r["mu"]), np.array(r["sd"]), np.array(r["w"])
    return [float(((np.array([f.get(k, 0.0) for k in r["keys"]]) - mu) / sd) @ w) for f in rows]
