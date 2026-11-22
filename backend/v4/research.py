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
         # continuing overreaction (Byun, Lim & Yun 2016): weighted signed volume over 12 months, -1 (down) to +1 (up)
         "co",
         # return seasonality (Heston & Sadka 2008): average return over the same ~3 months in up to 4 past years
         "seas",
         # relative downside beta (Ang, Chen & Xing 2006): beta on below-average market days minus ordinary beta
         "dbeta",
         # idiosyncratic volatility (Ang, Hodrick, Xing & Zhang 2006): 1-month residual volatility vs SPY, annualized
         "ivol",
         # long-term reversal (De Bondt & Thaler 1985): return from ~3 years to ~1 year ago, skipping the latest year
         "ltr",
         # price delay (Hou & Moskowitz 2005): 1 - R2(same-week SPY) / R2(with 4 lagged weeks), weekly returns over a year
         "delay",
         # realized skewness (Amaya, Christoffersen, Jacobs & Vasquez 2015): skewness of daily log returns, ~3 months
         "rskew",
         # coskewness (Harvey & Siddique 2000): standardized co-movement of the stock's residual with SPY's squared
         # moves, daily returns over ~1 year
         "coskew",
         # variability of trading activity (Chordia, Subrahmanyam & Anshuman 2001): coefficient of variation of daily
         # dollar volume over ~1 year
         "cvvol",
         # timing of the 52-week high (Bhootra & Hur 2013): sessions since the highest close of the past ~year, as a
         # share of the year (0 = today, 1 = a year ago)
         "hi_age",
         # level of trading activity (Brennan, Chordia & Subrahmanyam 1998): log mean daily dollar volume, ~1 year
         "ldvol",
         # volatility of volatility (Baltussen, van Bekkum & van der Grient 2018): coefficient of variation of 12 monthly
         # realized vols over ~1 year (a realized stand-in for the paper's implied-vol measure)
         "vov",
         # MuLine (MuLabs' trend line): which way it points, how far price is from it, how long since it turned, how choppy
         "mu_dist", "mu_slope", "mu_up", "mu_age", "mu_flips")
# beta is directional: in a bearish call the low-alpha side is the high-beta stock (short it), so -z_beta reads
# "low beta for longs, high beta for shorts", the betting-against-beta trade in either direction. max5 likewise:
# lottery stocks tend to lag, so -z_max5 avoids them for longs and shorts them for bearish calls
DIRECTIONAL = {"mom20", "mom60", "mom250", "rs60", "dist_high", "mom_12_1", "resid_mom", "beta", "max5", "mom_12_7", "mad",
               "amihud", "co", "seas", "dbeta", "ivol", "ltr", "delay", "rskew", "coskew", "cvvol", "hi_age", "ldvol", "vov", "vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value",
               "mu_dist", "mu_slope", "mu_up"}
VP_KEYS = ("vp_poc_dist", "vp_vah_dist", "vp_val_dist", "vp_above_value", "vp_below_value", "rvol")
# market regime (same for every idea of a belief, so it only matters through interactions with the styles)
REG_KEYS = ("reg_trend", "reg_crisis", "reg_calm")
INTERACTIONS = (("mom60", "reg_trend"), ("mom250", "reg_trend"), ("vol60", "reg_crisis"), ("dist_high", "reg_crisis"),
                ("mom60", "reg_calm"), ("vp_above_value", "reg_trend"))
XKEYS = tuple(f"zx_{a}_{b}" for a, b in INTERACTIONS)
KEY = "research:ranker"
NEUTRAL = {"rvol": 1.0, "beta": 1.0, "ivol": 0.30, "delay": 0.20, "hi_age": 0.5, "ldvol": 15.0, "vov": 0.35}  # value for a feature a pick never stored (anything else: 0)
# Feature coverage (docs/feature_ideas.md 2026-11-14 extra run): every input a rule can read, with one bit per key
# on each candidate saying whether the pick stored it. A rule scored while one of its inputs is under COVERAGE_OK
# is reported "provisional": part of its score comes from placeholder values, not data. Reporting only.
COV_KEYS = FEATS + REG_KEYS
COV_BIT = {k: 1 << i for i, k in enumerate(COV_KEYS)}
COVERAGE_OK = 0.99


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
                  OR p.features NOT LIKE '%"mad"%' OR p.features NOT LIKE '%"amihud"%'
                  OR p.features NOT LIKE '%"co"%' OR p.features NOT LIKE '%"seas"%'
                  OR p.features NOT LIKE '%"dbeta"%' OR p.features NOT LIKE '%"ivol"%'
                  OR p.features NOT LIKE '%"ltr"%' OR p.features NOT LIKE '%"delay"%'
                  OR p.features NOT LIKE '%"rskew"%' OR p.features NOT LIKE '%"coskew"%'
                  OR p.features NOT LIKE '%"cvvol"%' OR p.features NOT LIKE '%"hi_age"%'
                  OR p.features NOT LIKE '%"ldvol"%' OR p.features NOT LIKE '%"vov"%')
           LIMIT ?""", (DAYS, max(1, limit) * 2))
    def _need(r):
        num = (db.loads(r["features"], {}) or {}).get("num") or {}
        return "vp_poc_dist" not in num or "reg_trend" not in num or "mu_dist" not in num or "fip_id" not in num \
            or "resid_mom" not in num or "beta" not in num or "max5" not in num \
            or "mom_12_7" not in num or "mad" not in num or "amihud" not in num or "co" not in num \
            or "seas" not in num or "dbeta" not in num or "ivol" not in num or "ltr" not in num or "delay" not in num \
            or "rskew" not in num or "coskew" not in num or "cvvol" not in num \
            or "hi_age" not in num or "ldvol" not in num or "vov" not in num
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
            if "co" not in have:
                vp.update(market.co_features(r["ticker"], d0))
            if "seas" not in have:
                vp.update(market.seas_features(r["ticker"], d0))
            if "dbeta" not in have:
                vp.update(market.dbeta_features(r["ticker"], d0))
            if "ivol" not in have:
                vp.update(market.ivol_features(r["ticker"], d0))
            if "ltr" not in have:
                vp.update(market.ltr_features(r["ticker"], d0))
            if "delay" not in have:
                vp.update(market.delay_features(r["ticker"], d0))
            if "rskew" not in have:
                vp.update(market.rskew_features(r["ticker"], d0))
            if "coskew" not in have:
                vp.update(market.coskew_features(r["ticker"], d0))
            if "cvvol" not in have:
                vp.update(market.cvvol_features(r["ticker"], d0))
            if "hi_age" not in have:
                vp.update(market.hi_age_features(r["ticker"], d0))
            if "ldvol" not in have:
                vp.update(market.ldvol_features(r["ticker"], d0))
            if "vov" not in have:
                vp.update(market.vov_features(r["ticker"], d0))
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


def _pit_app(pit: dict | None, r: dict, app: float) -> float:
    """The app's own score for this idea on the call's date, before the engine's direction-first sort: what the
    engine mixes a live ranker into (engine.process_belief: final_score before _leads). Practice calls: Claude's
    score + the track-record nudge from outcomes graded before the call's date (see _pit_score); calls made in real
    time: their stored final_score, which was already point-in-time."""
    if pit is None or r.get("source") != "seed_backfill":
        return app
    from bisect import bisect_left
    from . import learning
    d = str(r["direction"]).lower()
    stat = None
    hit = pit.get(r.get("ticker"))
    if hit:
        dates, (rs, rc), (bs, bc), (es, ec) = hit
        i = bisect_left(dates, str(r["as_of_date"])[:10])  # graded strictly before the call's date
        if i:
            stat = {"n": i, "raw_mean": rs[i] / max(rc[i], 1),
                    "n_sel_bull": bc[i], "sel_bull": bs[i] / bc[i] if bc[i] else None,
                    "n_sel_bear": ec[i], "sel_bear": es[i] / ec[i] if ec[i] else None}
    return float(r.get("claude_score") or 0.0) + learning.ticker_adjustment(stat, d)


def _pit_score(pit: dict | None, r: dict, top: bool, app: float) -> float:
    """The app's score for this idea as it would have been on the call's own date: Claude's score plus the
    track-record nudge (learning.ticker_adjustment) from outcomes graded before that date, with the user's
    direction leading (as engine.process_belief sorts). Practice calls were scored long after their date, so their
    stored final_score / final_rank used track records that include later outcomes (look-ahead). Calls made in real
    time already were point-in-time: their stored #1 stays the #1. Approximation: the nudge here counts the ticker's
    outcomes under any theme (the live one filters by the belief's themes) and ignores user votes."""
    if pit is None or r.get("source") != "seed_backfill":
        return 100.0 + app if top else app
    d, core = str(r["direction"]).lower(), str(r.get("bdir") or "").lower()
    lead = 1.0 if core not in ("bullish", "bearish") or d == core else 0.0
    return 10.0 * lead + _pit_app(pit, r, app)


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
        if not r.get("num_only") and raw.get("rv2") is not None:
            b["rv2"] = True  # ranker v2 was ordering this call when it was made (engine stores rv2 only then)
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
        miss = zero = 0  # bitmasks over COV_KEYS: never stored / stored as exactly 0 (a heuristic: some can be 0)
        for k, bit in COV_BIT.items():
            v = num.get(k)
            if v is None:
                miss |= bit
            elif v == 0:
                zero |= bit
        core = str(r.get("bdir") or "").lower()
        b["cands"].append({"f": f, "ex": ex, "exa": exa, "has_beta": beta is not None, "top": top,  # 0 is the #1 shown
                           "miss": miss, "zero": zero,
                           "app": app, "pit": _pit_score(pit, r, top, app),
                           # the app score a mix is tested with: point-in-time, as a live mix would get it
                           "pit_app": _pit_app(pit, r, app),
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
        # Training label: the idea's outcome minus the average of the ideas it actually competes with. The engine
        # picks the #1 inside the lead group (belief's own direction, _lead), so a long is compared with the other
        # longs, not with a short on a competitor. Against the whole-belief mean, the 2,341 off-direction ideas in
        # mixed beliefs moved every lead label by a belief-level offset (sd 18% for the off group, prod 2026-11-14)
        # and 1,269 lone off-direction ideas taught only "which direction won". A group of one has nothing to be
        # ranked against, so it is left out of training (train=False). Test scoring (_pick) is unchanged.
        groups: dict[bool, list[dict]] = {}
        for c in b["cands"]:
            groups.setdefault(bool(c["lead"]), []).append(c)
        if len(groups) == 1:  # one group (or no lead idea at all: _lead falls back to everyone)
            groups = {True: b["cands"]}
        for g in groups.values():
            mean_ex = float(np.mean([c["ex"] for c in g]))
            mean_exa = float(np.mean([c["exa"] for c in g]))
            for c in g:
                c["rel"] = c["ex"] - mean_ex
                c["rela"] = c["exa"] - mean_exa
                c["train"] = len(g) >= 2
    out.sort(key=lambda b: b["date"])
    return out


def _se_overlap(x: np.ndarray, dates: list[str], window: int = DAYS) -> float:
    """Standard error of x.mean() that counts overlapping windows honestly (Newey & West 1987 / Driscoll & Kraay 1998
    style, Petersen 2009). Each call is graded over `window` calendar days, so calls made on the same day share one
    market path and calls a few days apart share most of it. Residuals are summed per call date, and each pair of dates
    is weighted by how much their windows overlap: 1 - gap/window (Bartlett weights in calendar time; positive
    semi-definite, so never negative). Same-day pairs get weight 1, which nests date-clustered errors."""
    n = len(x)
    if n < 2:
        return 0.0
    u = x - x.mean()
    by: dict[str, float] = {}
    for d, v in zip(dates, u):
        by[d] = by.get(d, 0.0) + float(v)
    keys = sorted(by)
    s = np.array([by[k] for k in keys])
    t = np.array([date.fromisoformat(k).toordinal() for k in keys], dtype=float)
    w = np.clip(1.0 - np.abs(t[:, None] - t[None, :]) / float(window), 0.0, None)
    var = float(s @ w @ s) / (n * n) * n / (n - 1)  # same small-sample factor as the plain ddof=1 se
    return math.sqrt(var) if var > 0 else 0.0


def _metrics(picks: list[tuple], cuts: tuple[float, float] | None = None) -> dict:
    """picks: [(ex of chosen, belief mean ex, risk-matched ex of chosen, belief mean risk-matched ex[, belief date])].
    beat/lift: against the S&P 500. beat_adj/lift_adj: against the S&P scaled to each stock's beta, so leaning on
    riskier stocks in a rising market doesn't count as skill.
    With dates: lift_t_nw / lift_adj_t_nw are the same lifts' t with overlap-honest errors (_se_overlap), `dates` the
    distinct call dates and n_eff about how many independent calls the n is worth. Reporting only: _passes and
    fit_production read the plain t's, exactly as before.
    Outlier check (always): lift_med = median per-call lift; top10_share = share of the summed lift that the 10 best
    calls contribute (None unless the summed lift is positive). With `cuts` and winsorized belief means (6th item):
    lift_w / lift_w_t (/ lift_w_t_nw) = the same lift with every outcome clipped to the cuts. Reporting only.
    Time blocks (with dates, _time_blocks): blocks = per-stretch n / lift / beat, pos_blocks = stretches with lift > 0
    (of n_blocks), last_block_lift, block_spread = best minus worst stretch. Reporting only."""
    if not picks:
        return {"n": 0}
    def tstat(x):
        se = x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else 0.0
        return round(float(x.mean() / se), 2) if se > 0 else 0.0
    dts = [str(p[4])[:10] for p in picks] if len(picks[0]) >= 5 and all(p[4] for p in picks) else None
    def tnw(x):
        se = _se_overlap(x, dts)
        return round(float(x.mean() / se), 2) if se > 0 else 0.0
    ex = np.array([p[0] for p in picks]); lift = np.array([p[0] - p[1] for p in picks])
    out = {"n": len(picks), "beat": round(float((ex > 0).mean()), 4), "avg": round(float(ex.mean()), 4),
           "lift": round(float(lift.mean()), 4), "lift_t": tstat(lift), "lift_med": round(float(np.median(lift)), 4)}
    tot = float(lift.sum())
    out["top10_share"] = round(float(np.sort(lift)[::-1][:10].sum()) / tot, 3) if tot > 0 and len(lift) > 10 else None
    if cuts and len(picks[0]) >= 6 and all(p[5] is not None for p in picks):
        lw = np.clip(ex, cuts[0], cuts[1]) - np.array([p[5] for p in picks], dtype=float)
        out.update({"lift_w": round(float(lw.mean()), 4), "lift_w_t": tstat(lw)})
        if dts:
            out["lift_w_t_nw"] = tnw(lw)
    if dts:
        se_p = lift.std(ddof=1) / math.sqrt(len(lift)) if len(lift) > 1 else 0.0
        se_h = _se_overlap(lift, dts)
        out.update({"lift_t_nw": tnw(lift), "dates": len(set(dts)),
                    "n_eff": int(round(min(len(lift), len(lift) * (se_p / se_h) ** 2))) if se_h > 0 else len(lift)})
        bl = _time_blocks(lift, ex, dts)
        if bl:  # "does it hold every year?" (reporting only)
            ls = [b["lift"] for b in bl]
            out.update({"blocks": bl, "pos_blocks": sum(1 for v in ls if v > 0), "n_blocks": len(bl),
                        "last_block_lift": ls[-1], "block_spread": round(max(ls) - min(ls), 4)})
    if len(picks[0]) >= 4:
        exa = np.array([p[2] for p in picks]); lifta = np.array([p[2] - p[3] for p in picks])
        out.update({"beat_adj": round(float((exa > 0).mean()), 4), "avg_adj": round(float(exa.mean()), 4),
                    "lift_adj": round(float(lifta.mean()), 4), "lift_adj_t": tstat(lifta)})
        if dts:
            out["lift_adj_t_nw"] = tnw(lifta)
    return out


TIME_BLOCKS = 4  # "does it hold every year?": each result is also split into this many chronological stretches
STEADY_MIN = 3  # stretches (of TIME_BLOCKS) a cleared result must be ahead in to count as steady


def _time_blocks(lift: np.ndarray, ex: np.ndarray, dates: list[str], k: int = TIME_BLOCKS) -> list[dict]:
    """Split the calls into k chronological stretches of about equal call count, cut on call dates (all calls made on
    one date stay in one stretch; outcomes never decide a cut). Per stretch: its first and last call date, n, the
    lift and beat rate. McLean & Pontiff (2016): an average over a long window can hide an edge that lived in one
    stretch and is gone. Reporting only."""
    if len(lift) < 2 * k:
        return []
    cnt: dict[str, int] = {}
    for d in dates:
        cnt[d] = cnt.get(d, 0) + 1
    n, seen, blk = len(dates), 0, {}
    for d in sorted(cnt):
        blk[d] = min(k - 1, int((seen + cnt[d] / 2) * k / n))  # a date goes where its middle call falls
        seen += cnt[d]
    idx = np.array([blk[d] for d in dates])
    out = []
    for j in range(k):
        m = idx == j
        if not m.any():
            continue
        ds = sorted({d for d, keep in zip(dates, m) if keep})
        out.append({"from": ds[0], "to": ds[-1], "n": int(m.sum()), "lift": round(float(lift[m].mean()), 4),
                    "beat": round(float((ex[m] > 0).mean()), 4)})
    return out


PBO_BLOCKS = 8  # "would we have picked the winner?": CSCV blocks (C(8,4) = 70 in-sample / out-of-sample splits)
PBO_EXCLUDE = ("app (current #1)",)  # its stored score carries look-ahead; the no-look-ahead app row stands in for it


def _date_blocks(dates: list[str], k: int) -> dict:
    """Date -> block index for k chronological blocks of about equal call count (the _time_blocks rule: a date goes
    where its middle call falls, so a date never splits and outcomes never decide a cut)."""
    cnt: dict[str, int] = {}
    for d in dates:
        cnt[d] = cnt.get(d, 0) + 1
    n, seen, blk = len(dates), 0, {}
    for d in sorted(cnt):
        blk[d] = min(k - 1, int((seen + cnt[d] / 2) * k / n))
        seen += cnt[d]
    return blk


def pbo(res: dict, s: int = PBO_BLOCKS, only: tuple | list | None = None, exclude=PBO_EXCLUDE) -> dict:
    """Probability of backtest overfitting (Bailey, Borwein, Lopez de Prado & Zhu 2017, CSCV). res: {method: picks as
    _pick makes them (lift = p[0] - p[1], call date = p[4])}, all scored on the walk-forward test calls. The test calls
    are cut into s chronological blocks on dates; for each of the C(s, s/2) ways to call half the blocks "in-sample",
    the method with the best pooled lift there is the winner, and we see where it ranks on the other half.
    pbo = share of splits where the winner ranks at or below the out-of-sample median (logit <= 0, as in the paper);
    oos_lift_med = the winner's median out-of-sample lift; p_loss = share of splits where it trails the belief average
    out of sample; slope = OLS slope of the winner's out-of-sample on in-sample lift; winners = method -> splits won.
    Only methods with calls in every block take part (n_methods). Reporting only: _passes / fit_production and the
    luck bar never read this."""
    from itertools import combinations
    names = [k for k, v in (res or {}).items() if v and k not in exclude and (only is None or k in only)]
    rows = {k: [(float(p[0] - p[1]), str(p[4])[:10]) for p in res[k] if len(p) >= 5 and p[4]] for k in names}
    pool = sorted({d for r in rows.values() for _, d in r})
    if len(names) < 2 or len(pool) < 2 * s:
        return {}
    ref = max(rows, key=lambda k: len(rows[k]))  # the fullest method sets the blocks' call counts
    blk = _date_blocks([d for _, d in rows[ref]], s)
    # dates some method has but the reference lacks go to the block of the nearest earlier reference date
    ref_dates = sorted(blk)
    for d in pool:
        if d not in blk:
            i = max(0, int(np.searchsorted(ref_dates, d, side="right")) - 1)
            blk[d] = blk[ref_dates[i]]
    sums, cnts, keep = [], [], []
    for k in names:
        sm, ct = np.zeros(s), np.zeros(s)
        for x, d in rows[k]:
            sm[blk[d]] += x
            ct[blk[d]] += 1
        if (ct > 0).all():
            keep.append(k); sums.append(sm); cnts.append(ct)
    if len(keep) < 2:
        return {}
    S, C = np.array(sums), np.array(cnts)
    half = s // 2
    lam, oos_w, is_w, wins = [], [], [], {}
    for ins in combinations(range(s), half):
        m = np.zeros(s, dtype=bool); m[list(ins)] = True
        is_l = S[:, m].sum(1) / C[:, m].sum(1)
        oos_l = S[:, ~m].sum(1) / C[:, ~m].sum(1)
        w = int(np.argmax(is_l))
        below = float((oos_l < oos_l[w]).sum()); ties = float((oos_l == oos_l[w]).sum()) - 1
        omega = (below + 0.5 * ties + 1) / (len(keep) + 1)  # relative rank out of sample, in (0, 1)
        lam.append(math.log(omega / (1 - omega)))
        oos_w.append(float(oos_l[w])); is_w.append(float(is_l[w]))
        wins[keep[w]] = wins.get(keep[w], 0) + 1
    lam_a, oos_a, is_a = np.array(lam), np.array(oos_w), np.array(is_w)
    slope = None
    if is_a.std() > 0:
        slope = round(float(np.polyfit(is_a, oos_a, 1)[0]), 3)
    return {"pbo": round(float((lam_a <= 0).mean()), 3), "n_splits": len(lam), "n_methods": len(keep),
            "n_blocks": s, "oos_lift_med": round(float(np.median(oos_a)), 4),
            "p_loss": round(float((oos_a < 0).mean()), 3), "slope": slope,
            "winners": dict(sorted(wins.items(), key=lambda kv: -kv[1]))}


LEARNED = ("ridge (learned)", "gbm (learned)", "gbm (risk-adjusted)", "neural net (learned)",
           "neural net (risk-adjusted)", "gbm (+ shifted)", "gbm (risk-adjusted, + shifted)")


VS_APP_BASE = "app, no look-ahead"  # the app's #1 the head-to-head compares against (no look-ahead, see _pit_score)
VS_APP_MIN = 100  # disagreements needed before the Brain page quotes a head-to-head


def _vs_app(chosen: list[tuple], base: dict) -> dict:
    """"Is it new?" (Feng, Giglio & Xiu 2020: judge a new signal by what it adds to what's already in hand). chosen:
    [(belief key, index of this method's #1, belief)]; base: {belief key: index of the app's #1 without look-ahead}.
    same_as_app = share of calls where the two #1s are the same idea; on the n_diff calls where they differ,
    lift_diff = this #1's excess minus the app's #1's excess (same belief, so the belief's average cancels), with its
    plain t and overlap-honest t_nw. A rule that mostly agrees and has lift_diff near zero is the app restated.
    Reporting only: _passes / fit_production and the luck bar never read these."""
    rows = [(i, b, base[k]) for k, i, b in chosen if k in base]
    if not rows:
        return {}
    diff = [(float(b["cands"][i]["ex"] - b["cands"][j]["ex"]), str(b.get("date") or "")[:10])
            for i, b, j in rows if i != j]
    out = {"same_as_app": round(1 - len(diff) / len(rows), 4), "n_diff": len(diff)}
    if len(diff) >= 2:
        x = np.array([d for d, _ in diff])
        se = x.std(ddof=1) / math.sqrt(len(x))
        out.update({"lift_diff": round(float(x.mean()), 4), "lift_diff_t": round(float(x.mean() / se), 2) if se > 0 else 0.0})
        if all(d for _, d in diff):
            se_h = _se_overlap(x, [d for _, d in diff])
            out["lift_diff_t_nw"] = round(float(x.mean() / se_h), 2) if se_h > 0 else 0.0
    return out


def is_new(results: dict, k: int = 3) -> list[dict]:
    """The k strongest methods other than the app itself (by overlap-honest t, else plain t), each with how often it
    picks the app's #1 and how it does where it doesn't. Reporting only."""
    rows = [(n, m) for n, m in (results or {}).items()
            if n not in ("app (current #1)", VS_APP_BASE) and (m or {}).get("n") and m.get("same_as_app") is not None]
    t = lambda m: float(m.get("lift_t_nw") if m.get("lift_t_nw") is not None else m.get("lift_t") or 0)
    rows.sort(key=lambda r: -t(r[1]))
    keys = ("lift", "lift_t", "lift_t_nw", "same_as_app", "n_diff", "lift_diff", "lift_diff_t", "lift_diff_t_nw",
            "pos_blocks", "n_blocks", "last_block_lift")
    return [{"name": n, **{q: m.get(q) for q in keys}} for n, m in rows[:k]]


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


def confidence_backed(conf) -> bool:
    """Whether the confidence badge may be shown to users: only while the test it rests on backs its promise (the most
    confident third of #1 picks beat the belief's average idea by more than the least confident third). On 2026-11-15
    the no-look-ahead thirds read high +0.2 / mid +0.9 / low +0.5 pts, so a green "High confidence" told users the
    opposite of the evidence. The label is still recorded on the pick (features.rv2_conf) for the live forward test."""
    try:
        hi, lo = (conf or {}).get("high") or {}, (conf or {}).get("low") or {}
        return bool(hi.get("n")) and bool(lo.get("n")) and float(hi.get("lift") or 0) > float(lo.get("lift") or 0)
    except (TypeError, ValueError, AttributeError):
        return False


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


def _choose(b: dict, score: Callable[[dict], float]) -> tuple:
    return _pick(b, b["cands"][_top(b, [score(c["f"]) for c in b["cands"]])])


def _pick(b: dict, c: dict) -> tuple:
    # 6th: the belief's mean excess with every idea's outcome winsorized (run() sets b["wmean"]); None outside run()
    return (c["ex"], float(np.mean([x["ex"] for x in b["cands"]])),
            c["exa"], float(np.mean([x["exa"] for x in b["cands"]])), b.get("date"), b.get("wmean"))


WINSOR_Q = 0.01  # the outlier check clips outcomes at the 1st / 99th percentile of the run's test-period ideas


def winsor_cuts(beliefs: list[dict], q: float = WINSOR_Q) -> tuple[float, float] | None:
    """Cut points for the outlier check (Adams, Hayunga, Mansi, Reeb & Verardi 2019): the q / 1-q quantiles of every
    candidate's 90-day excess in these beliefs, computed per run from outcomes already graded, so every rule is clipped
    at the same place and no rule's choice is looked ahead at. Reporting only."""
    xs = [float(c["ex"]) for b in beliefs for c in b["cands"]]
    if len(xs) < 50:
        return None
    lo, hi = (float(v) for v in np.quantile(np.array(xs), [q, 1 - q]))
    return (lo, hi) if hi > lo else None


def _fit_ridge(train: list[dict], keys: list[str], alpha: float = 5.0):
    x, y = _xy(train, keys, "rel")
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
    """Training inputs and labels: only ideas that have something to be ranked against inside their group (see load)."""
    mask = np.array([c.get("train", True) for b in train for c in b["cands"]], dtype=bool)
    x = _matrix(train, keys)[mask] if len(mask) else _matrix(train, keys)
    y = np.array([max(-0.5, min(0.5, c[label])) for b in train for c in b["cands"] if c.get("train", True)])
    return x, y


def _fit_mlp(train: list[dict], keys: list[str], label: str = "rel"):
    m = MLPRanker(*_xy(train, keys, label))
    return lambda f: float(m.predict(np.array([[f[k] for k in keys]]))[0])


def _fit_gbm(train: list[dict], keys: list[str], label: str = "rel"):
    from sklearn.ensemble import HistGradientBoostingRegressor
    x, y = _xy(train, keys, label)
    m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                      l2_regularization=1.0, random_state=7).fit(x, y)
    return lambda f: float(m.predict(np.array([[f[k] for k in keys]]))[0])


TRIES_KEY = "research:tries"  # every method name research has ever scored, so dropped rules still count
LUCK_ALPHA = 0.05


def _p_two_sided(t: float) -> float:
    return math.erfc(abs(float(t or 0.0)) / math.sqrt(2.0))


def _bar(m: int, alpha: float = LUCK_ALPHA) -> float:
    """Bonferroni two-sided critical t: with m methods tested, |t| must reach this before a 5% false alarm is likely
    for even one of them."""
    from statistics import NormalDist
    return float(NormalDist().inv_cdf(1.0 - alpha / (2.0 * max(1, m))))


def _holm(ts: dict, m: int, alpha: float = LUCK_ALPHA) -> set:
    """Holm step-down at `alpha` over m tests (m >= len(ts): untested past tries count too). A method clears only with
    a positive t. Assumes roughly independent tests; ours are correlated, so this errs on the strict side."""
    order = sorted(ts.items(), key=lambda kv: _p_two_sided(kv[1]))
    ok = set()
    for k, (name, t) in enumerate(order):
        if _p_two_sided(t) > alpha / max(1, m - k):
            break
        if t > 0:
            ok.add(name)
    return ok


def luck(results: dict, tries_ever: int | None = None) -> dict:
    """The luck bar (Harvey, Liu & Zhu 2016; Bailey & Lopez de Prado 2014): the more ways we try to pick the #1, the
    likelier one looks good by chance, so judge every method against how many were tried. Reporting only: the
    ranker v2 gate (_passes / fit_production) does not read this."""
    names = [k for k, v in (results or {}).items() if (v or {}).get("n")]
    m = max(len(names), int(tries_ever or 0))
    raw = {k: float(results[k].get("lift_t", 0) or 0) for k in names}
    adj = {k: float(results[k]["lift_adj_t"]) for k in names if results[k].get("lift_adj_t") is not None}
    clear, clear_adj = _holm(raw, m), _holm(adj, m)
    out = {"tests": len(names), "tries_ever": m, "alpha": LUCK_ALPHA, "bar": round(_bar(len(names)), 2),
           "bar_ever": round(_bar(m), 2), "clear": sorted(clear, key=lambda k: -raw[k]),
           "clear_adj": sorted(clear_adj, key=lambda k: -adj[k]),
           "app_clears": "app (current #1)" in clear, "app_clears_adj": "app (current #1)" in clear_adj}
    # the same bar on overlap-honest t's (_metrics lift_t_nw): a stricter lens, reporting only
    nw = {k: float(results[k]["lift_t_nw"]) for k in names if results[k].get("lift_t_nw") is not None}
    if nw:
        nwa = {k: float(results[k]["lift_adj_t_nw"]) for k in names if results[k].get("lift_adj_t_nw") is not None}
        c_nw, c_nwa = _holm(nw, m), _holm(nwa, m)
        app = results.get("app (current #1)") or {}
        out.update({"clear_nw": sorted(c_nw, key=lambda k: -nw[k]), "clear_adj_nw": sorted(c_nwa, key=lambda k: -nwa[k]),
                    "app_clears_nw": "app (current #1)" in c_nw, "app_clears_adj_nw": "app (current #1)" in c_nwa,
                    "app_t": app.get("lift_t"), "app_t_nw": app.get("lift_t_nw"),
                    "app_dates": app.get("dates"), "app_n_eff": app.get("n_eff")})
    # the same bar on outlier-clipped lifts (_metrics lift_w_t): does an edge survive without its few huge calls?
    w = {k: float(results[k]["lift_w_t"]) for k in names if results[k].get("lift_w_t") is not None}
    if w:
        app = results.get("app (current #1)") or {}
        c_w = _holm(w, m)
        out.update({"clear_w": sorted(c_w, key=lambda k: -w[k]), "app_clears_w": "app (current #1)" in c_w,
                    "app_lift": app.get("lift"), "app_lift_w": app.get("lift_w"), "app_lift_w_t": app.get("lift_w_t"),
                    "app_lift_med": app.get("lift_med"), "app_top10_share": app.get("top10_share")})
    # does it hold in every stretch of time? a cleared result ahead in fewer than STEADY_MIN stretches may be an episode
    bl = {k: results[k] for k in names if results[k].get("pos_blocks") is not None}
    if bl:
        ok = lambda k: k in bl and bl[k]["pos_blocks"] >= min(STEADY_MIN, bl[k].get("n_blocks") or TIME_BLOCKS)
        pick = lambda r: {q: (r or {}).get(q) for q in ("blocks", "pos_blocks", "n_blocks", "last_block_lift", "block_spread")}
        out.update({"steady": [k for k in out["clear"] if ok(k)], "steady_min": STEADY_MIN,
                    "app_blocks": pick(results.get("app (current #1)")), "app_pit_blocks": pick(results.get(VS_APP_BASE))})
        if "clear_nw" in out:
            out["steady_nw"] = [k for k in out["clear_nw"] if ok(k)]
    return out


def _tries(names) -> int:
    """Add this run's method names to the running set of everything research has ever scored; return its size."""
    try:
        row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (TRIES_KEY,))
        seen = set(json.loads(row["v"]) if row and row.get("v") else [])
    except Exception:
        seen = set()
    seen |= set(names)
    try:
        db.execute("DELETE FROM kv_cache WHERE k = ?", (TRIES_KEY,))
        db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                   (TRIES_KEY, json.dumps(sorted(seen)), datetime.now(timezone.utc).isoformat()))
    except Exception:
        pass
    return len(seen)


class _Reads:
    """Stands in for a candidate row and records which keys a rule reads (so each rule's inputs are never
    listed by hand and can't drift from its code)."""
    def __init__(self):
        self.keys: set[str] = set()

    def __getitem__(self, k: str) -> float:
        self.keys.add(k)
        return 0.0

    def get(self, k: str, default: float = 0.0) -> float:
        return self[k]


def rule_inputs(fn) -> list[str]:
    """The stored features a fixed rule reads ("z_seas" -> "seas"), limited to COV_KEYS."""
    r = _Reads()
    try:
        fn(r)
    except Exception:
        return []
    out = {k[2:] if k.startswith("z_") else k for k in r.keys}
    return sorted(k for k in out if k in COV_BIT)


def coverage(beliefs: list[dict]) -> dict:
    """Share of candidates that stored each feature, and the share of those that stored exactly 0. Counts only."""
    n, miss, zero = 0, dict.fromkeys(COV_KEYS, 0), dict.fromkeys(COV_KEYS, 0)
    for b in beliefs:
        for c in b["cands"]:
            n += 1
            m, z = int(c.get("miss", 0)), int(c.get("zero", 0))
            if m or z:
                for k, bit in COV_BIT.items():
                    if m & bit:
                        miss[k] += 1
                    elif z & bit:
                        zero[k] += 1
    if not n:
        return {"n": 0, "share": {}, "zero_share": {}}
    return {"n": n, "share": {k: round(1 - miss[k] / n, 4) for k in COV_KEYS},
            "zero_share": {k: round(zero[k] / max(1, n - miss[k]), 4) for k in COV_KEYS}}


def provisional(fixed: dict, cov: dict, ok: float = COVERAGE_OK) -> dict:
    """{rule: {feature: coverage}} for each fixed rule that reads a feature still under `ok` (still filling in)."""
    share = cov.get("share") or {}
    out = {}
    for name, fn in fixed.items():
        if fn is None:
            continue
        low = {k: share[k] for k in rule_inputs(fn) if k in share and share[k] < ok}
        if low:
            out[name] = low
    return out


def learn_keys(cov: dict, ok: float = COVERAGE_OK) -> list[str]:
    """The inputs the learned rankers (ridge, trees, neural net) may use: every z-scored feature (and interaction)
    whose stored values cover at least `ok` of the graded ideas. A feature the scout just added is filled in over days
    by `enrich`; until then most ideas carry a placeholder (NEUTRAL or 0), so the models fit the fill pattern, not the
    feature, and live calls (always fully filled) look unlike training. On 2026-11-17 `delay` was 12.6% filled, ridge
    gave z_delay a weight as large as z_vol60's, and on the same 4,391 beliefs with deterministic seeds the neural net
    (risk-adjusted) fell from +0.96% lift (t 3.14, live since that morning) to +0.62% (t 1.95) and switched off. The
    fixed rule for a new feature is still scored (marked provisional) while it fills; it joins the learned models once
    filled. Never adds inputs, only holds back unfilled ones."""
    share = (cov or {}).get("share") or {}
    low = {k for k, v in share.items() if v < ok}
    if not low:
        return list(ZKEYS)
    bad = {f"zx_{a}_{g}" for a, g in INTERACTIONS if a in low or g in low}
    return [k for k in ZKEYS if k not in bad and not (k.startswith("z_") and k[2:] in low)]


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
        # idea log, added 2026-11-12: continuing overreaction — heavy volume on up months for a long (down, for a short)
        "continuing overreaction (z_co)": lambda f: f["z_co"],
        # idea log, added 2026-11-13: return seasonality — the stock that did best in the same ~3 months of past years
        # (worst, for a short)
        "same season, past years (z_seas)": lambda f: f["z_seas"],
        # idea log, added 2026-11-14: downside risk premium — the stock that falls hardest on bad market days beyond
        # its plain beta for a long (the least exposed, for a short)
        "downside beta premium (z_dbeta)": lambda f: f["z_dbeta"],
        # idea log, added 2026-11-14: short-term reversal (Jegadeesh 1990) — last month's loser for a long (last month's
        # winner, for a short); uses the stored 20-session return, so nothing to backfill
        "short-term reversal (-z_mom20)": lambda f: -f["z_mom20"],
        # idea log, added 2026-11-14: idiosyncratic volatility puzzle (Ang et al. 2006) — the stock with the calmest
        # last month beyond what the market explains for a long (the wildest, for a short)
        "low idiosyncratic vol (-z_ivol)": lambda f: -f["z_ivol"],
        # idea log, added 2026-11-15: long-term reversal (De Bondt & Thaler 1985) — the stock that fell most from ~3 years
        # to ~1 year ago for a long (the one that rose most, for a short); the latest year is skipped
        "long-term reversal (-z_ltr)": lambda f: -f["z_ltr"],
        # idea log, added 2026-11-16: price delay premium (Hou & Moskowitz 2005) — the stock whose price follows the
        # market weeks late for a long (the one that reacts at once, for a short)
        "price delay premium (z_delay)": lambda f: f["z_delay"],
        # idea log, added 2026-11-17: realized skewness (Amaya, Christoffersen, Jacobs & Vasquez 2015) — the stock with
        # the most left-skewed recent daily returns for a long (the most right-skewed, lottery-like one, for a short)
        "avoid right-skewed stocks (-z_rskew)": lambda f: -f["z_rskew"],
        # idea log, added 2026-11-18: coskewness (Harvey & Siddique 2000) — the stock that does worst when the market
        # swings hardest (most negative coskewness, which investors pay to avoid) for a long (most positive, for a short)
        "negative coskewness premium (-z_coskew)": lambda f: -f["z_coskew"],
        # idea log, added 2026-11-21: variability of trading activity (Chordia, Subrahmanyam & Anshuman 2001) — the stock
        # whose dollar volume has been steadiest for a long (the one whose trading swings the most, for a short)
        "steady trading activity (-z_cvvol)": lambda f: -f["z_cvvol"],
        # idea log, added 2026-11-21 (late): timing of the 52-week high (Bhootra & Hur 2013) — the stock that set its 52-week
        # high most recently for a long (the one whose high is the most distant, for a short)
        "recent 52-week high (-z_hi_age)": lambda f: -f["z_hi_age"],
        # idea log, added 2026-11-21 (night): level of trading activity (Brennan, Chordia & Subrahmanyam 1998) — the
        # stock with the least dollar volume for a long (the most heavily traded one, for a short)
        "low dollar volume (-z_ldvol)": lambda f: -f["z_ldvol"],
        # idea log, added 2026-11-22: volatility of volatility (Baltussen, van Bekkum & van der Grient 2018) — the stock
        # whose own risk has been steadiest month to month for a long (the one whose volatility swings most, for a short)
        "steady volatility (-z_vov)": lambda f: -f["z_vov"],
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
    # only features filled in on (nearly) every test-period idea, the same coverage run() reports; see learn_keys
    zkeys = learn_keys(coverage([b for b in data if b["date"] >= dates[int(len(dates) * 0.4)]]))
    res = {k: [] for k in list(fixed) + ["ridge (learned)", "gbm (learned)", "gbm (risk-adjusted)",
                                          "neural net (learned)", "neural net (risk-adjusted)"]
               + (["gbm (+ shifted)", "gbm (risk-adjusted, + shifted)"] if aug else [])}
    # test blocks: the last 60% of dates split into `folds`; train on everything 90+ days before each block
    start = int(len(dates) * 0.4)
    blocks = np.array_split(np.array(dates[start:]), folds)
    weights = None
    # outlier check: clip at the pooled test-period ideas' 1st / 99th percentile; each test belief's clipped mean
    # rides along in _pick. Reporting only (the gate reads the plain lift and t).
    cuts = winsor_cuts([b for b in data if b["date"] >= dates[start]])
    for b in data:
        b.pop("wmean", None)
        if cuts and b["date"] >= dates[start]:
            b["wmean"] = float(np.mean(np.clip([c["ex"] for c in b["cands"]], cuts[0], cuts[1])))
    spreads: dict[str, list[float]] = {}
    off: dict[str, list[bool]] = {}  # test beliefs where the model's favourite idea was in the other direction
    # "is it new?" (reporting only): each method's #1 per test belief, and the app's no-look-ahead #1 to compare with
    chose: dict[str, list[tuple]] = {}
    base: dict[int, int] = {}

    def learned(name: str, fn, test: list[dict]) -> None:
        """Pick each test belief's top idea and remember how far it stood out (top score minus the belief's mean):
        the model's confidence, used to show how the most confident calls did."""
        for b in test:
            sc = [fn(c["f"]) for c in b["cands"]]
            i = _top(b, sc)  # within the belief's own direction, as the engine shows it
            off.setdefault(name, []).append(int(np.argmax(sc)) != i)
            res[name].append(_pick(b, b["cands"][i]))
            chose.setdefault(name, []).append((id(b), i, b))
            spreads.setdefault(name, []).append(float(sc[i] - np.mean(sc)))
            # what would go live: the model mixed into the app's score as it stood on the call's date. The stored score
            # of practice calls carries look-ahead (2026-11-09: ~2/3 of the app's lift); mixing into it let a mix
            # inherit that edge and clear the gate offline (2026-11-14 brain upgrade).
            mx = mix_scores([c.get("pit_app", c.get("app", 0.0)) for c in b["cands"]], sc, MIX_WEIGHT)
            j = _top(b, mx)
            res.setdefault(name + MIX, []).append(_pick(b, b["cands"][j]))
            chose.setdefault(name + MIX, []).append((id(b), j, b))
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
                for b in test:
                    j = _top(b, [c.get("pit", 0.0) for c in b["cands"]])
                    res[name].append(_pick(b, b["cands"][j]))
                    base[id(b)] = j
                    # confidence on the same point-in-time score the live engine computes (Claude + track record so
                    # far): how far the #1 stood out. The stored score's thirds carry look-ahead (2026-11-09).
                    pa = [c.get("pit_app", c.get("app", 0.0)) for c in b["cands"]]
                    spreads.setdefault(name, []).append(float(pa[j] - np.mean(pa)))
            elif fn is None:
                for b in test:
                    ti = next((q for q, c in enumerate(b["cands"]) if c["top"]), 0)
                    top = b["cands"][ti]
                    res[name].append(_pick(b, top))
                    chose.setdefault(name, []).append((id(b), ti, b))
                    spreads.setdefault(name, []).append(top.get("app", 0.0) - float(np.mean([c.get("app", 0.0) for c in b["cands"]])))
            else:
                for b in test:
                    i = _top(b, [fn(c["f"]) for c in b["cands"]])
                    res[name].append(_pick(b, b["cands"][i]))
                    chose.setdefault(name, []).append((id(b), i, b))
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
           "test_from": dates[start], "results": {k: _metrics(v, cuts) for k, v in res.items()},
           "winsor": {"q": WINSOR_Q, "lo": round(cuts[0], 4), "hi": round(cuts[1], 4)} if cuts else None,
           "ridge_weights_last": weights, "lead_only": True, "learn_keys": zkeys,
           "learn_held_back": [k for k in ZKEYS if k not in zkeys],
           "mixed_direction": round(float(np.mean([len(_lead(b)) < len(b["cands"]) for b in data[start:]])), 4),
           "off_lead": {k: round(float(np.mean(v)), 4) for k, v in off.items() if v},
           "beta_coverage": round(float(np.mean([c["has_beta"] for b in data for c in b["cands"]])), 3),
           "random_beat": round(float(np.mean([np.mean([c["ex"] > 0 for c in b["cands"]]) for b in data[start:]])), 4)}
    for name, rows in chose.items():  # "is it new?": agreement with the app's #1 and the head-to-head where they differ
        if name != VS_APP_BASE and name in out["results"]:
            out["results"][name].update(_vs_app(rows, base))
    out["luck"] = luck(out["results"], _tries([k for k, v in out["results"].items() if v.get("n")]))
    out["luck"]["is_new"] = is_new(out["results"])
    try:  # "would we have picked the winner?" across every way tested, and among the ranker v2 candidates (reporting only)
        out["luck"]["pbo"] = pbo(res)
        out["luck"]["pbo_learned"] = pbo(res, only=[k for k in res if k in LEARNED or (k.endswith(MIX) and k[:-len(MIX)] in LEARNED)])
    except Exception as e:
        out["luck"]["pbo"] = {"error": str(e)[:200]}
    if out["winsor"]:
        out["luck"]["winsor"] = out["winsor"]
    # feature coverage on the test-period calls (the ones every result is scored on); reporting only
    cov = coverage([b for b in data if b["date"] >= dates[start]])
    out["coverage"] = cov
    out["provisional"] = provisional(fixed, cov)
    out["low_coverage"] = {k: v for k, v in (cov.get("share") or {}).items() if v < COVERAGE_OK}
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
        try:  # base rates for "How sure" (at most once a day; the grading job refreshes it too)
            from . import baserate
            baserate.refresh_if_stale()
        except Exception:
            pass

    threading.Thread(target=go, name="research", daemon=True).start()


# ---------------------------------------------------------------------------------------------------------------
# Production ranker ("ranker v2"): the ridge model above, refit on every graded call, used to help choose the #1 pick
# ONLY while its walk-forward test (calls it never saw, 90-day embargo) shows a real edge over the app's old ranking.

RANKER_KEY = "ranker:v2"
ZKEYS = ["z_" + k for k in FEATS if k not in ("log_horizon", "conviction")] + ["bearish"] + list(XKEYS)
MIN_LIFT, MIN_T = 0.005, 1.5
# A model that passed the gate ALONE goes live alone: it orders the ideas inside the lead group exactly as in its
# walk-forward test. It used to go live at 0.5, a half-and-half blend with the app's score that no test ever measured
# (on 2026-11-16, the first day mlp_adj was active, the shown #1 was not the tested model's #1 in 17 of 62 real-time
# beliefs; the measured 25% blends kept under half the model's edge). A mix candidate runs at MIX_WEIGHT, as tested.
WEIGHT = 1.0
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


def live_check(model, mu, sd, w, days: int | None = None, min_calls: int | None = None,
               keys: list[str] | None = None, alone: bool = False) -> dict:
    """Would the mix (alone=True: the model on its own, as a lone ranker goes live) have done at least as well as the
    app's own #1 on calls made in real time (never practice, so no hindsight; all after every training outcome)? Needs
    min_calls such calls graded at `days`. model None = ridge. Calls that ranker v2 itself ordered are left out: their
    stored #1 is a ranker's pick, not the app's, so comparing against it would compare the model with itself."""
    days, min_calls = days or LIVE_DAYS, min_calls or LIVE_MIN_CALLS
    try:
        live = load(days=days, live_only=True)
    except Exception as e:
        return {"ok": False, "n": 0, "reason": f"{type(e).__name__}"}
    ranked = sum(1 for b in live if b.get("rv2"))
    live = [b for b in live if not b.get("rv2")]
    mix_p, app_p = [], []
    for b in live:
        xb = _matrix([b], keys or ZKEYS)
        sc = model.predict(xb) if model is not None else ((xb - np.asarray(mu)) / np.asarray(sd)) @ np.asarray(w)
        app = [c.get("app", 0.0) for c in b["cands"]]
        mix_p.append(_pick(b, b["cands"][_top(b, sc if alone else mix_scores(app, sc, MIX_WEIGHT))]))
        app_p.append(_pick(b, next((c for c in b["cands"] if c["top"]), b["cands"][_top(b, app)])))
    mm, am = _metrics(mix_p), _metrics(app_p)
    n = mm.get("n", 0)
    ok = n >= min_calls and mm.get("avg", 0) >= am.get("avg", 0)
    return {"ok": bool(ok), "n": n, "days": days, "needed": min_calls, "mix": mm, "app": am, "alone": alone,
            "ranker_ordered": ranked}


def live_veto(live: dict | None) -> bool:
    """A model that passed alone goes live without waiting for real-time proof (practice calls are all there is at first),
    but once enough real-time calls are graded it must not be doing worse than the app's own #1 on them."""
    return bool(live) and live.get("n", 0) >= live.get("needed", LIVE_MIN_CALLS) and not live.get("ok")


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
    # the same inputs the walk-forward test scored (features still filling in are held back; see learn_keys)
    keys = [k for k in (full.get("learn_keys") or learn_keys(coverage(data[len(data) * 2 // 5:]))) if k in ZKEYS] or list(ZKEYS)
    x, y = _xy(data, keys, "rel")
    mu, sd = x.mean(0), x.std(0) + 1e-9
    xs = (x - mu) / sd
    w = np.linalg.solve(xs.T @ xs + 5.0 * np.eye(len(keys)), xs.T @ y)
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
        xx, yy = _xy(fit_on, keys, cands[key][1])
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
            live = live_check(m, mu, sd, w, keys=keys)
            if not live.get("ok"):
                continue
        else:  # a lone model: vetoed once enough real-time calls show it doing worse than the app's #1 (live_veto)
            try:
                lv = {**live_check(m, mu, sd, w, keys=keys, alone=True), "candidate": k}
            except Exception:
                lv = None
            if live_veto(lv):
                live = lv
                continue
            live = lv
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
                live = {**live_check(fit(mixes[0])[1], mu, sd, w, keys=keys), "candidate": mixes[0]}
            except Exception:
                live = None
    # confidence cuts for whatever orders the live #1: this model if it is active, otherwise the app's own score —
    # judged without look-ahead, with cuts that split recent real-time calls into thirds (see _app_confidence)
    blocks = full.get("confidence") or {}
    conf = blocks.get(names.get(best, "")) if active else _app_confidence(blocks)
    out = {"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "model": best, "keys": keys, "mu": mu.tolist(),
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


CONF_LIVE_DAYS = 7     # real-time calls whose spread sets the live confidence cuts while the ranker is off. Short on
#                        purpose: on prod the median live spread stepped from ~0.12 to ~0.20 on Nov 9 and stayed there
CONF_LIVE_MIN = 150    # fewer than this: keep the walk-forward cuts


def _live_spreads(days: int = CONF_LIVE_DAYS) -> list[float]:
    """How far each recent real-time call's #1 stood out on the app's score (final_score of the #1 minus the belief's
    average idea), the same spread engine.process_belief labels. Aggregated in SQL: one number per belief."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.query(
        """SELECT MAX(CASE WHEN p.final_rank = 0 THEN p.final_score END) - AVG(p.final_score) AS sp
           FROM picks p JOIN beliefs b ON b.id = p.belief_id
           WHERE b.source <> 'seed_backfill' AND b.created_at >= ?
           GROUP BY p.belief_id HAVING COUNT(*) >= 2""", (since,))
    return [float(r["sp"]) for r in rows if r.get("sp") is not None]


def _app_confidence(blocks: dict) -> dict | None:
    """Confidence thirds for the live #1 while the ranker is off (the app's own score orders it).

    Before 2026-11-15 these were the thirds of the app's STORED score on practice calls, which carries look-ahead
    (track records that include later outcomes): its "high" third showed +2.5 pts. Now the thirds and their results
    come from the app's score as it stood on each call's date ("app, no look-ahead"). And the cuts: on prod, 56% of
    live #1 picks were labelled "high" and 15% "low" (Nov 8-15, 955 calls), because live spreads run wider than the
    practice ones the cuts came from. So when enough real-time calls exist (last CONF_LIVE_DAYS), the cuts split those
    calls into thirds;
    "high" then means the top third of how far a #1 stands out, as it did in the test. Labels only: no ordering."""
    conf = blocks.get("app, no look-ahead") or blocks.get("app (current #1)")
    if not conf:
        return conf
    conf = {**conf, "basis": "app, no look-ahead" if "app, no look-ahead" in blocks else "app (current #1)"}
    try:
        sp = _live_spreads()
    except Exception:
        sp = []
    if len(sp) >= CONF_LIVE_MIN:
        q1, q2 = (float(x) for x in np.quantile(np.array(sp), [1 / 3, 2 / 3]))
        conf.update({"cuts_test": conf.get("cuts"), "cuts": [round(q1, 6), round(q2, 6)], "cuts_from": "live",
                     "cuts_n": len(sp)})
    return conf


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
