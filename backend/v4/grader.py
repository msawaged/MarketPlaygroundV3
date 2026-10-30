"""
Grades picks against what the market actually did, then (optionally)
retrains the neural network.

Checkpoints: 7, 30, 90, 180 and 365 days after entry (only those that have
passed). For each: ticker return, SPY return, and directional excess
(direction sign × (ticker − SPY)), plus the return of the chosen trade
structure.

Two separate questions are graded (score_selection):
  1. Was the user's call right?  belief_right: did the belief's theme beat the market in the
     direction they called? That part is on the user.
  2. Did we express it well?     sel_edge: did each pick beat the SIMPLE way to trade the same
     idea: the sector fund among the ideas if there is one, otherwise the average of all the
     ideas in the same direction. That part is on us, and it's what the network learns from.

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
        """SELECT p.id, p.ticker, p.direction, p.entry_date, p.entry_price, p.legs, p.spy_entry,
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
            spy_entry = float(p["spy_entry"]) if p.get("spy_entry") else market.price_on("SPY", entry)[1]
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
    sel = score_selection()
    if done or sel:
        learning.invalidate()
    return {"graded": done, "skipped": skipped, "errors": errors, "selection_scored": sel}


def _is_etf(row: dict) -> bool:
    if row.get("is_etf") is not None:
        return bool(row["is_etf"])
    f = db.loads(row.get("features"), {}) or {}
    return bool((f.get("num") or {}).get("is_etf"))


def _group_scores(rows: list[dict], core: str) -> list[tuple]:
    """rows: one belief's picks at one checkpoint. Returns update tuples
    (bench_ret, sel_edge, belief_right, bench_kind, pick_id, checkpoint_days)."""
    by_dir: dict[str, list[dict]] = {}
    for r in rows:
        by_dir.setdefault(r["direction"] or "bullish", []).append(r)
    bench: dict[str, tuple[float, str, set]] = {}
    for d, g in by_dir.items():
        funds = [r for r in g if r["etf"]]
        if funds:
            bench[d] = (sum(r["ret"] for r in funds) / len(funds), "fund", {r["pick_id"] for r in funds})
        else:
            bench[d] = (sum(r["ret"] for r in g) / len(g), "basket" if len(g) > 1 else "self", set())
    spy = rows[0]["spy_ret"]
    right = None
    if core in bench:
        b = bench[core][0]
        if core == "bullish":
            right = 1 if b > spy else 0
        elif core == "bearish":
            right = 1 if b < spy else 0
        elif core == "volatile":
            right = 1 if abs(b) > abs(spy) else 0
    out = []
    for r in rows:
        d = r["direction"] or "bullish"
        b, kind, fund_ids = bench[d]
        edge = None
        if kind != "self" and r["pick_id"] not in fund_ids:
            if d == "volatile":
                edge = abs(r["ret"]) - abs(b)
            else:
                edge = (1.0 if d == "bullish" else -1.0) * (r["ret"] - b)
        out.append((b, edge, right, kind, r["pick_id"], r["checkpoint_days"]))
    return out


def score_selection(max_beliefs: int = 5000) -> int:
    """Fill bench_ret / sel_edge / belief_right for graded outcomes (also catches up old rows).
    Waits until every pick of a belief has that checkpoint graded, or 5 days have passed."""
    pending = db.query(
        """SELECT DISTINCT p.belief_id FROM outcomes o JOIN picks p ON p.id = o.pick_id
           WHERE o.bench_ret IS NULL LIMIT ?""", (max_beliefs,))
    if not pending:
        return 0
    stale = (market.today() - timedelta(days=5)).isoformat()
    updates: list[tuple] = []
    ids = [r["belief_id"] for r in pending]
    for k in range(0, len(ids), 200):
        chunk = ids[k:k + 200]
        ph = ",".join("?" for _ in chunk)
        rows = db.query(
            f"""SELECT o.pick_id, o.checkpoint_days, o.ret, o.spy_ret, o.eval_date, o.bench_ret,
                       p.belief_id, p.direction, p.is_etf, p.features, b.direction AS core
                FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
                WHERE p.belief_id IN ({ph})""", chunk)
        counts = {r["belief_id"]: int(r["n"]) for r in db.query(
            f"SELECT belief_id, COUNT(*) AS n FROM picks WHERE belief_id IN ({ph}) GROUP BY belief_id", chunk)}
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            r["etf"] = _is_etf(r)
            r["ret"] = float(r["ret"])
            r["spy_ret"] = float(r["spy_ret"])
            groups.setdefault((r["belief_id"], r["checkpoint_days"]), []).append(r)
        for (bid, _cp), g in groups.items():
            if all(r["bench_ret"] is not None for r in g):
                continue
            if len(g) < counts.get(bid, 0) and max(r["eval_date"] for r in g) >= stale:
                continue  # wait for the rest of this belief's picks
            updates += _group_scores(g, g[0]["core"] or "")
    if updates:
        db.executemany("""UPDATE outcomes SET bench_ret = ?, sel_edge = ?, belief_right = ?, bench_kind = ?
                          WHERE pick_id = ? AND checkpoint_days = ?""", updates)
    return len(updates)


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
    from .seeder import record_health
    try:
        result = {"grade": grade()}
        if args.train or args.force_train:
            result["train"] = nn.train(force=args.force_train)
    except Exception as e:
        record_health("grading", False, f"{type(e).__name__}: {e}")
        raise
    record_health("grading", True, "", {"graded": result["grade"].get("graded", 0),
                                         "trained": (result.get("train") or {}).get("status")})
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
