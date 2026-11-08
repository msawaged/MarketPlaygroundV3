"""
Time-shifted practice calls: more graded training data for ranker v2 without any Claude calls.

Each practice (backfill) belief is a basket of ideas Claude picked for one theme on one past date. The same basket,
looked at a few months earlier or later, is another honest ranking problem: which of these ideas did best over the
next 90 days? Features are computed from prices up to the shifted date only, and the outcome is the 90-day move after
it, exactly like a real graded call. No new belief text, no Claude, just market data.

Rules that keep it honest (see research.run):
- shifted calls are only ever TRAINING data; every test is still on real calls;
- a shifted call is used only when both its own date and its source belief's date are before the training cutoff
  (so its 90-day outcome ends before the test block starts, and no test belief lends its basket to training);
- they are measured as their own candidates ("+ shifted"), so the walk-forward test decides whether they help.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

from . import db, market

DAYS = 90
SHIFTS = tuple(int(x) for x in os.getenv("MP_AUG_SHIFTS", "-91,91").split(",") if x.strip())
STATIC = ("same_dir", "log_horizon", "conviction", "is_etf", "claude_rank_frac", "n_cands")


def ensure_table() -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS aug_ideas (
            id TEXT PRIMARY KEY,
            basket TEXT NOT NULL,
            shift INTEGER NOT NULL,
            src_date TEXT NOT NULL,
            as_of TEXT NOT NULL,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            num TEXT,
            dir_excess REAL,
            ret REAL,
            spy_ret REAL,
            created_at TEXT NOT NULL
        )""")


def outcome(ticker: str, d: date, days: int = DAYS) -> tuple[float, float] | None:
    """(stock return, SPY return) from the close on/before d to the first close on/after d + days; None if not done."""
    try:
        _, p0 = market.price_on(ticker, d)
        _, s0 = market.price_on("SPY", d)
    except market.MarketDataError:
        return None
    end = d + timedelta(days=days)
    tk, sp = market.close_on_or_after(ticker, end), market.close_on_or_after("SPY", end)
    if not tk or not sp or tk[0] >= market.today().isoformat() or p0 <= 0 or s0 <= 0:
        return None
    return tk[1] / p0 - 1.0, sp[1] / s0 - 1.0


def _todo(limit: int) -> list[dict]:
    """Practice beliefs with 2+ directional ideas that have no shifted rows yet."""
    return db.query(
        """SELECT b.id, b.as_of_date FROM beliefs b
           WHERE b.source = 'seed_backfill'
             AND NOT EXISTS (SELECT 1 FROM aug_ideas a WHERE a.basket = b.id)
             AND (SELECT COUNT(*) FROM picks p WHERE p.belief_id = b.id AND p.direction IN ('bullish', 'bearish')) >= 2
           ORDER BY b.id LIMIT ?""", (limit,))


def generate(limit: int = 120, deadline: float | None = None) -> dict:
    """Add shifted copies for up to `limit` practice beliefs (a batch per hour from the seeder job)."""
    import time
    ensure_table()
    made, baskets, skipped = 0, 0, 0
    today = market.today()
    for b in _todo(limit):
        if deadline and time.time() > deadline:
            break
        src = date.fromisoformat(str(b["as_of_date"])[:10])
        picks = db.query("SELECT ticker, direction, features FROM picks WHERE belief_id = ? AND direction IN ('bullish', 'bearish')",
                         (b["id"],))
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for shift in SHIFTS:
            d = src + timedelta(days=shift)
            if d + timedelta(days=DAYS + 5) >= today:
                continue  # its outcome isn't known yet
            for p in picks:
                base = ((db.loads(p["features"], {}) or {}).get("num") or {})
                try:
                    f = market.features(p["ticker"], d)
                except market.MarketDataError:
                    continue
                oc = outcome(p["ticker"], d)
                if oc is None:
                    continue
                sign = -1.0 if p["direction"] == "bearish" else 1.0
                num = {**{k: v for k, v in f.items() if isinstance(v, (int, float))},
                       **{k: base[k] for k in STATIC if k in base}, "backfill": 1.0, "has_claude": 0.0}
                rows.append((f"{b['id']}|{shift}|{p['ticker']}|{p['direction']}", b["id"], shift, src.isoformat(),
                             d.isoformat(), p["ticker"], p["direction"], json.dumps(num),
                             sign * (oc[0] - oc[1]), oc[0], oc[1], now))
        if not rows:  # marker so the basket isn't retried every hour (no data that far back, or too recent)
            rows = [(f"{b['id']}|none", b["id"], 0, src.isoformat(), src.isoformat(), "", "none", None, None, None, None, now)]
            skipped += 1
        else:
            made += sum(1 for r in rows if r[8] is not None)
        db.executemany(
            """INSERT INTO aug_ideas (id, basket, shift, src_date, as_of, ticker, direction, num, dir_excess, ret, spy_ret,
                                      created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        baskets += 1
    left = len(_todo(1))
    return {"baskets": baskets, "ideas": made, "no_data": skipped, "more": bool(left)}


def stats() -> dict:
    ensure_table()
    r = db.query_one("SELECT COUNT(*) AS n, COUNT(DISTINCT basket) AS b FROM aug_ideas WHERE dir_excess IS NOT NULL") or {}
    return {"ideas": int(r.get("n") or 0), "baskets": int(r.get("b") or 0)}
