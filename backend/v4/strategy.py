"""
Rule-based trade structure for v4.

Claude decides WHAT the belief means and WHICH tickers express it. Plain,
predictable rules decide HOW to trade it (structure, strikes, expiry). The
rules are nudged over time by graded results across all users
(see learning.structure_stats), not by guesswork.

Option premiums here are Black-Scholes estimates from realized volatility —
good enough to grade structures consistently. Live quotes should be checked
before placing a real order.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

STRUCTURES = (
    "Buy Stock",
    "Long Call",
    "Bull Call Spread",
    "Long Put",
    "Bear Put Spread",
    "Iron Condor",
    "Sell / Avoid",
)
BULLISH = {"Buy Stock", "Long Call", "Bull Call Spread"}
BEARISH = {"Long Put", "Bear Put Spread", "Sell / Avoid"}
RISK_FREE = 0.04


def horizon_bucket(days: int) -> str:
    if days <= 45:
        return "short"
    if days <= 180:
        return "medium"
    return "long"


def default_structure(direction: str, horizon_days: int, conviction: str, risk_profile: str) -> str:
    risk = (risk_profile or "moderate").lower()
    bucket = horizon_bucket(horizon_days)
    if direction == "bullish":
        if risk == "conservative" or bucket == "long":
            return "Buy Stock"
        if risk == "aggressive" and conviction == "high" and bucket == "medium":
            return "Long Call"
        return "Bull Call Spread"
    if direction == "bearish":
        if risk == "conservative":
            return "Sell / Avoid"
        if risk == "aggressive" and conviction == "high":
            return "Long Put"
        return "Bear Put Spread"
    # neutral
    if risk == "conservative":
        return "Sell / Avoid"
    return "Iron Condor"


OPTION_STRUCTURES = {"Long Call", "Bull Call Spread", "Long Put", "Bear Put Spread", "Iron Condor"}


def vary_structure(structure: str, direction: str, risk_profile: str, rank: int, is_etf: bool, price: float) -> tuple[str, str]:
    """
    Give each belief a mix of ways to trade it instead of three copies of one structure.
    - Cheap stocks (< $10) get shares: their options are usually thin and costly to trade.
    - Balanced (moderate), bullish: funds and the 2nd idea are shares, so there's always a simple
      share-based option next to the options spreads. Bold stays all-options; Careful is all shares already.
    """
    risk = (risk_profile or "moderate").lower()
    if structure in OPTION_STRUCTURES and price < 10:
        return ("Buy Stock" if direction == "bullish" else "Sell / Avoid"), "low price: options are thin"
    if risk == "moderate" and direction == "bullish" and structure in OPTION_STRUCTURES and (is_etf or rank == 1):
        return "Buy Stock", "mix: a simple share-based idea"
    return structure, ""


def choose_structure(
    direction: str,
    horizon_days: int,
    conviction: str,
    risk_profile: str,
    stats: Optional[dict] = None,
    min_samples: int = 40,
    min_edge: float = 0.02,
) -> tuple[str, str]:
    """
    Returns (structure, reason). `stats` maps structure -> {"n": int, "mean": float}
    of graded structure returns for this direction + horizon bucket across ALL users.
    A rule default is only overridden when another structure that fits the same
    direction has enough samples and a clear edge.
    """
    base = default_structure(direction, horizon_days, conviction, risk_profile)
    if not stats:
        return base, "rule"
    allowed = BULLISH if direction == "bullish" else BEARISH if direction == "bearish" else {"Iron Condor", "Sell / Avoid"}
    if (risk_profile or "").lower() == "conservative":
        allowed = {s for s in allowed if s in ("Buy Stock", "Bear Put Spread", "Sell / Avoid")}
    base_mean = (stats.get(base) or {}).get("mean")
    best, best_mean = base, base_mean if base_mean is not None else -1e9
    for s in allowed:
        st = stats.get(s) or {}
        if st.get("n", 0) >= min_samples and st.get("mean") is not None and st["mean"] > best_mean + min_edge:
            best, best_mean = s, st["mean"]
    if best != base:
        return best, f"learned: {best} has outperformed {base} for {direction}/{horizon_bucket(horizon_days)} beliefs"
    return base, "rule"


# ---------- option math ----------

def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(spot: float, strike: float, t_years: float, vol: float, kind: str) -> float:
    if t_years <= 0 or vol <= 0:
        return max(0.0, spot - strike) if kind == "call" else max(0.0, strike - spot)
    sq = vol * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (RISK_FREE + 0.5 * vol * vol) * t_years) / sq
    d2 = d1 - sq
    disc = math.exp(-RISK_FREE * t_years)
    if kind == "call":
        return spot * _ncdf(d1) - strike * disc * _ncdf(d2)
    return strike * disc * _ncdf(-d2) - spot * _ncdf(-d1)


def strike_step(price: float) -> float:
    if price < 25:
        return 0.5
    if price < 100:
        return 1.0
    if price < 250:
        return 2.5
    return 5.0


def round_strike(x: float, price: float) -> float:
    step = strike_step(price)
    return round(round(x / step) * step, 2)


def third_friday(year: int, month: int) -> date:
    d = date(year, month, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


MIN_DAYS_TO_EXPIRY = 30


def pick_expiry(as_of: date, horizon_days: int) -> date:
    # Never short-fuse: at least 30 days. Same-day and short-dated options lose beginners the most
    # (Bogousslavsky & Muravyev 2025: 0DTE trades averaged -4.6% vs +0.1% for other options).
    target = as_of + timedelta(days=max(MIN_DAYS_TO_EXPIRY, min(horizon_days, 730)))
    y, m = target.year, target.month
    exp = third_friday(y, m)
    if exp < target:
        m = 1 if m == 12 else m + 1
        y = y + 1 if m == 1 else y
        exp = third_friday(y, m)
    return exp


def build_trade(structure: str, ticker: str, price: float, vol: float, as_of: date, horizon_days: int) -> dict:
    """Legs + estimated economics for one structure."""
    if structure in ("Buy Stock", "Sell / Avoid"):
        action = "Buy" if structure == "Buy Stock" else "Sell / avoid"
        return {
            "type": structure,
            "expiration": None,
            "trade_legs": [{"action": action, "ticker": ticker, "quantity": 1, "instrument": "stock"}],
            "net_cost": price if structure == "Buy Stock" else 0.0,
            "max_loss": "Full position value" if structure == "Buy Stock" else None,
            "max_profit": "Unlimited" if structure == "Buy Stock" else None,
            "break_even": round(price, 2) if structure == "Buy Stock" else None,
            "estimated": False,
            "vol": round(vol, 4),
        }

    exp = pick_expiry(as_of, horizon_days)
    t = max((exp - as_of).days, 1) / 365.0
    sd = price * vol * math.sqrt(t)
    legs: list[dict] = []

    def leg(action: str, kind: str, k: float) -> dict:
        prem = bs_price(price, k, t, vol, kind)
        legs.append({
            "action": action, "ticker": ticker, "option_type": kind.capitalize(),
            "strike_price": k, "expiration": exp.isoformat(), "quantity": 1,
            "est_premium": round(prem, 2), "instrument": "option",
        })
        return {"k": k, "p": prem}

    if structure == "Long Call":
        a = leg("Buy", "call", round_strike(price * 0.97, price))
        cost = a["p"]
        out = {"max_loss": round(cost * 100, 2), "max_profit": "Unlimited", "break_even": round(a["k"] + cost, 2)}
    elif structure == "Long Put":
        a = leg("Buy", "put", round_strike(price * 1.03, price))
        cost = a["p"]
        out = {"max_loss": round(cost * 100, 2), "max_profit": round((a["k"] - cost) * 100, 2), "break_even": round(a["k"] - cost, 2)}
    elif structure == "Bull Call Spread":
        lo = round_strike(price, price)
        hi = max(round_strike(price + 0.75 * sd, price), lo + strike_step(price))
        a, b = leg("Buy", "call", lo), leg("Sell", "call", hi)
        cost = a["p"] - b["p"]
        out = {"max_loss": round(cost * 100, 2), "max_profit": round((hi - lo - cost) * 100, 2), "break_even": round(lo + cost, 2)}
    elif structure == "Bear Put Spread":
        hi = round_strike(price, price)
        lo = min(round_strike(price - 0.75 * sd, price), hi - strike_step(price))
        a, b = leg("Buy", "put", hi), leg("Sell", "put", lo)
        cost = a["p"] - b["p"]
        out = {"max_loss": round(cost * 100, 2), "max_profit": round((hi - lo - cost) * 100, 2), "break_even": round(hi - cost, 2)}
    elif structure == "Iron Condor":
        step = strike_step(price)
        sp = round_strike(price - 0.75 * sd, price)
        sc = round_strike(price + 0.75 * sd, price)
        lp = min(round_strike(price - 1.25 * sd, price), sp - step)
        lc = max(round_strike(price + 1.25 * sd, price), sc + step)
        a, b = leg("Buy", "put", lp), leg("Sell", "put", sp)
        c, d = leg("Sell", "call", sc), leg("Buy", "call", lc)
        credit = b["p"] + c["p"] - a["p"] - d["p"]
        cost = -credit
        width = max(sp - lp, lc - sc)
        out = {"max_loss": round((width - credit) * 100, 2), "max_profit": round(credit * 100, 2),
               "break_even": f"{round(sp - credit, 2)} / {round(sc + credit, 2)}"}
    else:
        raise ValueError(f"unknown structure {structure}")

    return {"type": structure, "expiration": exp.isoformat(), "trade_legs": legs,
            "net_cost": round(cost, 2), "estimated": True, "vol": round(vol, 4), **out}


def structure_return(trade: dict, entry_price: float, exit_price: float, entry: date, at: date, vol: float) -> Optional[float]:
    """
    Return on capital at risk if the structure were held from `entry` to `at`
    and the underlying moved entry_price -> exit_price. Options are marked with
    Black-Scholes at the remaining time (intrinsic at/after expiry).
    """
    st = trade.get("type")
    if st == "Buy Stock":
        return exit_price / entry_price - 1.0
    if st == "Sell / Avoid":
        return 0.0
    legs = [l for l in trade.get("trade_legs", []) if l.get("instrument") == "option"]
    if not legs:
        return None
    exp = date.fromisoformat(legs[0]["expiration"])
    t_entry = max((exp - entry).days, 1) / 365.0
    t_now = max((exp - at).days, 0) / 365.0
    v0 = v1 = 0.0
    for l in legs:
        sign = 1.0 if l["action"] == "Buy" else -1.0
        kind = l["option_type"].lower()
        v0 += sign * bs_price(entry_price, l["strike_price"], t_entry, vol, kind)
        v1 += sign * bs_price(exit_price, l["strike_price"], t_now, vol, kind)
    pnl = v1 - v0
    if st == "Iron Condor":
        strikes = sorted(l["strike_price"] for l in legs)
        width = max(strikes[1] - strikes[0], strikes[3] - strikes[2])
        risk = max(width + v0, 0.01)  # v0 is negative (credit)
    else:
        risk = max(abs(v0), 0.01)
    return max(-1.0, pnl / risk)
