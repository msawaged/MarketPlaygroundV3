"""
Trend-line lab: does MuLine actually beat ALMA and a plain 20-day average? Measured on real daily histories.

For each stock, the real turning points are found with hindsight: a top or bottom followed by a move of at least
SWING (a "zigzag"). Each line is then judged on what a user would feel:
  * lag         - trading days after a real top/bottom until the line turns the new way (lower = sooner)
  * false turns - times per year the line changes direction with no real turning point near it (lower = calmer)
A line only "wins" if it is quicker without being jumpier. Results are stored in kv_cache and shown on the Brain
page; nothing here touches anyone's picks.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Callable, Optional

from . import db, market

KEY = "trendlab:v1"
SWING = 0.10        # a real turn: price reverses at least 10% from the top/bottom
MATCH_DAYS = 20     # a line turn within this many days after a real turn counts as catching it
MIN_DAYS = 300      # skip stocks with less history
# each line -> its direction every day (+1 up / -1 down / 0 not started), the way the app would show it
LINES: dict[str, Callable[[list[float], Optional[list[float]]], list[int]]] = {
    "MuLine": lambda px, v: market.band_dirs(market.muline_series(px, v), px),
    "ALMA": lambda px, v: market.slope_dirs(market.alma_series(px)),
    "20-day average": lambda px, v: market.slope_dirs(market.sma_series(px, 20)),
}


def pivots(px: list[float], swing: float = SWING) -> list[tuple[int, int]]:
    """Real turning points with hindsight: [(index, +1 bottom / -1 top)], alternating."""
    out: list[tuple[int, int]] = []
    if len(px) < 3:
        return out
    trend, ext_i, lo_i, hi_i = 0, 0, 0, 0
    for i in range(1, len(px)):
        if trend == 1 and px[i] > px[ext_i]:
            ext_i = i
        elif trend == -1 and px[i] < px[ext_i]:
            ext_i = i
        if trend == 0:  # until the first real move, track the lowest and highest so far
            lo_i = i if px[i] < px[lo_i] else lo_i
            hi_i = i if px[i] > px[hi_i] else hi_i
            if px[i] >= px[lo_i] * (1 + swing):
                out.append((lo_i, 1)); trend, ext_i = 1, i
            elif px[i] <= px[hi_i] * (1 - swing):
                out.append((hi_i, -1)); trend, ext_i = -1, i
        elif trend == 1 and px[i] <= px[ext_i] * (1 - swing):
            out.append((ext_i, -1)); trend, ext_i = -1, i
        elif trend == -1 and px[i] >= px[ext_i] * (1 + swing):
            out.append((ext_i, 1)); trend, ext_i = 1, i
    return out


def judge(dirs: list[int], piv: list[tuple[int, int]]) -> dict:
    """Lag at each real turn and false turns, for one line's daily directions on one stock."""
    start = next((i for i, d in enumerate(dirs) if d), len(dirs))
    turns = [(i, d) for i, d in enumerate(dirs) if i > start and d and dirs[i - 1] and d != dirs[i - 1]]
    lags, matched = [], set()
    for p, kind in piv:
        if p <= start + 1:
            continue
        hit = next(((i, d) for i, d in turns if i >= p and d == kind), None)  # first turn the new way, at/after it
        if dirs[p] == kind and (not hit or hit[0] - p > MATCH_DAYS):
            lags.append(0)          # already pointing the new way at the turn itself
        elif hit and hit[0] - p <= MATCH_DAYS:
            lags.append(hit[0] - p)
            matched.add(hit[0])
        else:
            lags.append(MATCH_DAYS)  # missed it: counted as the maximum lag, never dropped
    span = max(1, len(dirs) - start)
    false_turns = sum(1 for i, _ in turns if i not in matched)
    return {"lags": lags, "false_per_year": false_turns / span * 252, "turns": len(turns), "real": len(piv)}


def run(tickers: list[str], as_of_max: Optional[str] = None) -> dict:
    """Race the lines on each ticker's full daily history (up to as_of_max)."""
    per: dict[str, dict[str, list]] = {k: {"lag": [], "false": []} for k in LINES}
    used = []
    for t in tickers:
        try:
            dates, px = market.daily_closes(t)
        except Exception:
            continue
        if as_of_max:
            cut = market._index_on_or_before(dates, as_of_max) + 1
            dates, px = dates[:cut], px[:cut]
        if len(px) < MIN_DAYS:
            continue
        vols = market.daily_volumes(t)
        vols = vols[:len(px)] if vols and len(vols) >= len(px) else None
        piv = pivots(px)
        if len(piv) < 3:
            continue
        used.append(t)
        for name, fn in LINES.items():
            j = judge(fn(px, vols), piv)
            per[name]["lag"] += j["lags"]
            per[name]["false"].append(j["false_per_year"])
    res = {}
    for name, v in per.items():
        if not v["lag"]:
            continue
        res[name] = {"avg_lag": round(statistics.mean(v["lag"]), 2), "median_lag": statistics.median(v["lag"]),
                     "false_per_year": round(statistics.mean(v["false"]), 2), "real_turns": len(v["lag"])}
    mu, al = res.get("MuLine"), res.get("ALMA")
    verdict = None
    if mu and al:
        quicker = mu["avg_lag"] < al["avg_lag"]
        calmer = mu["false_per_year"] <= al["false_per_year"]
        verdict = ("quicker and calmer" if quicker and calmer else "quicker but jumpier" if quicker
                   else "calmer but slower" if calmer else "not better yet")
    return {"at": datetime.now(timezone.utc).isoformat(), "stocks": len(used), "swing": SWING, "results": res,
            "verdict_vs_alma": verdict}


def run_and_store(limit: int = 150) -> dict:
    """The most-picked stocks and funds (plenty of history), raced and saved for the Brain page."""
    rows = db.query("SELECT ticker, COUNT(*) AS n FROM picks GROUP BY ticker ORDER BY COUNT(*) DESC LIMIT ?", (limit,))
    out = run([r["ticker"] for r in rows])
    db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (KEY, json.dumps(out), out["at"]))
    return out


def latest() -> Optional[dict]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (KEY,))
    return db.loads(row["v"], None) if row else None
