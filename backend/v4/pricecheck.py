"""
Option "Price check" (2026-11-10): is this option fairly priced, cheap or expensive, and what does it cost to trade?

Three honest checks, no "free money" claims:
  1. Put-call parity. For the same strike and expiration, C - P should be close to S - K*exp(-rT) (the European
     relationship; US stock options are American, so dividends, borrow costs and early exercise legitimately pull
     C - P below it). We say whether the gap is inside the bid-ask spread, and what it usually means when it isn't.
     Parity gaps on listed options are not an arbitrage for retail traders: market makers close real ones in
     microseconds, and the spreads on three legs cost more than the gap.
  2. Implied vs realized volatility. Implied volatility (the move the price assumes) vs how much the stock has
     actually moved over 20 and 60 trading days. Implied usually runs a little above realized (the variance risk
     premium), so "normal" reaches above 1x. With 20+ days of our own daily log we also show where today's
     at-the-money IV sits in its recent range.
  3. Trading cost: the bid-ask spread as a share of the price (what an immediate round trip costs).

Every check made for a pick is written to feature_log at the moment it is made (point in time), so the brain can
later test whether "cheap" options really did better, without look-ahead. The daily at-the-money IV log
(option_vol_daily) builds the history that test needs.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import db, market

_cache: dict = {}
CACHE_SECONDS = 600


def risk_free() -> float:
    """Annual risk-free rate (3-month T-bill, about 3.8% in Nov 2026). MP_RISK_FREE overrides."""
    return float(os.getenv("MP_RISK_FREE", "0.038"))


def _closest(rows: list[dict], kind: str, strike: float, expiration: date) -> Optional[dict]:
    rows = [r for r in rows if r["type"] == kind]
    if not rows:
        return None
    return min(rows, key=lambda r: abs((r["expiration"] - expiration).days) / 30.0 + abs(r["strike"] - strike) / max(strike, 1.0) * 10)


def _mid(r: Optional[dict]) -> Optional[float]:
    if not r or r["bid"] <= 0 or r["ask"] <= 0 or r["ask"] < r["bid"]:
        return None
    return (r["bid"] + r["ask"]) / 2


def parity(call: dict, put: dict, spot: float, rate: float, today: Optional[date] = None) -> Optional[dict]:
    """Pure: the parity gap for a call/put pair at the same strike and expiration."""
    cm, pm = _mid(call), _mid(put)
    if cm is None or pm is None or spot <= 0:
        return None
    t = max(1, (call["expiration"] - (today or date.today())).days) / 365.0
    k = call["strike"]
    lhs = cm - pm
    rhs = spot - k * math.exp(-rate * t)
    gap = lhs - rhs
    tol = (call["ask"] - call["bid"]) / 2 + (put["ask"] - put["bid"]) / 2 + 0.01
    return {"call_minus_put": round(lhs, 4), "parity_value": round(rhs, 4), "gap": round(gap, 4),
            "spread_cost": round(tol, 4), "within_spread": abs(gap) <= tol, "years": round(t, 4)}


def parity_text(p: Optional[dict], u: str) -> str:
    if not p:
        return "Couldn't compare with the matching put/call right now (no two-sided quotes)."
    if p["within_spread"]:
        return (f"Calls and puts at this strike agree with each other: put-call parity holds within the bid-ask spread "
                f"(gap ${abs(p['gap']):.2f} vs ${p['spread_cost']:.2f} of spread).")
    if p["gap"] < 0:
        return (f"Calls are about ${-p['gap']:.2f} a share cheaper than parity with the put says. That usually means the market "
                f"expects {u} dividends before expiration, the stock is costly to borrow, or the put carries early-exercise value. "
                f"Not free money: trading the three pieces costs about ${p['spread_cost']:.2f} in spreads, and big firms close real gaps instantly.")
    return (f"Calls are about ${p['gap']:.2f} a share richer than parity with the put says. That's rare and usually a stale or "
            f"one-sided quote, not a riskless gain: after spreads (about ${p['spread_cost']:.2f}) there's little or nothing left.")


def vol_verdict(iv: Optional[float], rv60: Optional[float]) -> tuple[str, Optional[float]]:
    if not iv or not rv60:
        return "unknown", None
    ratio = iv / rv60
    if ratio < 0.9:
        return "cheap", ratio
    if ratio > 1.35:
        return "expensive", ratio
    return "normal", ratio


def _vol_text(verdict: str, iv: Optional[float], rv20: Optional[float], rv60: Optional[float], ratio: Optional[float]) -> str:
    if verdict == "unknown":
        return "No implied volatility for this contract right now."
    base = (f"The price assumes {iv * 100:.0f}% yearly volatility; the stock actually moved {rv60 * 100:.0f}% (60 days) "
            f"and {rv20 * 100:.0f}% (20 days), so implied is {ratio:.2f}x realized.")
    if verdict == "cheap":
        return base + " That's cheap: you're paying for less movement than the stock has been showing."
    if verdict == "expensive":
        return base + " That's expensive: the stock has to move more than it has been for this to pay off. Often it's an earnings date or news."
    return base + " That's normal (implied usually runs a bit above realized)."


def _history(u: str, atm_iv: Optional[float]) -> Optional[dict]:
    if not atm_iv:
        return None
    since = (date.today() - timedelta(days=370)).isoformat()
    rows = [r["atm_iv"] for r in db.query("SELECT atm_iv FROM option_vol_daily WHERE underlying = ? AND day >= ? AND atm_iv IS NOT NULL",
                                          (u, since))]
    if len(rows) < 20:
        return {"days": len(rows), "percentile": None}
    below = sum(1 for v in rows if v < atm_iv)
    return {"days": len(rows), "percentile": round(below / len(rows), 3)}


def _atm(chain: list[dict], spot: float, target: date) -> tuple[Optional[float], Optional[int], Optional[float]]:
    """At-the-money IV (avg of call and put nearest the spot, expiration nearest target), its days, and put-call skew."""
    if not chain:
        return None, None, None
    exp = min({r["expiration"] for r in chain}, key=lambda e: abs((e - target).days))
    same = [r for r in chain if r["expiration"] == exp and r["iv"]]
    if not same:
        return None, None, None
    k = min({r["strike"] for r in same}, key=lambda s: abs(s - spot))
    c = next((r["iv"] for r in same if r["strike"] == k and r["type"] == "call"), None)
    p = next((r["iv"] for r in same if r["strike"] == k and r["type"] == "put"), None)
    ivs = [v for v in (c, p) if v]
    return (sum(ivs) / len(ivs) if ivs else None), (exp - date.today()).days, (p - c if c and p else None)


def check(underlying: str, option_type: str, strike: float, expiration: str, pick_id: Optional[str] = None) -> dict:
    u = underlying.upper().strip()
    kind = (option_type or "").lower()
    if kind not in ("call", "put"):
        return {"available": False, "reason": "Price check is for calls and puts."}
    try:
        exp = date.fromisoformat(str(expiration)[:10])
    except ValueError:
        return {"available": False, "reason": "That idea has no expiration date."}
    key = (u, kind, round(float(strike), 2), exp.isoformat())
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        res = hit[1]
    else:
        res = _compute(u, kind, float(strike), exp)
        _cache[key] = (time.time(), res)
    if pick_id and res.get("available"):
        try:
            db.execute("INSERT INTO feature_log (id, feature, subject, pick_id, as_of, value, created_at) VALUES (?,?,?,?,?,?,?)",
                       (f"fl-{uuid.uuid4().hex[:16]}", "price_check", res["contract"], pick_id, res["as_of"],
                        json.dumps({k: res[k] for k in ("iv", "rv20", "rv60", "iv_rv", "vol_verdict", "spread_pct", "parity")}),
                        datetime.now(timezone.utc).isoformat()))
        except Exception:
            pass
    return res


def _compute(u: str, kind: str, strike: float, exp: date) -> dict:
    chain = market.option_chain_near(u, strike, exp)
    c = _closest(chain, kind, strike, exp)
    if not c:
        return {"available": False, "reason": f"No live option prices for {u} near that strike and date right now."}
    twin = next((r for r in chain if r["type"] != kind and r["strike"] == c["strike"] and r["expiration"] == c["expiration"]), None)
    try:
        spot = market.latest_price(u)
        dates, closes = market.daily_closes(u)
        rv20 = market.realized_vol(closes, len(closes) - 1, 20) if len(closes) > 25 else None
        rv60 = market.realized_vol(closes, len(closes) - 1, 60) if len(closes) > 65 else None
    except Exception:
        return {"available": False, "reason": f"No stock price for {u} right now."}
    call, put = (c, twin) if kind == "call" else (twin, c)
    par = parity(call, put, spot, risk_free()) if twin else None
    mid = _mid(c)
    spread_pct = round((c["ask"] - c["bid"]) / mid, 4) if mid else None
    atm_iv, atm_days, skew = _atm(chain, spot, c["expiration"])
    # Deep in-the-money contracts often carry no IV in the feed. Parity implies the matching put/call has the same IV
    # (European), so use that, else the at-the-money level, and say which.
    iv, iv_src = c["iv"], "this contract"
    if not iv and twin and twin["iv"]:
        iv, iv_src = twin["iv"], f"the matching {twin['type']} (same strike and date)"
    elif not iv and atm_iv:
        iv, iv_src = atm_iv, "at-the-money options (this one has no quote-based volatility)"
    verdict, ratio = vol_verdict(iv, rv60)
    hist = _history(u, atm_iv)
    cost_text = ("No two-sided quote right now, so the trading cost is unknown." if spread_pct is None else
                 f"Buyers pay ${c['ask']:.2f}, sellers get ${c['bid']:.2f}: buying and selling right away would cost about "
                 f"{spread_pct * 100:.0f}% of the price." + (" That's a wide spread; use a limit order." if spread_pct > 0.1 else ""))
    hist_text = None
    if hist and hist["percentile"] is not None:
        hist_text = f"Today's at-the-money volatility is higher than on {hist['percentile'] * 100:.0f}% of the last {hist['days']} days we logged."
    elif hist:
        hist_text = f"We've logged {hist['days']} day{'s' if hist['days'] != 1 else ''} of {u} option volatility so far; a range comparison starts at 20."
    headline = {"cheap": "Cheap vs how much the stock moves", "expensive": "Expensive vs how much the stock moves",
                "normal": "Fairly priced", "unknown": "Partly checked"}[verdict]
    if par and not par["within_spread"] and verdict == "normal":
        headline = "Fairly priced, with a parity gap"
    return {
        "available": True, "as_of": datetime.now(timezone.utc).isoformat(), "underlying": u, "contract": c["symbol"],
        "type": kind, "strike": c["strike"], "expiration": c["expiration"].isoformat(), "spot": round(spot, 2),
        "bid": c["bid"], "ask": c["ask"], "mid": round(mid, 4) if mid else None, "spread_pct": spread_pct,
        "iv": round(iv, 4) if iv else None, "rv20": round(rv20, 4) if rv20 else None, "rv60": round(rv60, 4) if rv60 else None,
        "iv_rv": round(ratio, 3) if ratio else None, "vol_verdict": verdict, "parity": par, "risk_free": risk_free(),
        "atm_iv": round(atm_iv, 4) if atm_iv else None, "history": hist, "headline": headline,
        "iv_source": iv_src if iv else None,
        "lines": [l for l in (_vol_text(verdict, iv, rv20, rv60, ratio) + ("" if iv_src == "this contract" or not iv else f" (Volatility from {iv_src}.)"),
                              parity_text(par, u), cost_text, hist_text) if l],
        "note": ("Prices come from a free data feed that can lag a little. Parity uses mid prices and a "
                 f"{risk_free() * 100:.1f}% risk-free rate; US stock options are American-style, so dividends and early exercise "
                 "can explain a gap. A guide, not a guarantee."),
    }


def log_daily(limit: int = 60, force: bool = False) -> dict:
    """Once a trading day after the close: at-the-money IV, realized vol and skew for SPY, QQQ and recently shown tickers."""
    now = market.now_ny()
    day = now.date().isoformat()
    if not force:
        if now.weekday() >= 5 or (now.hour, now.minute) < (16, 15):
            return {"skipped": "not after today's close"}
        if db.query_one("SELECT v FROM kv_cache WHERE k = 'optvol:day'") == {"v": day}:
            return {"skipped": "already logged today"}
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = db.query("SELECT p.ticker, COUNT(*) n FROM picks p JOIN beliefs b ON b.id = p.belief_id "
                    "WHERE p.shown = 1 AND b.created_at >= ? GROUP BY p.ticker ORDER BY n DESC", (since,))
    tickers = ["SPY", "QQQ"] + [r["ticker"] for r in rows if r["ticker"] not in ("SPY", "QQQ")]
    done = 0
    for u in tickers[:limit]:
        try:
            spot = market.latest_price(u)
            chain = market.option_chain_near(u, spot, date.today() + timedelta(days=30), days=20, band=0.06)
            atm_iv, atm_days, skew = _atm(chain, spot, date.today() + timedelta(days=30))
            if atm_iv is None:
                continue
            dates, closes = market.daily_closes(u)
            rv20 = market.realized_vol(closes, len(closes) - 1, 20) if len(closes) > 25 else None
            rv60 = market.realized_vol(closes, len(closes) - 1, 60) if len(closes) > 65 else None
            db.execute("DELETE FROM option_vol_daily WHERE day = ? AND underlying = ?", (day, u))
            db.execute("INSERT INTO option_vol_daily (day, underlying, spot, atm_iv, atm_days, rv20, rv60, put_call_skew, created_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (day, u, spot, atm_iv, atm_days, rv20, rv60, skew, datetime.now(timezone.utc).isoformat()))
            done += 1
        except Exception:
            continue
    db.execute("DELETE FROM kv_cache WHERE k = 'optvol:day'")
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", ("optvol:day", day, datetime.now(timezone.utc).isoformat()))
    return {"logged": done, "day": day}
