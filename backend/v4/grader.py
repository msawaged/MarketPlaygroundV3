"""
Grades picks against what the market actually did, then (optionally)
retrains the neural network.

Checkpoints: 7, 30, 90, 180 and 365 days after entry (only those that have
passed). For each: ticker return, SPY return, and directional excess
(direction sign × (ticker − SPY)), plus the return of the chosen trade
structure.

Run as a daily cron:  PYTHONPATH=./ python -m backend.v4.grader --train
"""
from __future__ import annotations

import argparse
import bisect
import json
from datetime import date, datetime, timedelta, timezone

from . import db, learning, market, nn, strategy

CHECKPOINTS = (7, 30, 90, 180, 365)


def _due_picks(limit: int) -> list[dict]:
    last_cp = (market.today() - timedelta(days=min(CHECKPOINTS) + 1)).isoformat()
    return db.query(
        """SELECT p.id, p.ticker, p.direction, p.entry_date, p.entry_price, p.legs,
                  (SELECT COUNT(*) FROM outcomes o WHERE o.pick_id = p.id) AS n_done
           FROM picks p
           WHERE p.entry_date <= ?
           ORDER BY p.entry_date
           LIMIT ?""",
        (last_cp, limit),
    )


def grade(limit: int = 50000) -> dict:
    done, skipped, errors = 0, 0, 0
    today = market.today()
    rows_out = []
    for p in _due_picks(limit):
        entry = date.fromisoformat(p["entry_date"])
        due = [cp for cp in CHECKPOINTS if entry + timedelta(days=cp) < today]
        if p["n_done"] >= len(due):
            continue
        have = {r["checkpoint_days"] for r in db.query("SELECT checkpoint_days FROM outcomes WHERE pick_id = ?", (p["id"],))}
        try:
            spy_entry = market.price_on("SPY", entry)[1]
            dates, closes = market.daily_closes(p["ticker"])
            i0 = max(0, bisect.bisect_right(dates, p["entry_date"]) - 1)
            vol = market.realized_vol(closes, i0, 60) if closes else 0.35
        except market.MarketDataError:
            errors += 1
            continue
        sign = 1.0 if p["direction"] == "bullish" else -1.0
        trade = db.loads(p["legs"], {})
        for cp in due:
            if cp in have:
                continue
            target = entry + timedelta(days=cp)
            tk = market.close_on_or_after(p["ticker"], target)
            sp = market.close_on_or_after("SPY", target)
            if not tk or not sp or tk[0] >= today.isoformat():
                skipped += 1
                continue
            ret = tk[1] / p["entry_price"] - 1.0
            spy_ret = sp[1] / spy_entry - 1.0
            try:
                sret = strategy.structure_return(trade, p["entry_price"], tk[1], entry, date.fromisoformat(tk[0]), vol)
            except Exception:
                sret = None
            # volatile picks were a bet on a BIG move either way: did it move more than the market?
            dx = (abs(ret) - abs(spy_ret)) if p["direction"] == "volatile" else sign * (ret - spy_ret)
            rows_out.append((p["id"], cp, tk[0], tk[1], ret, spy_ret, dx, sret,
                             datetime.now(timezone.utc).isoformat()))
            done += 1
        if len(rows_out) >= 500:
            _flush(rows_out)
    _flush(rows_out)
    if done:
        learning.invalidate()
    return {"graded": done, "skipped": skipped, "errors": errors}


def _flush(rows: list) -> None:
    if not rows:
        return
    sql = """INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, structure_ret, graded_at)
             VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT (pick_id, checkpoint_days) DO NOTHING"""
    db.executemany(sql, rows)
    rows.clear()


def main() -> None:
    ap = argparse.ArgumentParser(description="Grade picks and retrain the network")
    ap.add_argument("--train", action="store_true", help="retrain the neural network after grading")
    ap.add_argument("--force-train", action="store_true", help="train even below the minimum data size (testing)")
    args = ap.parse_args()
    result = {"grade": grade()}
    if args.train or args.force_train:
        result["train"] = nn.train(force=args.force_train)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
