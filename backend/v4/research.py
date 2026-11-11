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
import os
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
         # MAX effect (Bali, Cakici & Whitelaw 2011): mean of the 5 biggest daily returns in the past month ("lottery")
         "max5",
         # intermediate momentum (Novy-Marx 2012): return from ~12 to ~6 months ago, skipping the latest six months
         "mom_12_7",
         # moving average distance (Avramov, Kaplanski & Subrahmanyam 2021): 21-day over 200-day average close, minus 1
         "mad",
         # Amihud (2002) illiquidity: log(1 + 1e8 * mean daily |return| per dollar traded) over the past year
         "amihud",
         # MuLine (MuLabs' trend line): which way it points, how far price is from it, how long since it turned, how choppy
         "mu_dist", "mu_slope", "mu_up", "mu_age", "mu_flips")
# beta is directional: in a bearish call the low-alpha side is the high-beta stock (short it), so -z_beta reads
# "low beta for longs, high beta for shorts", the betting-against-beta trade in either direction. max5 likewise:
# lottery stocks tend to lag, so -z_max5 avoids them for longs and shorts them for bearish calls
DIRECTIONAL = {"mom20", "mom60", "mom250", "rs60", "dist_high", "mom_12_1", "resid_mom", "beta", "max5", "mom_12_7", "mad",
               "amihud", "vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value",
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
                  OR p.features NOT LIKE '%resid_mom%' OR p.features NOT LIKE '%"beta"%'
                  OR p.features NOT LIKE '%"max5"%' OR p.features NOT LIKE '%"mom_12_7"%'
                  OR p.features NOT LIKE '%"mad"%' OR p.features NOT LIKE '%"amihud"%')
           LIMIT ?""", (DAYS, max(1, limit) * 2))
    def _need(r):
        num = (db.loads(r["features"], {}) or {}).get("num") or {}
        return "vp_poc_dist" not in num or "reg_trend" not in num or "mu_dist" not in num or "fip_id" not in num \
            or "resid_mom" not in num or "beta" not in num or "max5" not in num \
            or "mom_12_7" not in num or "mad" not in num or "amihud" not in num
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
            if "max5" not in have:
                vp.update(market.max_features(r["ticker"], d0))
            if "mom_12_7" not in have:
                vp.update(market.echo_features(r["ticker"], d0))
            if "mad" not in have:
                vp.update(market.mad_features(r["ticker"], d0))
            if "amihud" not in have:
                vp.update(market.amihud_features(r["ticker"], d0))
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

    @classmethod
    def from_array(cls, v: np.ndarray) -> "FeatRow":
        r = cls.__new__(cls)
        r.v = np.array(v, dtype=np.float64)
        return r

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


AUG_MAX = int(os.getenv("MP_AUG_MAX", "40000"))  # cap on time-shifted training ideas held in memory (512 MB jobs)


PIT_DAYS = 90  # the checkpoint learning.ticker_stats reads (LABEL_DAYS) and so the one the app's nudge used


def _pit_index(rows: list) -> dict:
    """Per ticker, every graded outcome sorted by the day it was graded, with running sums of what
    learning.ticker_stats averages. Lets us rebuild the app's track-record nudge for a practice call as of the call's
    own date: only outcomes already graded before that date count (no look-ahead)."""
    by: dict[str, list] = {}
    for r in rows:
        if not r.get("ticker") or r.get("eval_date") is None or r.get("dir_excess") is None:
            continue
        d, ex, se = str(r["direction"]).lower(), float(r["dir_excess"]), r.get("sel_edge")
        by.setdefault(r["ticker"], []).append((str(r["eval_date"])[:10], -ex if d == "bearish" else ex,
                                               None if se is None or d != "bullish" else float(se),
                                               None if se is None or d != "bearish" else float(se)))
    out = {}
    for t, v in by.items():
        v.sort(key=lambda x: x[0])
        def cum(j):
            s, c, ss, cc = 0.0, 0, [0.0], [0]
            for x in v:
                if x[j] is not None:
                    s, c = s + x[j], c + 1
                ss.append(s); cc.append(c)
            return ss, cc
        out[t] = ([x[0] for x in v], cum(1), cum(2), cum(3))
    return out


def _pit_score(pit: dict | None, r: dict, top: bool, app: float) -> float:
    """The app's score for this idea as it would have been on the call's own date: Claude's score plus the
    track-record nudge (learning.ticker_adjustment) from outcomes graded before that date, with the user's
    direction leading (as engine.process_belief sorts). Practice calls were scored long after their date, so their
    stored final_score / final_rank used track records that include later outcomes (look-ahead). Calls made in real
    time already were point-in-time: their stored #1 stays the #1. Approximation: the nudge here counts the ticker's
    outcomes under any theme (the live one filters by the belief's themes) and ignores user votes."""
    if pit is None or r.get("source") != "seed_backfill":
        return 100.0 + app if top else app
    from bisect import bisect_left
    from . import learning
    d, core = str(r["direction"]).lower(), str(r.get("bdir") or "").lower()
    lead = 1.0 if core not in ("bullish", "bearish") or d == core else 0.0
    stat = None
    hit = pit.get(r.get("ticker"))
    if hit:
        dates, (rs, rc), (bs, bc), (es, ec) = hit
        i = bisect_left(dates, str(r["as_of_date"])[:10])  # graded strictly before the call's date
        if i:
            stat = {"n": i, "raw_mean": rs[i] / max(rc[i], 1),
                    "n_sel_bull": bc[i], "sel_bull": bs[i] / bc[i] if bc[i] else None,
                    "n_sel_bear": ec[i], "sel_bear": es[i] / ec[i] if ec[i] else None}
    return 10.0 * lead + float(r.get("claude_score") or 0.0) + learning.ticker_adjustment(stat, d)


def load(include_aug: bool = False, days: int = DAYS, live_only: bool = False) -> list[dict]:
    """One dict per belief: {date, cands: [{f: {...}, ex, top}]}. With include_aug, time-shifted practice calls
    (augment.py) are added as beliefs flagged aug=True with src_date; they are only ever used for training.
    live_only: calls made in real time only (no practice/backfill), for the live check."""
    rows = db.query(
        """SELECT p.belief_id, p.direction, p.features, p.final_rank, p.final_score, o.dir_excess, o.ret, o.spy_ret,
                  b.as_of_date, p.ticker, p.claude_score, o.sel_edge, o.eval_date, b.direction AS bdir, b.source
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.checkpoint_days = ?""" + (" AND b.source <> 'seed_backfill'" if live_only else ""), (days,))
    pit = _pit_index(rows) if days == PIT_DAYS and not live_only else None
    if include_aug:
        try:
            from . import augment
            augment.ensure_table()
            for a in db.query(
                    """SELECT basket, shift, src_date, as_of, direction, num, dir_excess, ret, spy_ret FROM aug_ideas
                       WHERE dir_excess IS NOT NULL ORDER BY id LIMIT ?""", (AUG_MAX,)):
                rows.append({"belief_id": f"aug:{a['basket']}:{a['shift']}", "direction": a["direction"],
                             "features": a["num"], "final_rank": None, "dir_excess": a["dir_excess"], "ret": a["ret"],
                             "spy_ret": a["spy_ret"], "as_of_date": a["as_of"], "src_date": a["src_date"],
                             "num_only": True})
        except Exception:
            pass
    by: dict[str, dict] = {}
    for r in rows:
        if not directional(r["direction"]):
            continue  # graded on |move| (see grader), not comparable with the others' directional excess
        raw = db.loads(r["features"], {}) or {}
        num = _with_derived(raw if r.get("num_only") else raw.get("num", {}))
        sign = -1.0 if str(r["direction"]).lower() == "bearish" else 1.0
        # raw values as one small float array (FEATS, bearish, regime); z-scores are added per belief below.
        # A dict of Python floats per idea here was the job's memory peak (~5 KB x every graded idea).
        f = np.fromiter([float(num.get(k, NEUTRAL.get(k, 0.0)) or 0.0) * (sign if k in DIRECTIONAL else 1.0) for k in FEATS]
                        + [1.0 if sign < 0 else 0.0] + [float(num.get(k, 0.0) or 0.0) for k in REG_KEYS],
                        dtype=np.float64, count=len(FEATS) + 1 + len(REG_KEYS))
        b = by.setdefault(r["belief_id"], {"date": str(r["as_of_date"])[:10], "cands": []})
        if r.get("src_date"):
            b["aug"], b["src_date"] = True, str(r["src_date"])[:10]
        ex = float(r["dir_excess"])
        # risk-matched outcome: beat what the S&P would have done at this stock's own beta (as of the pick's date).
        # Without a stored beta (older picks not yet backfilled) it equals the plain outcome.
        beta = num.get("beta")
        exa = ex if beta is None or r["ret"] is None or r["spy_ret"] is None else \
            sign * (float(r["ret"]) - float(beta) * float(r["spy_ret"]))
        top = r["final_rank"] == 0
        app = float(r.get("final_score") or 0.0)
        core = str(r.get("bdir") or "").lower()
        b["cands"].append({"f": f, "ex": ex, "exa": exa, "has_beta": beta is not None, "top": top,  # 0 is the #1 shown
                           "app": app, "pit": _pit_score(pit, r, top, app),
                           # the engine always shows an idea in the belief's own direction first (engine._leads)
                           "lead": core not in ("bullish", "bearish") or str(r["direction"]).lower() == core})
    _set_keys()
    del rows, pit  # the raw rows (full feature JSON) are the biggest thing in memory; drop them before building more
    out = [b for b in by.values() if len(b["cands"]) >= 2]
    nf, idx = len(FEATS), FeatRow.IDX
    xa = [(idx["z_" + a], idx[g]) for a, g in INTERACTIONS]
    for b in out:  # within-belief versions: selection is a choice among this belief's ideas
        raw = np.vstack([c["f"] for c in b["cands"]])                 # ideas x (FEATS, bearish, regime)
        mu, sd = raw[:, :nf].mean(0), raw[:, :nf].std(0)
        z = (raw[:, :nf] - mu) / np.where(sd > 1e-9, sd, 1.0)
        full = np.zeros((len(b["cands"]), len(FeatRow.KEYS)))
        full[:, :raw.shape[1]] = raw
        full[:, raw.shape[1]:raw.shape[1] + nf] = z
        for j, (zi, gi) in enumerate(xa):
            full[:, raw.shape[1] + nf + j] = full[:, zi] * full[:, gi]
        for c, v in zip(b["cands"], full):
            c["f"] = FeatRow.from_array(v)
        mean_ex = float(np.mean([c["ex"] for c in b["cands"]]))
        mean_exa = float(np.mean([c["exa"] for c in b["cands"]]))
        for c in b["cands"]:
            c["rel"] = c["ex"] - mean_ex
            c["rela"] = c["exa"] - mean_exa
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


def mix_scores(app, model, w: float) -> np.ndarray:
    """The app's score with a model mixed in, exactly as the engine does it live: the model's scores are put on the
    app's scale for this belief (z-scored, clipped to +-2, times the app's spread, at least 0.08), then weighted."""
    a, m = np.asarray(app, dtype=float), np.asarray(model, dtype=float)
    if len(a) < 2:
        return a
    z = np.clip((m - m.mean()) / m.std(), -2.0, 2.0) if m.std() > 1e-9 else np.zeros_like(m)
    return (1 - w) * a + w * (a.mean() + z * max(float(a.std()), 0.08))


def _by_confidence(picks: list[tuple], spreads: list[float]) -> dict:
    """Split a candidate's walk-forward picks into thirds by confidence (how far the top idea's score stood out from
    the belief's average) and score each third. cuts are the two spread values between the thirds."""
    a = np.array(spreads)
    q1, q2 = (float(x) for x in np.quantile(a, [1 / 3, 2 / 3]))
    out = {"cuts": [round(q1, 6), round(q2, 6)]}
    for name, lo, hi in (("low", -np.inf, q1), ("mid", q1, q2), ("high", q2, np.inf)):
        out[name] = _metrics([p for p, x in zip(picks, a) if lo < x <= hi])
    return out


def confidence_label(spread: float, cuts) -> str:
    """'high' / 'medium' / 'low' for a live call, using the walk-forward cuts of the model that scored it."""
    if not cuts or len(cuts) != 2:
        return ""
    return "high" if spread > cuts[1] else "medium" if spread > cuts[0] else "low"


def _lead(b: dict) -> list[int]:
    """Which of a belief's ideas can be its #1. The engine sorts ideas in the belief's own direction first
    (engine._leads: on a bullish belief a short on a competitor can only follow the longs), so a ranker can only
    reorder within that group. Tests choose the #1 the same way, or a model gets credit (or blame) for a #1 users
    could never be shown. On 2026-11-11 data, 39% of graded 90-day practice beliefs mixed both directions, and in
    bullish ones the opposite-direction ideas averaged +2.85% vs -0.60% for the longs."""
    idx = [i for i, c in enumerate(b["cands"]) if c.get("lead", True)]
    return idx or list(range(len(b["cands"])))


def _top(b: dict, scores) -> int:
    """Index of the #1 idea for these scores, as the engine would show it (best score within the lead group)."""
    return max(_lead(b), key=lambda i: scores[i])


def _choose(b: dict, score: Callable[[dict], float]) -> tuple[float, float, float, float]:
    return _pick(b, b["cands"][_top(b, [score(c["f"]) for c in b["cands"]])])


def _pick(b: dict, c: dict) -> tuple[float, float, float, float]:
    return (c["ex"], float(np.mean([x["ex"] for x in b["cands"]])),
            c["exa"], float(np.mean([x["exa"] for x in b["cands"]])))


def _fit_ridge(train: list[dict], keys: list[str], alpha: float = 5.0):
    x = _matrix(train, keys)
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in train for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + alpha * np.eye(len(keys)), xs.T @ y)
    return lambda f: float(((np.array([f[k] for k in keys]) - mu) / sd) @ w), dict(zip(keys, np.round(w, 4).tolist()))


def _matrix(beliefs: list[dict], keys: list[str]) -> np.ndarray:
    """Ideas x keys, sliced straight from the compact rows (no per-value Python floats: this was a memory peak)."""
    cols = [FeatRow.IDX[k] for k in keys]
    rows = [c["f"].v[cols] for b in beliefs for c in b["cands"]]
    return np.vstack(rows) if rows else np.zeros((0, len(keys)))


class MLPRanker:
    """A small neural network for ranker v2: same inputs and within-belief label as the trees. Inputs are standardized
    on the training rows, the label is scaled to unit spread, and a few seeds are averaged (one net's result moves with
    its random start). Picklable, so the nightly refit can store it like the tree model."""
    SEEDS = (7, 8, 9, 10, 11)

    def __init__(self, x: np.ndarray, y: np.ndarray, hidden=(32,), alpha: float = 1.0):
        from sklearn.neural_network import MLPRegressor
        self.mu, self.sd = x.mean(0), x.std(0) + 1e-9
        xs = np.clip((x - self.mu) / self.sd, -5, 5)
        self.ys = float(y.std()) + 1e-9
        self.nets = [MLPRegressor(hidden_layer_sizes=hidden, alpha=alpha, learning_rate_init=1e-3, max_iter=200,
                                  early_stopping=True, n_iter_no_change=10, random_state=k).fit(xs, y / self.ys)
                     for k in self.SEEDS]

    def predict(self, x: np.ndarray) -> np.ndarray:
        xs = np.clip((np.asarray(x, dtype=float) - self.mu) / self.sd, -5, 5)
        return np.mean([n.predict(xs) for n in self.nets], axis=0)


def _xy(train: list[dict], keys: list[str], label: str):
    x = _matrix(train, keys)
    y = np.array([max(-0.5, min(0.5, c[label])) for b in train for c in b["cands"]])
    return x, y


def _fit_mlp(train: list[dict], keys: list[str], label: str = "rel"):
    m = MLPRanker(*_xy(train, keys, label))
    return lambda f: float(m.predict(np.array([[f[k] for k in keys]]))[0])


def _fit_gbm(train: list[dict], keys: list[str], label: str = "rel"):
    from sklearn.ensemble import HistGradientBoostingRegressor
    x = _matrix(train, keys)
    y = np.array([max(-0.5, min(0.5, c[label])) for b in train for c in b["cands"]])
    m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                      l2_regularization=1.0, random_state=7).fit(x, y)
    return lambda f: float(m.predict(np.array([[f[k] for k in keys]]))[0])


def run(folds: int = 5, data: list[dict] | None = None) -> dict:
    data = load(include_aug=True) if data is None else data
    aug = [b for b in data if b.get("aug")]
    data = [b for b in data if not b.get("aug")]  # every test, rule and baseline is on real calls only
    dates = sorted({b["date"] for b in data})
    if len(data) < 150:
        return {"error": f"only {len(data)} graded beliefs"}
    fixed = {
        "app (current #1)": None,
        # the same app ordering without look-ahead (see _pit_score); reported, not (yet) the gate's bar
        "app, no look-ahead": None,
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
        # idea log, added 2026-11-06: MAX effect — avoid lottery-like stocks for longs, short them for bearish calls
        "avoid lottery stocks (-z_max5)": lambda f: -f["z_max5"],
        # idea log, added 2026-11-09: Novy-Marx "echo" — momentum from 12 to 7 months ago, not the recent six
        "intermediate momentum (z_mom_12_7)": lambda f: f["z_mom_12_7"],
        # idea log, added 2026-11-10: moving average distance — 21-day average far above the 200-day (below, for shorts)
        "moving average distance (z_mad)": lambda f: f["z_mad"],
        # idea log, added 2026-11-11: Amihud illiquidity premium — the less liquid stock for a long, the most liquid
        # for a short (illiquid stocks have earned more, so the liquid one is the weaker side of a bearish call)
        "illiquidity premium (z_amihud)": lambda f: f["z_amihud"],
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
    res = {k: [] for k in list(fixed) + ["ridge (learned)", "gbm (learned)", "gbm (risk-adjusted)",
                                          "neural net (learned)", "neural net (risk-adjusted)"]
               + (["gbm (+ shifted)", "gbm (risk-adjusted, + shifted)"] if aug else [])}
    # test blocks: the last 60% of dates split into `folds`; train on everything 90+ days before each block
    start = int(len(dates) * 0.4)
    blocks = np.array_split(np.array(dates[start:]), folds)
    weights = None
    spreads: dict[str, list[float]] = {}
    off: dict[str, list[bool]] = {}  # test beliefs where the model's favourite idea was in the other direction

    def learned(name: str, fn, test: list[dict]) -> None:
        """Pick each test belief's top idea and remember how far it stood out (top score minus the belief's mean):
        the model's confidence, used to show how the most confident calls did."""
        for b in test:
            sc = [fn(c["f"]) for c in b["cands"]]
            i = _top(b, sc)  # within the belief's own direction, as the engine shows it
            off.setdefault(name, []).append(int(np.argmax(sc)) != i)
            res[name].append(_pick(b, b["cands"][i]))
            spreads.setdefault(name, []).append(float(sc[i] - np.mean(sc)))
            mx = mix_scores([c.get("app", 0.0) for c in b["cands"]], sc, MIX_WEIGHT)  # what would go live
            j = _top(b, mx)
            res.setdefault(name + MIX, []).append(_pick(b, b["cands"][j]))
            spreads.setdefault(name + MIX, []).append(float(mx[j] - mx.mean()))

    for blk in blocks:
        lo, hi = blk[0], blk[-1]
        cutoff = (date.fromisoformat(lo) - timedelta(days=DAYS)).isoformat()
        train = [b for b in data if b["date"] < cutoff]
        test = [b for b in data if lo <= b["date"] <= hi]
        if len(train) < 80 or not test:
            continue
        for name, fn in fixed.items():
            if fn is None and name == "app, no look-ahead":
                res[name] += [_pick(b, b["cands"][_top(b, [c.get("pit", 0.0) for c in b["cands"]])]) for b in test]
            elif fn is None:
                for b in test:
                    top = next((c for c in b["cands"] if c["top"]), b["cands"][0])
                    res[name].append(_pick(b, top))
                    spreads.setdefault(name, []).append(top.get("app", 0.0) - float(np.mean([c.get("app", 0.0) for c in b["cands"]])))
            else:
                res[name] += [_choose(b, fn) for b in test]
        ridge, weights = _fit_ridge(train, zkeys)
        learned("ridge (learned)", ridge, test)
        try:
            gbm = _fit_gbm(train, zkeys)
            learned("gbm (learned)", gbm, test)
            gbma = _fit_gbm(train, zkeys, label="rela")  # learns from risk-matched outcomes, not raw ones
            learned("gbm (risk-adjusted)", gbma, test)
        except Exception:
            pass
        if aug:  # same trees, trained with time-shifted practice calls added (both dates before the cutoff)
            extra = [b for b in aug if b["date"] < cutoff and b["src_date"] < cutoff]
            try:
                g2 = _fit_gbm(train + extra, zkeys)
                learned("gbm (+ shifted)", g2, test)
                g2a = _fit_gbm(train + extra, zkeys, label="rela")
                learned("gbm (risk-adjusted, + shifted)", g2a, test)
            except Exception:
                pass
        try:  # the neural network competes on exactly the same inputs, labels and walk-forward test
            mlp = _fit_mlp(train, zkeys)
            learned("neural net (learned)", mlp, test)
            mlpa = _fit_mlp(train, zkeys, label="rela")
            learned("neural net (risk-adjusted)", mlpa, test)
        except Exception:
            pass
    out = {"at": datetime.now(timezone.utc).isoformat(), "beliefs": len(data), "days": DAYS, "shifted_beliefs": len(aug),
           "confidence": {k: _by_confidence(res[k], v) for k, v in spreads.items() if len(v) == len(res[k]) >= 90},
           "test_from": dates[start], "results": {k: _metrics(v) for k, v in res.items()},
           "ridge_weights_last": weights, "lead_only": True,
           "mixed_direction": round(float(np.mean([len(_lead(b)) < len(b["cands"]) for b in data[start:]])), 4),
           "off_lead": {k: round(float(np.mean(v)), 4) for k, v in off.items() if v},
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
# Murad's decision (2026-11-09, option B): also test each model the way it would go live, mixed into the app's own
# score at MIX_WEIGHT, against the app alone; a mix must clear the same gate AND hold up on real-time calls.
MIX_WEIGHT = float(os.getenv("MP_RANKER_MIX_WEIGHT", "0.25"))
LIVE_DAYS = int(os.getenv("MP_RANKER_LIVE_DAYS", "30"))
LIVE_MIN_CALLS = int(os.getenv("MP_RANKER_LIVE_MIN", "300"))
MIX = " + app (25%)"


GBM_KEY = "ranker:v2:gbm"


MIN_T_ADJ = 1.0       # once betas are in: the edge must also survive scoring against a risk-matched S&P
RISK_COVERAGE = 0.8   # share of graded picks that need a stored beta before that extra check applies


RAW_BEAT_SLACK = 0.01  # with the risk check on: raw beat rate may trail the old way by at most 1 point


def _passes(m: dict, app: dict, risk: bool = False) -> bool:
    """The edge must be real on calls the model never saw. Before betas are stored: lift >= MIN_LIFT, t >= MIN_T and a
    beat rate at least the old way's. With the risk check on, "beat the S&P" is compared on a risk-matched basis
    (a raw beat rate rewards simply holding riskier stocks in a rising market), the risk-matched edge over the other
    ideas must be positive with t >= MIN_T_ADJ, and the raw beat rate may not trail the old way by more than 1 point.
    (Amended 2026-11-06 after the first risk-matched results; see docs/brain_upgrades.md.)"""
    ok = m.get("lift", 0) >= MIN_LIFT and m.get("lift_t", 0) >= MIN_T
    if not risk:
        return bool(ok and m.get("beat", 0) >= app.get("beat", 1))
    return bool(ok and m.get("lift_adj", 0) > 0 and m.get("lift_adj_t", 0) >= MIN_T_ADJ
                and m.get("beat_adj", 0) >= app.get("beat_adj", 1)
                and m.get("beat", 0) >= app.get("beat", 1) - RAW_BEAT_SLACK)


def live_check(model, mu, sd, w, days: int | None = None, min_calls: int | None = None) -> dict:
    """Would the mix have done at least as well as the app's own #1 on calls made in real time (never practice, so no
    hindsight; all after every training outcome)? Needs min_calls such calls graded at `days`. model None = ridge."""
    days, min_calls = days or LIVE_DAYS, min_calls or LIVE_MIN_CALLS
    try:
        live = load(days=days, live_only=True)
    except Exception as e:
        return {"ok": False, "n": 0, "reason": f"{type(e).__name__}"}
    mix_p, app_p = [], []
    for b in live:
        xb = _matrix([b], ZKEYS)
        sc = model.predict(xb) if model is not None else ((xb - np.asarray(mu)) / np.asarray(sd)) @ np.asarray(w)
        app = [c.get("app", 0.0) for c in b["cands"]]
        mix_p.append(_pick(b, b["cands"][_top(b, mix_scores(app, sc, MIX_WEIGHT))]))
        app_p.append(_pick(b, next((c for c in b["cands"] if c["top"]), b["cands"][_top(b, app)])))
    mm, am = _metrics(mix_p), _metrics(app_p)
    n = mm.get("n", 0)
    ok = n >= min_calls and mm.get("avg", 0) >= am.get("avg", 0)
    return {"ok": bool(ok), "n": n, "days": days, "needed": min_calls, "mix": mm, "app": am}


def fit_production(results: dict | None = None) -> dict:
    """Refit the production ranker on every graded call. Candidates, all judged on the same walk-forward test (calls
    they never saw): ridge, gradient-boosted trees and a small neural network (each trees/net also on risk-matched
    outcomes). The one with the bigger out-of-sample edge goes live, but only if it clears the gate; otherwise nothing
    changes the ranking."""
    data = load(include_aug=True)
    real = [b for b in data if not b.get("aug")]
    if len(real) < 150:
        return {"active": False, "reason": "not enough graded calls"}
    full = results or run(data=data)  # reuse the same data: loading it twice ran the nightly job out of memory
    aug, data = [b for b in data if b.get("aug")], real
    res = full["results"]
    risk = float(full.get("beta_coverage", 0) or 0) >= RISK_COVERAGE
    app = res.get("app (current #1)", {})
    cands = {"ridge": (res.get("ridge (learned)", {}), "rel"), "gbm": (res.get("gbm (learned)", {}), "rel"),
             "gbm_adj": (res.get("gbm (risk-adjusted)", {}), "rela"),
             "mlp": (res.get("neural net (learned)", {}), "rel"), "mlp_adj": (res.get("neural net (risk-adjusted)", {}), "rela")}
    if aug and "gbm (+ shifted)" in res:
        cands.update({"gbm_aug": (res["gbm (+ shifted)"], "rel"), "gbm_adj_aug": (res["gbm (risk-adjusted, + shifted)"], "rela")})
    names = {"ridge": "ridge (learned)", "gbm": "gbm (learned)", "gbm_adj": "gbm (risk-adjusted)",
             "mlp": "neural net (learned)", "mlp_adj": "neural net (risk-adjusted)", "gbm_aug": "gbm (+ shifted)",
             "gbm_adj_aug": "gbm (risk-adjusted, + shifted)"}
    for k in list(cands):  # each model also as it would go live: mixed into the app's score
        if names[k] + MIX in res:
            cands[k + "_mix"] = (res[names[k] + MIX], cands[k][1])
            names[k + "_mix"] = names[k] + MIX
    x = _matrix(data, ZKEYS)
    y = np.array([max(-0.5, min(0.5, c["rel"])) for b in data for c in b["cands"]])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + 5.0 * np.eye(len(ZKEYS)), xs.T @ y)
    edge = "lift_adj" if risk else "lift"
    passing = sorted((k for k, (m, _) in cands.items() if _passes(m, app, risk)),
                     key=lambda k: cands[k][0].get(edge, 0), reverse=True)

    def fit(key: str):
        """The production model for a candidate (trees / net / ridge weights), fit on every graded call."""
        base = key[:-4] if key.endswith("_mix") else key
        kind_ = "ridge" if base == "ridge" else "mlp" if base.startswith("mlp") else "gbm"
        if kind_ == "ridge":
            return kind_, None
        from sklearn.ensemble import HistGradientBoostingRegressor
        fit_on = data + aug if base.endswith("_aug") else data
        xx = x if fit_on is data else _matrix(fit_on, ZKEYS)
        yy = np.array([max(-0.5, min(0.5, c[cands[key][1]])) for b in fit_on for c in b["cands"]])
        return kind_, (MLPRanker(xx, yy) if kind_ == "mlp" else HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40, l2_regularization=1.0,
            random_state=7).fit(xx, yy))

    # the candidate with the biggest out-of-sample edge (risk-matched once betas are in) among those clearing the gate;
    # a mix must also hold up on real-time calls (live_check) before it can go live
    best, kind, model, live = "ridge", "ridge", None, None
    for k in passing:
        try:
            kd, m = fit(k)
        except Exception:
            continue
        if k.endswith("_mix"):
            live = live_check(m, mu, sd, w)
            if not live.get("ok"):
                continue
        best, kind, model = k, kd, m
        break
    oos, label = cands[best]
    if model is not None:
        try:
            import base64
            import pickle
            blob = base64.b64encode(pickle.dumps(model)).decode()
            db.execute("DELETE FROM kv_cache WHERE k = ?", (GBM_KEY,))
            db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (GBM_KEY, blob, datetime.now(timezone.utc).isoformat()))
        except Exception:
            best, kind, (oos, label) = "ridge", "ridge", cands["ridge"]
    active = best in passing and _passes(oos, app, risk)
    if live is None:  # show how the strongest mix is doing on real-time calls, even while it can't go live
        mixes = sorted((k for k in cands if k.endswith("_mix")), key=lambda k: cands[k][0].get(edge, 0), reverse=True)
        if mixes:
            try:
                live = {**live_check(fit(mixes[0])[1], mu, sd, w), "candidate": mixes[0]}
            except Exception:
                live = None
    # confidence cuts for whatever orders the live #1: this model if it is active, otherwise the app's own score
    conf = (full.get("confidence") or {}).get(names.get(best, "") if active else "app (current #1)")
    out = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "model": best, "keys": ZKEYS, "mu": mu.tolist(),
           "sd": sd.tolist(), "w": w.tolist(), "oos": oos, "old": app,
           "old_pit": res.get("app, no look-ahead"), "active": active, "trained_on": len(data), "shifted": len(aug), "confidence": conf,
           "weight": MIX_WEIGHT if best.endswith("_mix") else WEIGHT, "mix": best.endswith("_mix"), "live": live,
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
    if r.get("kind") in ("gbm", "mlp"):  # the stored model (trees or neural net), same inputs either way
        try:
            m = _gbm_model(r["at"])
            if m is not None:
                return [float(v) for v in m.predict(np.array([[f.get(k, 0.0) for k in r["keys"]] for f in rows]))]
        except Exception:
            pass  # fall back to the ridge weights fitted alongside it
    mu, sd, w = np.array(r["mu"]), np.array(r["sd"]), np.array(r["w"])
    return [float(((np.array([f.get(k, 0.0) for k in r["keys"]]) - mu) / sd) @ w) for f in rows]
