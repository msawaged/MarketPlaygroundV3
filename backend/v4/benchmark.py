"""
"Same money in the S&P 500": every practice trade next to what the same dollars would have done in the S&P 500 (SPY)
over the same days.

A gain on its own says little: +$300 in a month when the market rose 5% on the same money is worse than buying the
index. Comparing a portfolio with a passive benchmark is how fund performance is judged (Jensen 1968; Sharpe 1966),
and most active stock pickers trail it after costs (SPIVA scorecards). The app already grades every call against
the S&P 500; this does the same for the practice account, dollar for dollar.

How it's measured (no look-ahead, daily data only):
- money = what the trade put to work (shares: quantity x average price; options: the cash set aside).
- the S&P leg runs from SPY's price when the trade opened to its price when it closed, or to SPY's live price if it's
  still open. A moment inside regular hours (9:30-4pm New York) uses SPY's 5-minute bar it falls in (the bar's open,
  so within 5 minutes and never later than the moment); a moment while the market is closed uses the last close before
  it. So a trade opened at 2pm is not charged with the S&P's move that morning (the old close-to-close rule did that,
  and showed a brand-new trade "behind the S&P" before it had a chance to move). If the 5-minute bars can't be
  fetched, it falls back to the last close before the moment.
- cash never invested isn't counted (it would earn the S&P's return in neither case).
- shorts are left out (a short profits when prices fall; the same-money long S&P comparison doesn't fit it), and so
  are older sales with no recorded cost.

Information only: it never feeds ranking, research, grading or anything that trades.
"""
from __future__ import annotations

import bisect
import os
import threading
import time as _clock
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


def in_session(ts, dates: list[str]) -> Optional[datetime]:
    """The moment in New York time if it falls inside a regular session (9:30-4pm on a day SPY traded, or today),
    else None."""
    d = _aware(ts)
    if d is None:
        return None
    ny = d.astimezone(market.NY) if market.NY else d - timedelta(hours=5)
    if ny.weekday() >= 5 or not (time(9, 30) <= ny.time() < time(16)):
        return None
    day = ny.date().isoformat()
    i = bisect.bisect_left(dates, day)
    if (i < len(dates) and dates[i] == day) or day == market.today().isoformat():
        return ny
    return None  # a holiday


def level_at(ts, dates: list[str], closes: list[float], at: Optional[Callable] = None) -> Optional[tuple[str, float]]:
    """SPY at the moment `ts`: its 5-minute bar if the market was open (via `at(ny_moment)` -> price or None),
    otherwise (or if no bar) the last close before it."""
    if at is not None:
        ny = in_session(ts, dates)
        if ny is not None:
            try:
                px = at(ny)
            except Exception:
                px = None
            if px and px > 0:
                return (ny.date().isoformat(), float(px))
    return level_before(ts, dates, closes)


def compare(trades: list[dict], dates: list[str], closes: list[float], live: Optional[float],
            at: Optional[Callable] = None) -> dict:
    """trades: {id, cost, pnl, opened_at, closed_at (None = still open), position_type}.
    `at(ny_moment)`: SPY's price at a moment inside a session (None = use the last close before it).
    Returns {"rows": {id: {...}}, "summary": {...} or None}."""
    rows: dict = {}
    for t in trades:
        cost, pnl = t.get("cost"), t.get("pnl")
        if cost is None or pnl is None or cost <= 0 or t.get("position_type") == "short":
            continue
        a = level_at(t.get("opened_at"), dates, closes, at)
        if a is None:
            continue
        if t.get("closed_at"):
            b = level_at(t["closed_at"], dates, closes, at)
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


_bars5: dict[str, tuple[float, list]] = {}
_bars5_lock = threading.Lock()
MAX_DAYS_FETCHED = 12  # per portfolio load; beyond that, moments fall back to the last close


def _five_minute_bars(day: str) -> list[tuple[datetime, float]]:
    """SPY's 5-minute bars (start, open) for one New York trading day, adjusted like the daily closes. Cached:
    a past day for 6 hours, today for 2 minutes."""
    ttl = 120 if day == market.today().isoformat() else 6 * 3600
    with _bars5_lock:
        hit = _bars5.get(day)
        if hit and _clock.time() - hit[0] < ttl:
            return hit[1]
    start = market._session_open_dt(day)
    r = market._session.get(f"{market._data_base()}/v2/stocks/{SYMBOL}/bars", headers=market._headers(), params={
        "timeframe": "5Min", "start": start.isoformat(), "end": (start + timedelta(hours=6, minutes=30)).isoformat(),
        "adjustment": "all", "feed": os.getenv("ALPACA_DATA_FEED", "iex"), "limit": 200}, timeout=8)
    if r.status_code != 200:
        raise market.MarketDataError(f"5Min bars {SYMBOL} {day}: HTTP {r.status_code}")
    out = sorted((datetime.fromisoformat(b["t"].replace("Z", "+00:00")), float(b["o"]))
                 for b in (r.json().get("bars") or []))
    with _bars5_lock:
        _bars5[day] = (_clock.time(), out)
    return out


def _price_at_factory(fetch: Callable = _five_minute_bars) -> Callable:
    """at(ny_moment) -> the open of the 5-minute bar the moment falls in (or the last bar that started before it)."""
    days: dict[str, Optional[list]] = {}

    def at(ny: datetime) -> Optional[float]:
        day = ny.date().isoformat()
        if day not in days:
            if len(days) >= MAX_DAYS_FETCHED:
                return None
            try:
                days[day] = fetch(day)
            except Exception:
                days[day] = None
        bars = days[day]
        if not bars:
            return None
        i = bisect.bisect_right([b[0] for b in bars], ny) - 1
        if i < 0 or ny - bars[i][0] > timedelta(minutes=30):  # no bar near the moment (thin data): don't guess
            return None
        return bars[i][1]
    return at


def attach(portfolio: dict, bars: Optional[Callable] = None, live: Optional[Callable] = None,
           at: Optional[Callable] = None) -> dict:
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
    res = compare(trades, dates, closes, now, at if at is not None else _price_at_factory())
    rows = res["rows"]
    for p in portfolio.get("positions") or []:
        p["vs_spy"] = rows.get(f"pos:{p.get('position_id')}")
    for o in portfolio.get("option_positions") or []:
        o["vs_spy"] = rows.get(f"opt:{o.get('position_id')}")
    for c in portfolio.get("closed_trades") or []:
        c["vs_spy"] = rows.get(f"{c.get('kind')}:{c.get('id')}")
    portfolio["benchmark"] = res["summary"]
    return portfolio
