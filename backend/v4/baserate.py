"""
"The outside view": how often calls like this one have come true before.

Before someone says how sure they are of a call, show them the base rate: of all the calls the app has graded in the
same direction at the same check (7 / 30 / 90 / 180 / 365 days), how many beat the S&P 500 that way. Same definition
the "How sure" calibration card scores against (grader belief_right: one result per call, the theme vs the S&P).

Base-rate neglect is the classic forecasting error (Kahneman & Lovallo 1993, "inside view" vs "outside view");
starting from the record of similar cases is the core of the training that improved forecasters' Brier scores
(Mellers et al. 2014).

The table is ~15 numbers, computed by the daily grading job (and at most once a day by the web service) into one
kv_cache row, never on a request. Each cell also carries the spread ("How wide it can go"): the 10th / 50th / 90th
percentile of how far those same calls finished from the S&P in the direction called, because a beginner reads "beat
the S&P 47% of the time" as a coin flip with small stakes (Goldstein, Johnson & Sharpe 2008: people judge risk better
from the range of outcomes than from summary numbers). Information only: it's the app's past record, not a forecast, and it never feeds
ranking, research or anything that trades.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional

from . import calibration, db

KEY = "baserate:v1"
MIN_N = 100            # a cell with fewer graded calls is not shown (too noisy to be a base rate)
MAX_AGE_S = 86400      # the web service refreshes it if older than this
DIRECTIONS = ("bullish", "bearish", "volatile")

_cache: dict = {"at": 0.0, "v": None}


def compute() -> dict:
    """One aggregate query (one row per direction x checkpoint), stored in kv. Safe on the 512Mi jobs."""
    agg = db.query(
        """SELECT b.direction AS direction, x.cp AS cp, COUNT(*) AS n, SUM(x.r) AS right_n,
                  MIN(b.as_of_date) AS since, MAX(b.as_of_date) AS upto
           FROM (SELECT p.belief_id, o.checkpoint_days AS cp, MAX(o.belief_right) AS r
                 FROM outcomes o JOIN picks p ON p.id = o.pick_id
                 WHERE o.belief_right IS NOT NULL
                 GROUP BY p.belief_id, o.checkpoint_days) x
           JOIN beliefs b ON b.id = x.belief_id
           GROUP BY b.direction, x.cp""")
    cells: dict = {}
    for r in agg:
        d = r["direction"]
        if d not in DIRECTIONS or not r["n"]:
            continue
        n, right = int(r["n"]), int(r["right_n"] or 0)
        cells.setdefault(d, {})[str(int(r["cp"]))] = {
            "n": n, "right": right, "beat": round(right / n, 3),
            "since": str(r["since"] or "")[:10] or None, "upto": str(r["upto"] or "")[:10] or None}
    for (d, cp), xs in _spreads().items():
        c = cells.get(d, {}).get(str(cp))
        if c is not None and len(xs) == c["n"]:  # same calls as the beat rate, or no spread at all
            c.update(p10=round(_pct(xs, 0.1), 4), p50=round(_pct(xs, 0.5), 4), p90=round(_pct(xs, 0.9), 4))
    out = {"at": datetime.now(timezone.utc).isoformat(), "min_n": MIN_N, "cells": cells}
    db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (KEY, json.dumps(out), out["at"]))
    _cache.update(at=time.time(), v=out)
    return out


def _pct(xs: list, q: float) -> float:
    """Linear-interpolated percentile of a sorted list (same as Postgres percentile_cont)."""
    k = (len(xs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _call_excess(direction: str, bench, spy) -> Optional[float]:
    """How far one call's theme finished from the S&P in the direction called (the number belief_right is the sign
    of: grader._group_scores compares the same theme return, bench_ret, with the S&P)."""
    if bench is None or spy is None:
        return None
    b, s = float(bench), float(spy)
    if direction == "bullish":
        return b - s
    if direction == "bearish":
        return s - b
    return abs(b) - abs(s)


def _spreads() -> dict:
    """'How wide it can go': per direction x checkpoint, the sorted call-level results (one number per call, the
    same calls the beat rate counts). One grouped query, ~15k small rows; fine for the 512Mi jobs."""
    rows = db.query(
        """SELECT b.direction AS direction, o.checkpoint_days AS cp, MAX(o.bench_ret) AS br, MAX(o.spy_ret) AS sr
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.belief_right IS NOT NULL AND p.direction = b.direction
           GROUP BY p.belief_id, o.checkpoint_days, b.direction""")
    out: dict = {}
    for r in rows:
        x = _call_excess(r["direction"], r["br"], r["sr"])
        if x is not None and r["direction"] in DIRECTIONS:
            out.setdefault((r["direction"], int(r["cp"])), []).append(x)
    for xs in out.values():
        xs.sort()
    return out


def latest() -> Optional[dict]:
    """The stored table (cached in-process for 10 minutes)."""
    if _cache["v"] is not None and time.time() - _cache["at"] < 600:
        return _cache["v"]
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (KEY,))
    try:
        v = json.loads(row["v"]) if row else None
    except (TypeError, ValueError):
        v = None
    _cache.update(at=time.time(), v=v)
    return v


def refresh_if_stale() -> None:
    v = latest()
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(v["at"])).total_seconds() if v else None
    except (KeyError, TypeError, ValueError):
        age = None
    if age is None or age > MAX_AGE_S:
        compute()


def public() -> dict:
    """What the app shows: only cells with at least MIN_N graded calls."""
    v = latest() or {}
    cells = {d: {cp: c for cp, c in by.items() if int(c.get("n") or 0) >= MIN_N}
             for d, by in (v.get("cells") or {}).items()}
    return {"at": v.get("at"), "min_n": MIN_N, "cells": {d: by for d, by in cells.items() if by}}


def for_call(direction: str, horizon_days) -> Optional[dict]:
    """The base rate for one call (None when that cell is too small or not computed yet)."""
    cp = calibration.checkpoint_for(horizon_days)
    c = ((public().get("cells") or {}).get(direction) or {}).get(str(cp))
    return dict(c, checkpoint_days=cp) if c else None
