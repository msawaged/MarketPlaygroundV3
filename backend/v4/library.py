"""
The strategy library: every structure MarketPlayground can suggest, what it's for, who it's for,
how its legs are built, and its economics (computed from the payoff, not hand formulas).

How a strategy gets chosen for a pick (see engine.pick_structure):
  1. The person's preferences narrow the list: shares vs options vs "let the AI pick", and for
     options what matters most (biggest upside / limit my risk / earn income / protect what I own).
  2. Claude proposes the best fit from that list for each company, with a one-line reason.
  3. If Claude's choice isn't allowed for that direction + risk level + preferences, the rules pick.
  4. Over time the shared track record can swap in a structure that has clearly done better.

Not included on purpose: naked short calls/straddles (unlimited risk), calendars/diagonals (two
expirations; needs a different pricing model), ratio spreads (hard to explain, easy to misuse).
"""
from __future__ import annotations

import math
from typing import Optional

GOALS = ("upside", "limited", "income", "protect")

# name: family, directions it fits, risk levels allowed, goals it serves, options approval level, needs
LIB: dict[str, dict] = {
    "Buy Stock":          {"family": "shares",  "dirs": {"bullish"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"upside", "limited"}, "level": 0},
    "Sell / Avoid":       {"family": "shares",  "dirs": {"bearish", "neutral", "volatile"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"limited"}, "level": 0},
    "Long Call":          {"family": "options", "dirs": {"bullish"}, "risks": {"moderate", "aggressive"}, "goals": {"upside"}, "level": 2},
    "Bull Call Spread":   {"family": "options", "dirs": {"bullish"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"limited", "upside"}, "level": 3},
    "Bull Put Spread":    {"family": "options", "dirs": {"bullish"}, "risks": {"moderate", "aggressive"}, "goals": {"income"}, "level": 3},
    "Cash-Secured Put":   {"family": "options", "dirs": {"bullish"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"income"}, "level": 1},
    "Covered Call":       {"family": "options", "dirs": {"bullish", "neutral"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"income"}, "level": 1},
    "Protective Put":     {"family": "options", "dirs": {"bullish", "bearish", "volatile"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"protect"}, "level": 2},
    "Collar":             {"family": "options", "dirs": {"bullish", "neutral", "bearish"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"protect"}, "level": 2},
    "Long Put":           {"family": "options", "dirs": {"bearish"}, "risks": {"moderate", "aggressive"}, "goals": {"upside"}, "level": 2},
    "Bear Put Spread":    {"family": "options", "dirs": {"bearish"}, "risks": {"conservative", "moderate", "aggressive"}, "goals": {"limited", "upside"}, "level": 3},
    "Bear Call Spread":   {"family": "options", "dirs": {"bearish"}, "risks": {"moderate", "aggressive"}, "goals": {"income"}, "level": 3},
    "Iron Condor":        {"family": "options", "dirs": {"neutral"}, "risks": {"moderate", "aggressive"}, "goals": {"income", "limited"}, "level": 3},
    "Iron Butterfly":     {"family": "options", "dirs": {"neutral"}, "risks": {"aggressive"}, "goals": {"income", "upside"}, "level": 3},
    "Long Call Butterfly": {"family": "options", "dirs": {"bullish", "neutral"}, "risks": {"moderate", "aggressive"}, "goals": {"limited", "upside"}, "level": 3, "needs": "target"},
    "Long Straddle":      {"family": "options", "dirs": {"volatile"}, "risks": {"moderate", "aggressive"}, "goals": {"upside", "limited"}, "level": 2},
    "Long Strangle":      {"family": "options", "dirs": {"volatile"}, "risks": {"moderate", "aggressive"}, "goals": {"limited", "upside"}, "level": 2},
}

# Preference order when the person picked a goal (first allowed one wins when Claude's pick doesn't fit)
ORDER = {
    ("bullish", "upside"): ["Long Call", "Bull Call Spread", "Long Call Butterfly"],
    ("bullish", "limited"): ["Bull Call Spread", "Long Call Butterfly", "Buy Stock"],
    ("bullish", "income"): ["Cash-Secured Put", "Covered Call", "Bull Put Spread"],
    ("bullish", "protect"): ["Protective Put", "Collar"],
    ("bearish", "upside"): ["Long Put", "Bear Put Spread"],
    ("bearish", "limited"): ["Bear Put Spread"],
    ("bearish", "income"): ["Bear Call Spread"],
    ("bearish", "protect"): ["Protective Put", "Collar"],
    ("neutral", "upside"): ["Iron Butterfly", "Long Call Butterfly", "Iron Condor"],
    ("neutral", "limited"): ["Iron Condor", "Long Call Butterfly"],
    ("neutral", "income"): ["Iron Condor", "Covered Call", "Iron Butterfly"],
    ("neutral", "protect"): ["Collar"],
    ("volatile", "upside"): ["Long Straddle", "Long Strangle"],
    ("volatile", "limited"): ["Long Strangle", "Long Straddle"],
    ("volatile", "income"): ["Long Strangle"],
    ("volatile", "protect"): ["Protective Put"],
}

PLAIN = {
    "Buy Stock": "Own the shares (or fund). Simple: you gain if it rises.",
    "Sell / Avoid": "No trade: stay out, or trim if you already own it.",
    "Long Call": "Buy the right to purchase 100 shares at a set price. Big upside if it rises; you can lose the whole cost.",
    "Bull Call Spread": "Buy a call and sell a higher one. Gains if it rises, with both gain and loss capped.",
    "Bull Put Spread": "Sell a put and buy a lower one. Collect cash now; keep it if the stock stays above your strike.",
    "Cash-Secured Put": "Get paid to agree to buy the stock lower. Keep the cash if it stays up; buy at a discount if it dips.",
    "Covered Call": "Own 100 shares and sell a call above. Earn extra income; give up gains above the strike.",
    "Protective Put": "Own 100 shares and buy a put as insurance. Your loss has a floor; your upside stays open.",
    "Collar": "Own 100 shares, buy a put below and sell a call above. A cheap floor, paid for by capping the upside.",
    "Long Put": "Buy the right to sell 100 shares at a set price. Gains if it falls; you can lose the whole cost.",
    "Bear Put Spread": "Buy a put and sell a lower one. Gains if it falls, with both gain and loss capped.",
    "Bear Call Spread": "Sell a call and buy a higher one. Collect cash now; keep it if the stock stays below your strike.",
    "Iron Condor": "Collect cash betting the price stays in a range. Small capped gain, larger capped loss.",
    "Iron Butterfly": "Collect more cash betting the price ends right near today's. Bigger payout, narrower target.",
    "Long Call Butterfly": "A cheap bet that the stock lands near one target price on expiration day.",
    "Long Straddle": "Buy a call and a put at the same price. Win on a big move either way; lose if it barely moves.",
    "Long Strangle": "Buy a call above and a put below. Cheaper than a straddle; needs a bigger move either way.",
}


def allowed(direction: str, risk: str, instrument: str = "auto", goal: str = "", target_price: float = 0.0) -> list[str]:
    """Every structure that fits, best-first when a goal is given."""
    risk = risk if risk in ("conservative", "moderate", "aggressive") else "moderate"
    names = [n for n, m in LIB.items() if direction in m["dirs"] and risk in m["risks"]]
    if instrument == "shares":
        names = [n for n in names if LIB[n]["family"] == "shares"]
    elif instrument == "options":
        names = [n for n in names if LIB[n]["family"] == "options"] or names
    if not target_price:
        names = [n for n in names if LIB[n].get("needs") != "target"]
    if goal in GOALS:
        pref = [n for n in ORDER.get((direction, goal), []) if n in names]
        if pref:
            return pref
    return names


# ---------------- legs + economics ----------------

def stock_leg(ticker: str, price: float, shares: int = 100) -> dict:
    return {"action": "Buy", "ticker": ticker, "quantity": shares, "instrument": "stock", "price": round(price, 2)}


def payoff_at_expiry(legs: list[dict], s: float, entry: float) -> float:
    """$ P&L of one unit at expiration if the stock ends at s (options x100, stock legs in shares)."""
    v = 0.0
    for l in legs:
        if l.get("instrument") == "stock":
            v += l.get("quantity", 100) * (s - entry)
        else:
            sign = 1.0 if l["action"] == "Buy" else -1.0
            k = l["strike_price"]
            intrinsic = max(0.0, s - k) if l["option_type"].lower() == "call" else max(0.0, k - s)
            v += sign * l.get("quantity", 1) * (intrinsic - l["est_premium"]) * 100
    return v


def economics(legs: list[dict], price: float) -> dict:
    """Max profit / max loss / breakevens / capital at risk, read off the payoff.

    The payoff at expiry is piecewise linear with kinks only at strikes, so it is evaluated exactly at
    0, every strike and a far point (3x price): peaks and troughs sit on strikes (a straddle's max loss, a
    butterfly's max gain), and breakevens are solved exactly on each straight segment. 2026-11-13: replaced a
    2,400-point grid that stepped over the strikes and misstated those numbers by up to ~1%."""
    ks = sorted({float(l["strike_price"]) for l in legs if l.get("instrument") != "stock" and l.get("strike_price")})
    hi = max([price * 3] + [k * 1.5 for k in ks])
    xs = sorted({0.0, hi, *ks})
    ys = [payoff_at_expiry(legs, x, price) for x in xs]
    bes = []
    for i in range(1, len(xs)):
        y0, y1 = ys[i - 1], ys[i]
        if (y0 < 0) != (y1 < 0) and y1 != y0:
            t = y0 / (y0 - y1)
            bes.append(round(xs[i - 1] + t * (xs[i] - xs[i - 1]), 2))
    slope_far = payoff_at_expiry(legs, hi + 1.0, price) - ys[-1]
    unlimited = slope_far > 1e-6
    max_profit = "Unlimited" if unlimited else round(max(ys), 2)
    max_loss = round(-min(ys), 2)
    stock_cost = sum(l.get("quantity", 100) * price for l in legs if l.get("instrument") == "stock")
    net_prem = sum((1 if l["action"] == "Buy" else -1) * l.get("quantity", 1) * l["est_premium"]
                   for l in legs if l.get("instrument") != "stock")
    capital = stock_cost + net_prem * 100 if stock_cost else max_loss
    return {"max_profit": max_profit, "max_loss": max_loss, "break_even": " / ".join(str(b) for b in bes) if bes else None,
            "capital": round(max(capital, 1.0), 2), "net_cost": round(net_prem, 2)}


def _k(x: float) -> str:
    return f"${x:,.0f}" if float(x).is_integer() else f"${x:,.2f}"


def exercise_notes(legs: list[dict], ticker: str = "") -> list[str]:
    """Plain-words notes on what the expiry payoff leaves out (2026-11-14, expert-review checklist).

    US stock and ETF options are American-style: a long option can be exercised, and a short one assigned, any day
    up to expiration. The card's chart is the value AT expiration and the prices are Black-Scholes with no
    dividends, so we say what that means for each short leg (early assignment, ex-dividend calls, deep in-the-money
    puts), pin risk at a short strike on the last day, and automatic exercise of in-the-money longs. [] when there
    are no option legs. Reporting only: pricing and grading are unchanged."""
    opts = [l for l in legs if l.get("instrument") != "stock" and l.get("strike_price")]
    if not opts:
        return []
    t = ticker or (opts[0].get("ticker") or "the stock")
    shares = sum(int(l.get("quantity", 100)) for l in legs if l.get("instrument") == "stock")
    kind = lambda l: str(l.get("option_type", "")).lower()
    longs = [l for l in opts if l.get("action") == "Buy"]
    shorts = [l for l in opts if l.get("action") != "Buy"]
    notes = ["These are American-style options: they can be exercised any day before expiration, not only at the end. "
             "Max loss, max gain and the scenarios are values at expiration; before then the trade is worth whatever it sells for. "
             "Prices here assume no dividends, so if " + t + " pays one before expiration, calls read a little high "
             "and puts a little low."]
    for l in sorted(shorts, key=lambda x: float(x["strike_price"])):
        k = float(l["strike_price"]); q = int(l.get("quantity", 1))
        n = f"{q * 100} shares" if q > 1 else "100 shares"
        if kind(l) == "call":
            lo = [x for x in longs if kind(x) == "call" and float(x["strike_price"]) < k]
            hi = [x for x in longs if kind(x) == "call" and float(x["strike_price"]) > k]
            cover = (" Your shares cover it." if shares >= 100 * q else
                     " Your higher call still caps the loss, but you'd be short the shares until you buy them back or exercise it." if hi else
                     f" Your {_k(float(lo[0]['strike_price']))} call covers it: exercising it delivers the shares." if lo else "")
            notes.append(f"You're selling the {_k(k)} call. Once it's in the money, its buyer can exercise it early, most "
                         f"often the day before an ex-dividend date. You'd then sell {n} at {_k(k)}.{cover}")
        else:
            lo = [x for x in longs if kind(x) == "put" and float(x["strike_price"]) < k]
            hi = [x for x in longs if kind(x) == "put" and float(x["strike_price"]) > k]
            cover = (" Your lower put still caps the loss, but you'd own the shares until you sell them or exercise it." if lo else
                     f" Your {_k(float(hi[0]['strike_price']))} put covers it: exercising it sells the shares." if hi else
                     " The cash set aside covers it." if len(opts) == 1 else "")
            notes.append(f"You're selling the {_k(k)} put. If it goes deep in the money, its buyer can exercise it early. "
                         f"You'd then buy {n} at {_k(k)}.{cover}")
    if shorts:
        ks = sorted({float(l["strike_price"]) for l in shorts})
        notes.append(f"Pin risk: if {t} closes very near {' or '.join(_k(k) for k in ks)} on the last day, you may not "
                     "know until the next morning whether you were assigned. Closing the trade before expiration day avoids it.")
    if longs:
        notes.append("Options you own that finish at least $0.01 in the money are exercised automatically at expiration, "
                     "which turns them into shares unless you sell them first.")
    return notes


def build(structure: str, ticker: str, price: float, sd: float, k_round, step: float, leg, target_price: float = 0.0) -> list[dict]:
    """Legs for the library-only structures. `leg(action, kind, strike, qty=1)` adds an option leg."""
    atm = k_round(price)
    w = max(step, k_round(price + 0.5 * sd) - atm)
    if structure == "Bull Put Spread":
        k1 = min(k_round(price - 0.25 * sd), atm - step)
        leg("Sell", "put", k1); leg("Buy", "put", k1 - w)
    elif structure == "Bear Call Spread":
        k1 = max(k_round(price + 0.25 * sd), atm + step)
        leg("Sell", "call", k1); leg("Buy", "call", k1 + w)
    elif structure == "Iron Butterfly":
        wing = max(step, k_round(price + sd) - atm)
        leg("Buy", "put", atm - wing); leg("Sell", "put", atm); leg("Sell", "call", atm); leg("Buy", "call", atm + wing)
    elif structure == "Long Call Butterfly":
        center = k_round(target_price) if target_price else k_round(price + 0.5 * sd)
        leg("Buy", "call", center - w); leg("Sell", "call", center, 2); leg("Buy", "call", center + w)
    elif structure == "Cash-Secured Put":
        leg("Sell", "put", min(k_round(price - 0.5 * sd), atm - step))
    elif structure == "Covered Call":
        leg("Sell", "call", max(k_round(price + 0.5 * sd), atm + step))
    elif structure == "Protective Put":
        leg("Buy", "put", min(k_round(price - 0.5 * sd), atm - step))
    elif structure == "Collar":
        leg("Buy", "put", min(k_round(price - 0.5 * sd), atm - step))
        leg("Sell", "call", max(k_round(price + 0.5 * sd), atm + step))
    else:
        raise ValueError(f"unknown structure {structure}")
    return []


HAS_STOCK = {"Covered Call", "Protective Put", "Collar"}
