"""
"Same money in the S&P 500": every practice trade next to what the same dollars would have done in the S&P 500 (SPY)
over the same days.

A gain on its own says little: +$300 in a month when the market rose 5% on the same money is worse than buying the
index. Comparing a portfolio with a passive benchmark is how fund performance is judged (Jensen 1968; Sharpe 1966),
and most active stock pickers trail it after costs (SPIVA scorecards). The app already grades every call against
the S&P 500; this does the same for the practice account, dollar for dollar.

How it's measured (no look-ahead, daily data only):
- money = what the trade put to work (shares: quantity x average price; options: the cash set aside).
- the S&P leg runs from SPY's last close before the trade opened to its last close before it closed, or to SPY's
  live price if it's still open. "Before" is New York time: a trade at 2pm Tuesday starts from Monday's close, one at
  5pm Tuesday from Tuesday's close. So a trade held for a few hours inside one day compares against little or no S&P
  move, and the page says so.
- cash never invested isn't counted (it would earn the S&P's return in neither case).
- shorts are left out (a short profits when prices fall; the same-money long S&P comparison doesn't fit it), and so
  are older sales with no recorded cost.

Information only: it never feeds ranking, research, grading or anything that trades.
"""
from __future__ import annotations

import bisect
from datetime import datetime, time, timedelta, timezone
from typing import Callable, Optional

from . import market

SYMBOL = "SPY"


def _aware(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # bare practice times are the server's UTC clock


def level_before(ts, dates: list[str], closes: list[float]) -> Optional[tuple[str, float]]:
    """SPY's last daily close at or before the moment `ts` (New York time): a close counts once it's 4pm that day."""
    d = _aware(ts)
    if d is None or not dates:
        return None
    ny = d.astimezone(market.NY) if market.NY else d - timedelta(hours=5)
    day = ny.date() if ny.time() >= time(16) else ny.date() - timedelta(days=1)
    i = bisect.bisect_right(dates, day.isoformat()) - 1
    return (dates[i], closes[i]) if i >= 0 and closes[i] > 0 else None


def compare(trades: list[dict], dates: list[str], closes: list[float], live: Optional[float]) -> dict:
    """trades: {id, cost, pnl, opened_at, closed_at (None = still open), position_type}.
    Returns {"rows": {id: {...}}, "summary": {...} or None}."""
    rows: dict = {}
    for t in trades:
        cost, pnl = t.get("cost"), t.get("pnl")
        if cost is None or pnl is None or cost <= 0 or t.get("position_type") == "short":
            continue
        a = level_before(t.get("opened_at"), dates, closes)
        if a is None:
            continue
        if t.get("closed_at"):
            b = level_before(t["closed_at"], dates, closes)
            if b is None:
                continue
            end_on, end = b
        else:
            if not live or live <= 0:
                continue
            end_on, end = "now", float(live)
        spy_ret = end / a[1] - 1.0
        spy_gain = cost * spy_ret
        rows[t["id"]] = {"spy_ret": round(spy_ret * 100, 2), "spy_gain": round(spy_gain, 2),
                         "ahead": round(pnl - spy_gain, 2), "from": a[0], "to": end_on}
    if not rows:
        return {"rows": rows, "summary": None}
    used = [t for t in trades if t["id"] in rows]
    gain = sum(float(t["pnl"]) for t in used)
    spy_gain = sum(rows[t["id"]]["spy_gain"] for t in used)
    money = sum(float(t["cost"]) for t in used)
    return {"rows": rows, "summary": {
        "symbol": SYMBOL, "trades": len(used), "money": round(money, 2),
        "gain": round(gain, 2), "spy_gain": round(spy_gain, 2), "ahead": round(gain - spy_gain, 2),
        "beat": sum(1 for t in used if rows[t["id"]]["ahead"] > 0),
        "open": sum(1 for t in used if not t.get("closed_at")),
        "skipped_short": sum(1 for t in trades if t.get("position_type") == "short"),
        "since": min(rows[t["id"]]["from"] for t in used)}}


def _trades(portfolio: dict) -> list[dict]:
    out = []
    for p in portfolio.get("positions") or []:
        q, avg = float(p.get("quantity") or 0), float(p.get("avg_price") or 0)
        out.append({"id": f"pos:{p.get('position_id')}", "cost": q * avg, "pnl": float(p.get("unrealized_pnl") or 0),
                    "opened_at": p.get("opened_at"), "closed_at": None, "position_type": p.get("position_type")})
    for o in portfolio.get("option_positions") or []:
        out.append({"id": f"opt:{o.get('position_id')}", "cost": o.get("set_aside"), "pnl": o.get("pnl"),
                    "opened_at": o.get("opened_at"), "closed_at": None, "position_type": "options"})
    for c in portfolio.get("closed_trades") or []:
        out.append({"id": f"{c.get('kind')}:{c.get('id')}", "cost": c.get("cost"), "pnl": c.get("pnl"),
                    "opened_at": c.get("opened_at"), "closed_at": c.get("closed_at"),
                    "position_type": c.get("position_type") or c.get("kind")})
    return out


def attach(portfolio: dict, bars: Optional[Callable] = None, live: Optional[Callable] = None) -> dict:
    """Adds `vs_spy` to each position / options trade / closed trade it can measure, and portfolio["benchmark"]."""
    trades = _trades(portfolio)
    if not any(t["cost"] for t in trades):
        portfolio["benchmark"] = None
        return portfolio
    dates, closes = (bars or market.daily_closes)(SYMBOL)
    try:
        now = float((live or market.latest_price)(SYMBOL))
    except Exception:
        now = None  # open trades are skipped rather than measured against a stale price
    res = compare(trades, dates, closes, now)
    rows = res["rows"]
    for p in portfolio.get("positions") or []:
        p["vs_spy"] = rows.get(f"pos:{p.get('position_id')}")
    for o in portfolio.get("option_positions") or []:
        o["vs_spy"] = rows.get(f"opt:{o.get('position_id')}")
    for c in portfolio.get("closed_trades") or []:
        c["vs_spy"] = rows.get(f"{c.get('kind')}:{c.get('id')}")
    portfolio["benchmark"] = res["summary"]
    return portfolio
