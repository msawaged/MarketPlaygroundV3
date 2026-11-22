"""
Close Call (Yes / No, 2026-11-12): "Will NVDA close above $150 on Fri Nov 21?" answered with real option prices.

A Nadex-style question without Nadex. Three numbers, in this order:
  1. The market's odds: the chance option prices imply that the stock finishes above the line on that expiration
     (Black-Scholes N(d2) with the implied volatility of the listed strike nearest the line). Over days or weeks the
     market's (risk-neutral) odds and real-world odds are very close, so we show it as plain odds.
  2. The brain's lean: the market's odds nudged by what the brain knows (the stock's MuLine trend and which way the
     app's recent ideas on it point). The nudge is small and capped (at most about 7 points), because the brain is
     proven on 90-day calls, not on one-week ones. Every lean is logged and graded so that changes with evidence.
  3. The trade: YES = a call spread on the listed strikes either side of the line (buy the lower, sell the upper),
     centred on it so its price matches the market's odds; NO = the matching put spread (buy the upper, sell the
     lower). Fixed cost, fixed most-you-can-make, like a Nadex contract. Opened
     with practice money through practice_options, so it shows in Portfolio and settles at expiration like any
     other practice options trade.

Grading: after expiration, a question is right when the stock closed above the line and the answer was YES (or at or
below and the answer was NO). We keep the market's and the brain's odds at the moment of asking, so the scorecard can
say honestly whether the brain's lean beat the market's odds (Brier score: lower is better).

Nothing here touches existing features: own table (yesno_calls), own endpoints, trades via practice_options.open_trade.
"""
from __future__ import annotations

import math
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import db, market

MAX_DAYS = 70           # furthest expiration offered
MAX_TILT = 0.30         # cap on the brain's nudge, in log-odds (about +-7 points near 50%)
W_TREND = 0.15          # MuLine rising / falling
W_IDEAS = 0.12          # balance of the app's recent bullish vs bearish ideas on the stock
IDEA_DAYS = 14
MIN_IDEAS = 3


class YesNoError(Exception):
    pass


# ----------------------------------------------------------------------------- math (pure)

def _mids(calls: list[dict]) -> dict:
    """{strike: mid} for calls with a sensible two-sided quote (tight enough to trust)."""
    q = {}
    for r in calls:
        b, a = float(r.get("bid") or 0), float(r.get("ask") or 0)
        if a > 0 and b >= 0 and a >= b and (a - b) <= max(0.25, 0.5 * a):
            q[float(r["strike"])] = (a + b) / 2
    return q


def spread_vol(calls: list[dict], k1: float, k2: float, spot: float, years: float, near: float) -> Optional[float]:
    """The one volatility at which the model prices the k1/k2 call spread at its listed mid. YES and NO are then
    priced off the market's own price for the spread (skew included), not off one strike's IV, and still add up to
    the payout. Several vols can fit (a spread's value isn't monotone in vol near the money): take the one closest
    to `near` (the line's IV). None if either strike lacks a sensible quote or no vol fits."""
    from .strategy import bs_price
    q = _mids(calls)
    if k1 not in q or k2 not in q or years <= 0:
        return None
    target = q[k1] - q[k2]
    if not (0.0 < target < k2 - k1):
        return None
    f = lambda v: bs_price(spot, k1, years, v, "call") - bs_price(spot, k2, years, v, "call") - target
    grid = [0.05 + i * 0.025 for i in range(59)]          # 0.05 .. 1.50
    roots = []
    for a, b in zip(grid, grid[1:]):
        fa, fb = f(a), f(b)
        if fa == 0:
            roots.append(a)
        elif fa * fb < 0:
            for _ in range(40):
                m = (a + b) / 2
                if f(a) * f(m) <= 0:
                    b = m
                else:
                    a = m
            roots.append((a + b) / 2)
    if not roots:
        return None
    return min(roots, key=lambda v: abs(v - near))


def strike_vol(mid: float, spot: float, k: float, years: float, kind: str = "call") -> Optional[float]:
    """The implied volatility at which one option prices at its listed mid (an option's price rises with vol,
    so bisection finds the one answer). None if the mid sits outside what any vol from 2% to 200% can give."""
    from .strategy import bs_price
    lo, hi = 0.02, 2.0
    if years <= 0 or mid <= 0 or not (bs_price(spot, k, years, lo, kind) <= mid <= bs_price(spot, k, years, hi, kind)):
        return None
    for _ in range(60):
        m = (lo + hi) / 2
        if bs_price(spot, k, years, m, kind) < mid:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def quote_iv(row: dict, spot: float, years: float) -> Optional[float]:
    """One listed option's implied volatility from its own two-sided quote (mid), on the quote clock
    (market.quote_years). None without a usable bid AND ask (callers fall back to the feed's number)."""
    bid, ask = float(row.get("bid") or 0), float(row.get("ask") or 0)
    if bid <= 0 or ask < bid or spot <= 0 or years <= 0:
        return None
    mid = (bid + ask) / 2
    if (ask - bid) > 0.5 * mid:          # too loose to read a volatility off
        return None
    return strike_vol(mid, spot, row["strike"], years, row["type"])


def atm_quote_iv(rows: list[dict], spot: float, years: float) -> Optional[tuple[float, float, Optional[float]]]:
    """(at-the-money vol, its strike, put minus call vol) from the call and put quotes at the listed strike nearest
    the stock price, for ONE expiration's rows. Averaging the call and put cancels most of a dividend's pull.
    None when neither has a readable quote."""
    if not rows or spot <= 0:
        return None
    k = min({r["strike"] for r in rows}, key=lambda s: abs(s - spot))
    by = {r["type"]: quote_iv(r, spot, years) for r in rows if r["strike"] == k}
    ivs = [v for v in by.values() if v]
    if not ivs:
        return None
    c, p = by.get("call"), by.get("put")
    return sum(ivs) / len(ivs), k, (p - c if c and p else None)


def leg_vols(calls: list[dict], k1: float, k2: float, spot: float, years: float, near: float) -> Optional[tuple[float, float]]:
    """Each strike of the YES spread at its own implied volatility, from its listed call mid ("sticky strike").
    One flat vol can't reprice a skewed spread: the skew sits in how IV changes from k1 to k2, and a vertical
    spread's flat-vol value barely moves with vol (live AAPL $360/$365, Dec 18: $204 at the line IV, at most
    ~$212 at any vol, while the market's odds of 50% imply ~$230). Per-strike vols put YES at the listed
    spread mid, and the put spread at the same two vols keeps YES + NO = the discounted payout (put-call parity).
    None if a quote is missing, the spread is nonsense, or a vol is more than 20% off the line IV (thin or stale
    quotes, same guard as spread_vol)."""
    q = _mids(calls)
    if k1 not in q or k2 not in q or not (0.0 < q[k1] - q[k2] < k2 - k1) or not near:
        return None
    v1, v2 = strike_vol(q[k1], spot, k1, years), strike_vol(q[k2], spot, k2, years)
    if v1 is None or v2 is None or any(abs(v / near - 1) > 0.2 for v in (v1, v2)):
        return None
    return round(v1, 4), round(v2, 4)


def parity_forward(chain: list[dict], strikes, years: float) -> Optional[tuple[float, float]]:
    """The stock price the option quotes themselves imply, by put-call parity: C(K) - P(K) = (F - K) * exp(-r * years),
    so F = K + (C - P) * exp(r * years), averaged over the given strikes that have a tight call AND put quote.
    Returns (F, mid noise) where the noise is half the call and put bid/ask gaps (how far mids can sit from fair),
    or None if no strike has both. A desk reads this before trusting a call spread: if the quotes' F is far from the
    stock's last price, the quotes were set when the stock traded elsewhere (e.g. a late print in the stock after the
    options stopped quoting). Checked live Sat Nov 21: SPY $693.89 and its Nov 27 quotes gave F = $693.5-693.9 at
    $695-$710, so they agreed; SPY's "50% above $700" there is real skew (a digital call is N(d2) - vega * dsigma/dK,
    and equity skew has dsigma/dK < 0, so it sits ABOVE the one-vol 43%), not stale quotes."""
    from .strategy import RISK_FREE
    grow = math.exp(RISK_FREE * max(0.0, years))
    calls = _mids([r for r in chain if r["type"] == "call"])
    puts = _mids([r for r in chain if r["type"] == "put"])
    gaps = {(r["type"], float(r["strike"])): float(r.get("ask") or 0) - float(r.get("bid") or 0) for r in chain}
    fs, noise = [], []
    for k in strikes:
        k = float(k)
        if k in calls and k in puts:
            fs.append(k + (calls[k] - puts[k]) * grow)
            noise.append(0.5 * (gaps.get(("call", k), 0) + gaps.get(("put", k), 0)) * grow)
    if not fs:
        return None
    return sum(fs) / len(fs), sum(noise) / len(noise)


def quotes_own_price(chain: list[dict], spot: float, level: float, years: float,
                     strikes=None) -> Optional[dict]:
    """The stock price the option quotes near the line were set at (put-call parity, parity_forward), the volatility
    they price once read at THAT price (where calls and puts agree), and whether that price is too far from the last
    price for the quotes to be read against it ("out").

    Why the volatility has to be read at the quotes' own price: read at the last price instead, quotes set while the
    stock traded lower make every put look dear and every call cheap. Live Sun Nov 22, NVDA $129.17, Dec 4: the
    quotes implied ~$126.1 (calls ~0.81 vol beside puts ~1.19 at the same strikes); read at $126 both say ~1.03. The
    old allowance (0.1 sd of the move, on the puts' inflated 1.19) grew with the very gap it measured and let the
    quotes through, so the smile, all puts there, read "46% to close above $125" with the stock $4 above it.

    The bar: 0.1 sd of the move at the quotes' own vol (about 4 points of odds at the money) plus the quotes' mid
    noise. No dividend room here: callers that allow for a dividend (quotes_out_of_step) keep doing so.
    strikes: which strikes to read (default: those within SKEW_BAND of the line). None without a strike quoted on both
    sides."""
    from .strategy import RISK_FREE
    if spot <= 0 or level <= 0 or years <= 0:
        return None
    calls = _mids([r for r in chain if r["type"] == "call"])
    puts = _mids([r for r in chain if r["type"] == "put"])
    both = sorted(k for k in calls if k in puts)
    if strikes is None:
        strikes = [k for k in both if abs(k - level) <= SKEW_BAND * level]
    pf = parity_forward(chain, strikes, years)
    if not pf or pf[0] <= 0:
        return None
    # Quotes from one moment give every strike the same parity price (to within their noise); junk quotes (the same
    # price at every strike) give each strike its own, which is no stock price at all.
    grow = math.exp(RISK_FREE * years)
    each = [float(k) + (calls[float(k)] - puts[float(k)]) * grow for k in strikes if float(k) in calls and float(k) in puts]
    if max(each) - min(each) > 2 * pf[1] + 0.005 * spot:
        return None
    price = pf[0] / grow
    k = min(both, key=lambda x: abs(x - level))
    cv, pv = strike_vol(calls[k], price, k, years, "call"), strike_vol(puts[k], price, k, years, "put")
    # At their own price a call and a put on one strike price one vol; if they still don't, the vol isn't readable.
    vol = (cv + pv) / 2 if cv and pv and abs(cv / pv - 1) <= 0.15 else None
    gap = pf[0] - spot * math.exp(RISK_FREE * years)
    out = bool(vol) and abs(gap) > 0.1 * vol * math.sqrt(years) * spot + pf[1]
    return {"price": price, "vol": vol, "noise": pf[1], "out": out}


def quotes_out_of_step(spot: float, fwd: Optional[tuple[float, float]], vol: float, years: float) -> bool:
    """True when the option quotes' own stock price (parity_forward) is too far from the last price for their odds to
    describe a close relative to it. The bar: a tenth of one standard deviation of the move to expiration (about 4
    points of odds at the money) plus the quotes' own mid noise. A forward BELOW the price gets 2% extra room, since a
    dividend before expiration (or early-exercise value in puts) lowers it legitimately; nothing raises it."""
    if not fwd or spot <= 0 or vol <= 0 or years <= 0:
        return False
    from .strategy import RISK_FREE
    f, noise = fwd
    gap = f - spot * math.exp(RISK_FREE * years)
    band = 0.1 * vol * math.sqrt(years) * spot + noise
    return gap > band or gap < -(band + 0.02 * spot)


def calls_puts_disagree(chain: list[dict], k1: float, k2: float, years: float) -> bool:
    """True when the k1/k2 call spread and the k2/k1 put spread, read off their own mids, add up to clearly more or
    less than the strike gap. Put-call parity makes them sum to (k2 - k1) * exp(-r T) whatever the stock price,
    dividend or volatility (a dividend shifts every strike's parity forward by the same amount, so it cancels), so a
    gap beyond the quotes' own noise means the calls and puts were set at different stock prices: stale quotes.
    Live Sun Nov 22, NVDA $129.17, Nov 27 $127/$133: the call spread's mid $3.06 read "51% to close above $130" and
    the put spread's $3.85 read 64% for NO, $6.91 for a $6 spread. quotes_out_of_step let it through (the quotes'
    stock price, ~$126, sat inside its 2% dividend room). The bar: 5% of the gap or half the four legs' bid/ask
    widths, whichever is bigger."""
    from .strategy import RISK_FREE
    calls = _mids([r for r in chain if r["type"] == "call"])
    puts = _mids([r for r in chain if r["type"] == "put"])
    if not all(k in calls and k in puts for k in (k1, k2)) or k2 <= k1:
        return False
    total = (calls[k1] - calls[k2]) + (puts[k2] - puts[k1])
    gaps = {(r["type"], float(r["strike"])): float(r.get("ask") or 0) - float(r.get("bid") or 0) for r in chain}
    noise = 0.5 * sum(gaps.get((t, k), 0) for t in ("call", "put") for k in (k1, k2))
    return abs(total - (k2 - k1) * math.exp(-RISK_FREE * max(0.0, years))) > max(0.05 * (k2 - k1), noise)


SKEW_BAND = 0.02          # strikes within 2% of the line feed the local skew fit
SKEW_REACH = 0.08         # ... and the two nearest on each side out to 8% where the grid is coarse
MAX_SKEW_TERM = 0.15      # a skew term over 15 points of odds is a bad fit, not skew
MAX_SMILE_MISS = 0.08     # the strikes' vols must sit near one straight line (RMS miss under 8% of the vol)


def skew_odds(chain: list[dict], spot: float, level: float, years: float) -> Optional[dict]:
    """What the option smile near the line says the odds should be, as a check on a spread's reading. Backs an
    implied vol out of each out-of-the-money mid within SKEW_BAND of the line (puts below the forward, calls above:
    the liquid side, the way a desk reads the smile) with our own Black-Scholes, fits a straight line sigma(K) through
    them, and returns the digital with its skew term: P(close > L) = N(d2(sigma_L)) - exp(r T) * vega(L) * dsigma/dK.
    Equity skew (dsigma/dK < 0) lifts the odds above one vol's N(d2). Live Sat Nov 21, SPY $693.89, Nov 27: sigma
    falls ~0.35 vol pts per $1, which lifts the $690 line from 54% to 66%, so the quiet $687/$693 spread's 64% was
    right and the old guard (10 points off the one-vol answer) refused it, leaving $690 at 54.7% under $695's 56.7%.
    Feed IVs aren't used: Alpaca's call and put IVs at one strike disagreed by ~10 vol pts while parity held.
    None when the quotes' own stock price (put-call parity) is over 0.1 sd of the move from the last price, with
    fewer than two usable strikes on either side of the line, vols that don't sit near one straight line
    (RMS miss over MAX_SMILE_MISS of the vol: junk quotes, e.g. every strike at the same price, make a V), or a skew
    term over MAX_SKEW_TERM."""
    from .strategy import RISK_FREE
    if spot <= 0 or level <= 0 or years <= 0:
        return None
    fwd = spot * math.exp(RISK_FREE * years)
    mids = {"call": _mids([r for r in chain if r["type"] == "call"]),
            "put": _mids([r for r in chain if r["type"] == "put"])}
    allv = []
    for k in sorted(set(mids["call"]) | set(mids["put"])):
        if abs(k - level) > SKEW_REACH * level:
            continue
        kind = "put" if k < fwd else "call"
        m = mids[kind].get(k)
        v = strike_vol(m, spot, k, years, kind) if m else None
        if v:
            allv.append((k, v))
    # Every strike within SKEW_BAND, and on a coarse grid (NVDA $5 strikes around $120) at least the two nearest on
    # each side, out to SKEW_REACH.
    lo = [kv for kv in allv if kv[0] <= level][-2:]
    hi = [kv for kv in allv if kv[0] >= level][:2]
    pts = sorted(set(kv for kv in allv if abs(kv[0] - level) <= SKEW_BAND * level) | set(lo) | set(hi))
    if sum(1 for k, _ in pts if k <= level) < 2 or sum(1 for k, _ in pts if k >= level) < 2:
        return None
    mk = sum(k for k, _ in pts) / len(pts)
    mv = sum(v for _, v in pts) / len(pts)
    sxx = sum((k - mk) ** 2 for k, _ in pts)
    if sxx <= 0:
        return None
    slope = sum((k - mk) * (v - mv) for k, v in pts) / sxx
    sig = mv + slope * (level - mk)
    # Puts and calls only describe one smile when they agree on the stock price (put-call parity). Live Sat Nov 21,
    # NVDA $129.17: the quotes implied ~$126.15, so put IVs read ~140% beside ~90% for calls and the "smile" was a
    # step. No dividend allowance here (unlike quotes_out_of_step): a gap that size breaks the fit either way.
    # The allowance is measured at the vol the quotes price at their own stock price (quotes_own_price), not at this
    # fit's: live Sun Nov 22, NVDA Dec 4, the fit ran through puts alone, each inflated by the gap, which widened its
    # own allowance enough to pass and read 46% above $125 with the stock at $129.17.
    pf = parity_forward(chain, [k for k, _ in pts], years)
    own = quotes_own_price(chain, spot, level, years, [k for k, _ in pts]) if pf else None
    band_vol = own["vol"] if own and own["vol"] else sig
    if pf and band_vol > 0 and abs(pf[0] - fwd) > 0.1 * band_vol * math.sqrt(years) * spot + pf[1]:
        return None
    rms = math.sqrt(sum((v - mv - slope * (k - mk)) ** 2 for k, v in pts) / len(pts))
    if sig <= 0 or rms > MAX_SMILE_MISS * sig:
        return None
    sq = sig * math.sqrt(years)
    d1 = (math.log(spot / level) + (RISK_FREE + 0.5 * sig * sig) * years) / sq
    flat = _ncdf(d1 - sq)
    vega = spot * math.sqrt(years) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    term = -math.exp(RISK_FREE * years) * vega * slope
    if abs(term) > MAX_SKEW_TERM:
        return None
    return {"p": min(0.99, max(0.01, flat + term)), "flat": flat, "vol": sig, "slope": slope, "n": len(pts),
            "miss": rms}


def digital_from_spread(calls: list[dict], level: float, years: float = 0.0,
                        why: Optional[list] = None) -> Optional[tuple[float, float, float, list]]:
    """Market-implied P(close > level) from listed call prices. A call spread (C(Ka) - C(Kb)) / (Kb - Ka) is the
    chance of finishing above the middle of its two strikes, (Ka + Kb) / 2, not above any line between them. So take
    the two neighbouring strike pairs whose middles sit either side of the line and read the chance at the line
    itself, in a straight line between them (for evenly spaced strikes around a listed line this is the usual
    (C(K - w) - C(K + w)) / 2w). With $149 / $150 / $152.5 listed, the $149/$152.5 spread alone measures a close above
    $150.75, not $150. If only one pair is quoted near the line, that pair is used as before.
    Uses quoted mids, so the volatility skew is already in the price (a single-vol N(d2) ignores the
    -vega * dsigma/dK term a digital carries). A spread pays at expiration, so its price is the discounted chance:
    divide by exp(-r * years) (r = the same rate the option prices use). Returns (p, lowest strike used, highest
    strike used, all strikes used), or None if quotes are missing or don't make sense. The chance of closing above
    can't rise with the strike, so when the left pair reads lower than the right one the quotes are out of step
    (seen after hours: NVDA $159.45, $152.50/$155 at 40% but $155/$157.50 at 52%, read as "46% above $155"); then
    None, and "inverted" is added to `why` if a list is passed."""
    from .strategy import RISK_FREE
    q = _mids(calls)
    ks = sorted(q)
    below = [k for k in ks if k < level - 1e-9]
    above = [k for k in ks if k > level + 1e-9]
    if not below or not above:
        return None
    grow = math.exp(RISK_FREE * max(0.0, years))
    cap = 0.12 * level                                   # too wide to say anything precise about one line

    def pair(ka, kb):
        if not (0 < kb - ka <= cap):
            return None
        p = (q[ka] - q[kb]) / (kb - ka) * grow
        return p if 0.0 < p < 1.0 else None

    ka, kb = below[-1], above[0]
    at = [k for k in ks if abs(k - level) <= 1e-9]
    # Neighbouring pairs: left middle at or below the line, right middle at or above it.
    if at:                                               # a listed line: (Ka, K) and (K, Kb)
        left, right = (ka, at[0]), (at[0], kb)
    else:
        mid = (ka + kb) / 2
        if abs(mid - level) <= 1e-9:
            left = right = (ka, kb)
        elif level < mid:
            left, right = ((below[-2], ka) if len(below) > 1 else None), (ka, kb)
        else:
            left, right = (ka, kb), ((kb, above[1]) if len(above) > 1 else None)
    pl = pair(*left) if left else None
    pr = pair(*right) if right else None
    if pl is not None and pr is not None and left != right:
        if pl + 0.02 < pr:                               # 2 points of slack for bid/ask rounding
            if why is not None:
                why.append("inverted")
            return None
        ml, mr = sum(left) / 2, sum(right) / 2
        p = pl + (pr - pl) * (level - ml) / (mr - ml)
        used = sorted(set(left) | set(right))
    else:                                                # one pair only: the tight spread around the line
        if at:
            p = pair(ka, kb)
            used = [ka, kb]
        else:
            p = pr if right == (ka, kb) else pl
            used = [ka, kb]
    if p is None or not (0.0 < p < 1.0):
        return None
    return min(0.99, max(0.01, p)), used[0], used[-1], used


def odds_label(used: list, level: float) -> str:
    """Where the market's odds came from, in the words shown under them."""
    ks = "/".join(_money(k) for k in used)
    if len(used) == 2:                                   # one spread (its middle is what it measures)
        return f"the {ks} call spread (skew included)"
    return f"the {ks} call prices, read at the {_money(level)} line (skew included)"


def _money(x: float) -> str:
    """$190 for whole dollars, $187.50 otherwise (not "$187.5")."""
    return f"${x:,.0f}" if float(x).is_integer() else f"${x:,.2f}"


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def prob_above(spot: float, level: float, years: float, vol: float, rate: float = 0.038) -> float:
    """Chance the stock finishes above `level` (risk-neutral N(d2))."""
    if spot <= 0 or level <= 0:
        return 0.5
    if years <= 0 or vol <= 0:
        return 1.0 if spot > level else 0.0
    sq = vol * math.sqrt(years)
    d2 = (math.log(spot / level) + (rate - 0.5 * vol * vol) * years) / sq
    return min(0.995, max(0.005, _ncdf(d2)))


def expected_move(spot: float, rows: list[dict], years: float, rv60: Optional[float] = None,
                  quote_years: Optional[float] = None) -> Optional[dict]:
    """The range option prices put about a 2-in-3 chance on by the expiration (one standard deviation), from the
    at-the-money implied volatility of that one expiration, and whether that's a bigger move than the stock has been
    making (implied vs its last 60 trading days of realized volatility; same 1.35x line as Price Check).

    Information only: it doesn't feed the odds, the lean or any grade.

    quote_years (market.quote_years): the vol is read off the at-the-money quotes themselves on the quote clock, so
    a weekend doesn't inflate it (Friday's quotes still price Friday-to-expiration risk); the range uses the same
    clock, so it is the spread those prices carry. Without it, or without readable quotes, the feed's IV and `years`."""
    if spot <= 0 or years <= 0:
        return None
    own = atm_quote_iv(rows, spot, quote_years) if quote_years and quote_years > 0 else None
    if own and abs(own[1] / spot - 1) <= 0.03:
        iv, k = own[0], own[1]
        sd = iv * math.sqrt(quote_years)
    else:
        rows = [r for r in rows if r.get("iv")]
        if not rows:
            return None
        k = min({r["strike"] for r in rows}, key=lambda s: abs(s - spot))
        if abs(k / spot - 1) > 0.03:        # no strike near today's price in this slice of the chain
            return None
        ivs = [r["iv"] for r in rows if r["strike"] == k]
        iv = sum(ivs) / len(ivs)
        sd = iv * math.sqrt(years)
    lo, hi = spot * math.exp(-sd), spot * math.exp(sd)
    ratio = iv / rv60 if rv60 else None
    return {"atm_iv": round(iv, 4), "atm_strike": k, "low": round(lo, 2), "high": round(hi, 2),
            "pct": round((hi - lo) / (2 * spot), 4), "rv60": round(rv60, 4) if rv60 else None,
            "iv_rv": round(ratio, 2) if ratio else None, "big": bool(ratio and ratio > 1.35)}


# A stock's options priced well above its own recent moves usually means news is due (earnings), unless the whole
# market's options are priced the same way (live Nov 21 2026, a selloff: SPY 2.2x, AAPL 1.6x, MSFT 1.7x, NVDA 2.4x,
# and the card told each of them "news is due, like an earnings report" with no earnings for months). A stock counts
# as standing out from the market when its ratio is over STAND_OUT times SPY's.
STAND_OUT = 1.5
_MKT: dict = {}


def market_iv_rv(exp: date, years: float) -> Optional[float]:
    """SPY's implied-vs-realized ratio for the same expiration (the expected_move test), cached 15 minutes.
    None when SPY lists nothing that day or the feed fails: the card then keeps its usual wording."""
    key = exp.isoformat()
    hit = _MKT.get(key)
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    r = None
    try:
        spot = float(market.latest_price("SPY"))
        chain = [x for x in _chain("SPY", spot, exp) if x["expiration"] == exp]
        _, closes = market.daily_closes("SPY")
        rv = market.realized_vol(closes, len(closes) - 1, 60) if len(closes) > 65 else None
        m = expected_move(spot, chain, years, rv, market.quote_years(exp))
        r = m["iv_rv"] if m else None
    except Exception:
        r = None
    _MKT[key] = (time.time(), r)
    return r


def move_text(u: str, m: dict, exp: date, is_etf: bool = False) -> list[str]:
    day = f"{exp.strftime('%a %b')} {exp.day}"
    pct = m["pct"] * 100
    pct_s = f"{pct:.1f}" if pct < 10 else f"{pct:.0f}"
    out = [f"Option prices put about a 2-in-3 chance on {u} closing between {_money(m['low'])} and {_money(m['high'])} "
           f"on {day} (about \u00b1{pct_s}% from today)."]
    if m["big"]:
        head = (f"That's a bigger move than usual: these options are priced for {m['atm_iv'] * 100:.0f}% yearly "
                f"volatility, while {u} actually moved {m['rv60'] * 100:.0f}% a year over the last 60 trading days "
                f"({m['iv_rv']:.1f}x). ")
        mk = m.get("market_iv_rv")
        news = "like a Fed decision or a big economic report" if is_etf else "like an earnings report"
        if u == "SPY":
            out.append(head + f"Often that means news is due before {day}, {news}, or that the market is nervous.")
        elif mk and mk > 1.35 and m["iv_rv"] <= STAND_OUT * mk:
            out.append(head + f"Options across the whole market are priced that way right now (the S&P 500's at "
                              f"{mk:.1f}x), so it's market-wide nervousness more than news about {u}.")
        elif mk and mk > 1.35:
            out.append(head + f"That's more than the whole market's (the S&P 500's options are at {mk:.1f}x), so "
                              f"news may be due before {day}, {news}.")
        else:
            out.append(head + f"Often that means news is due before {day}, {news}.")
    return out


def _logit(p: float) -> float:
    p = min(0.995, max(0.005, p))
    return math.log(p / (1 - p))


def _sig(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def lean(market_p: float, trend_dir: float, idea_balance: Optional[float]) -> tuple[float, float]:
    """(brain's odds, tilt in log-odds). trend_dir: +1 / -1 / 0. idea_balance: -1..+1 or None."""
    tilt = W_TREND * max(-1.0, min(1.0, trend_dir or 0.0))
    if idea_balance is not None:
        tilt += W_IDEAS * max(-1.0, min(1.0, idea_balance))
    tilt = max(-MAX_TILT, min(MAX_TILT, tilt))
    return min(0.99, max(0.01, _sig(_logit(market_p) + tilt))), tilt


def strikes_around(strikes: list[float], level: float) -> Optional[tuple[float, float]]:
    """The two listed strikes either side of the line, so the spread is centred on it.

    A k1/k2 call spread replicates a bet on a close above the middle of its strikes, (k1 + k2) / 2 (see
    digital_from_spread). When the line is itself a listed strike, the line and the next strike up (the old choice)
    put that middle half a strike gap above the line: NVDA $185 on $2.50 strikes was a $185/$187.50 spread, a bet on
    a close above $186.25, priced at 44% while the screen said the market's odds were 50%, with both breakevens
    above the line. So a line on a strike takes the strikes below and above it ($182.50/$187.50, the same pair the
    odds are read from); a line between two strikes takes those two. Only when the line is the lowest listed strike
    does it fall back to the line and the next one up.

    Strike grids aren't always even: live SPY Nov 27 listed $699, $700 and $705 but nothing from $701 to $704, so
    the nearest strikes either side of $700 were $699/$705, a bet on a close above $702 that cost 41% of its payout
    beside "Market's odds 43%", with both breakevens above the line. So first look for two listed strikes the SAME
    distance either side of the line ($695/$705 there), no wider than twice the nearest pair; only when there is
    none does it take the nearest pair (and the spread note says which close it really bets on)."""
    ks = sorted(set(k for k in strikes if k > 0))
    below = [k for k in ks if k < level - 1e-9]
    above = [k for k in ks if k > level + 1e-9]
    if not above:
        return None
    on = any(abs(k - level) <= 1e-9 for k in ks)
    if not below:
        return (level, above[0]) if on else None
    near = below[-1], above[0]
    cap = 2 * (near[1] - near[0]) + 1e-9
    for k1 in reversed(below):
        if 2 * (level - k1) > cap:
            break
        k2 = next((k for k in above if abs(k - (2 * level - k1)) <= 1e-6), None)
        if k2 is not None:
            return k1, k2
    return near


def spread_noise(calls: list[dict], k1: float, k2: float) -> Optional[float]:
    """How far the k1/k2 call spread's odds can sit from fair because of the quotes alone: half of each leg's
    bid/ask gap, over the strike gap. None if a leg has no two-sided quote."""
    gap = {}
    for r in calls:
        b, a = float(r.get("bid") or 0), float(r.get("ask") or 0)
        if a > 0 and b >= 0 and a >= b:
            gap[float(r["strike"])] = a - b
    if k1 not in gap or k2 not in gap or k2 <= k1:
        return None
    return 0.5 * (gap[k1] + gap[k2]) / (k2 - k1)


MAX_NOISE = 0.03          # a spread whose quotes alone blur its odds by more than 3 points is too fine to read


def quiet_pair(calls: list[dict], level: float, pair: tuple[float, float]) -> tuple[float, float]:
    """The narrowest pair of listed strikes the same distance either side of the line whose quotes read the odds to
    within MAX_NOISE, starting from `pair`. Live Sat Nov 21, SPY Nov 27 on $1 strikes: $694/$696 quoted
    $13.68/$13.85 and $12.38/$12.56, so one $1 step read anywhere from 17% to 78% and the $695 line fell back to the
    one-vol 48% beside a skew-included 50% for $700 (odds rising with the line). $690/$700 reads it to ~1.5 points.
    Stays within 4% of the line either way; keeps `pair` when it is already quiet or nothing wider is."""
    n = spread_noise(calls, *pair)
    if n is not None and n <= MAX_NOISE:
        return pair
    ks = sorted({float(r["strike"]) for r in calls})
    have = set(ks)
    for k1 in reversed([k for k in ks if k < pair[0] - 1e-9 and level - k <= 0.04 * level]):
        k2 = round(2 * level - k1, 6)
        k2 = next((k for k in have if abs(k - k2) <= 1e-6), None)
        if k2 is None:
            continue
        n = spread_noise(calls, k1, k2)
        if n is not None and n <= MAX_NOISE:
            return k1, k2
    return pair


def brier(p: float, happened: bool) -> float:
    return (p - (1.0 if happened else 0.0)) ** 2


# ----------------------------------------------------------------------------- data

def _today() -> date:
    return market.today()


def _chain(u: str, level: float, exp: date) -> list[dict]:
    return market.option_chain_near(u, level, exp, days=3, band=0.12)


def expirations(ticker: str) -> dict:
    """Listed expirations in the next ~10 weeks, the live price and a few suggested lines."""
    u = (ticker or "").upper().strip()
    if not u or not market.asset_info(u):
        raise YesNoError("That isn't a stock we can ask about.")
    spot = float(market.latest_price(u))
    t = _today()
    chain = market.option_chain_near(u, spot, t + timedelta(days=MAX_DAYS // 2), days=MAX_DAYS // 2 + 1, band=0.03)
    exps = sorted({r["expiration"] for r in chain if t < r["expiration"] <= t + timedelta(days=MAX_DAYS)})
    if not exps:
        raise YesNoError(f"We couldn't load options on {u} expiring in the next few weeks. The quote feed may be busy: "
                         "try again in a minute. (Not every company has listed options.)")
    step = _nice_step(spot)
    base = round(spot / step) * step
    lines = sorted({round(base + i * step, 2) for i in (-2, -1, 0, 1, 2)})
    return {"ticker": u, "spot": spot, "expirations": [e.isoformat() for e in exps[:8]], "lines": lines}


def _nice_step(spot: float) -> float:
    for lim, s in ((25, 1.0), (60, 2.5), (200, 5.0), (500, 10.0), (1500, 25.0)):
        if spot < lim:
            return s
    return 50.0


def _signals(u: str) -> dict:
    out = {"trend": 0.0, "trend_age": None, "ideas": None, "ideas_n": 0, "ideas_bull": 0, "ideas_bear": 0,
           "crowd": None, "crowd_n": 0}
    try:
        ts = market.trend_state(u)
        if ts:
            out["trend"], out["trend_age"] = float(ts["dir"]), int(ts["age"])
    except Exception:
        pass
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=IDEA_DAYS)).isoformat()
        rows = db.query("""SELECT p.direction AS d, COUNT(*) AS n FROM picks p JOIN beliefs b ON b.id = p.belief_id
                           WHERE p.ticker = ? AND b.created_at >= ? AND p.direction IN ('bullish', 'bearish')
                           GROUP BY p.direction""", (u, since))
        bull = sum(int(r["n"]) for r in rows if r["d"] == "bullish")
        bear = sum(int(r["n"]) for r in rows if r["d"] == "bearish")
        out.update(ideas_n=bull + bear, ideas_bull=bull, ideas_bear=bear)
        if bull + bear >= MIN_IDEAS:
            out["ideas"] = (bull - bear) / (bull + bear)
    except Exception:
        pass
    try:  # people's own YES / NO answers on this stock (open questions only, the brain's own excluded)
        rows = db.query("""SELECT side, COUNT(*) AS n FROM yesno_calls WHERE ticker = ? AND graded_at IS NULL
                           AND user_id NOT IN ('brain', 'anonymous') GROUP BY side""", (u,))
        y = sum(int(r["n"]) for r in rows if r["side"] == "yes")
        n = sum(int(r["n"]) for r in rows if r["side"] == "no")
        out["crowd_n"] = y + n
        if y + n >= MIN_IDEAS:
            out["crowd"] = (y - n) / (y + n)
    except Exception:
        pass
    return out


def _reasons(sig: dict, u: str) -> list[str]:
    r = []
    if sig["trend"] > 0:
        r.append(f"{u}'s MuLine trend is rising" + (f" (for {sig['trend_age']} trading day{'' if sig['trend_age'] == 1 else 's'})" if sig.get("trend_age") else "") + ".")
    elif sig["trend"] < 0:
        r.append(f"{u}'s MuLine trend is falling" + (f" (for {sig['trend_age']} trading day{'' if sig['trend_age'] == 1 else 's'})" if sig.get("trend_age") else "") + ".")
    if sig["ideas"] is not None:
        r.append(f"In the past {IDEA_DAYS} days the app suggested {u} {sig['ideas_n']:,} times: {sig['ideas_bull']:,} as a "
                 f"bullish idea, {sig['ideas_bear']:,} as a bearish one.")
    if not r:
        r.append("The brain has no strong read on this stock, so it stays with the market's odds.")
    return r


def quote(ticker: str, level: float, expiration: str) -> dict:
    u = (ticker or "").upper().strip()
    info = market.asset_info(u) if u else None
    if not info:
        raise YesNoError("That isn't a stock we can ask about.")
    try:
        level = float(level)
        exp = date.fromisoformat(str(expiration)[:10])
    except (TypeError, ValueError):
        raise YesNoError("Pick a price and a date.")
    t = _today()
    if not (t < exp <= t + timedelta(days=MAX_DAYS + 5)) or level <= 0:
        raise YesNoError("Pick a date in the next couple of months.")
    spot = float(market.latest_price(u))
    if not (0.5 * spot <= level <= 1.5 * spot):
        raise YesNoError(f"Pick a price within 50% of where {u} is now (${spot:,.2f}).")
    chain = [r for r in _chain(u, level, exp) if r["expiration"] == exp]
    if not chain:
        raise YesNoError(f"No listed {u} options expire on that date. Pick one of the dates shown.")
    pair = strikes_around([r["strike"] for r in chain if r["type"] == "call"], level)
    if not pair:
        raise YesNoError("That price is outside the strikes listed for that date. Try one closer to today's price.")
    k1, k2 = pair
    near = [r for r in chain if r["iv"]]
    if near:
        iv_row = min(near, key=lambda r: (abs(r["strike"] - level), r["type"] != ("call" if level >= spot else "put")))
        vol, vol_source = iv_row["iv"], "market"
    else:
        try:
            vol = float(market.features(u)["vol60"])
        except Exception:
            vol = 0.4
        vol_source = "estimate"
    years = max(1, (exp - t).days) / 365.0
    # Quotes near the line set at another stock price (stale weekend quotes on the free feed): read their volatility
    # at that price, where calls and puts agree, not the feed's number (a put's IV read at the last price carries the
    # gap: live NVDA Dec 4 $125, feed 1.22 vs ~1.03). The one-vol answer below is then at the last price.
    at_own = quotes_own_price(chain, spot, level, years) if vol_source == "market" else None
    moved = bool(at_own and at_own["out"])
    if moved:
        vol = at_own["vol"]
    m_p_flat = prob_above(spot, level, years, vol)
    # The yardstick a spread's reading is checked against: the smile's own odds near the line (skew included) when
    # the quotes give a usable fit, else the one-vol answer.
    sk = skew_odds(chain, spot, level, years)
    ref = sk["p"] if sk else m_p_flat
    why: list = []
    dig = digital_from_spread([r for r in chain if r["type"] == "call"], level, years, why=why)
    # Quotes too noisy for a fine spread (thin $1 strikes, weekend quotes) read as inverted, far off, or blur the
    # trade's own pair by over MAX_NOISE: step out to a wider centred pair whose quotes can read the odds, trade that
    # pair, and read the odds off it. (With skew in the yardstick, a noisy $694/$696 reading of 64% sat within 10
    # points of the smile's 60%, so "far off" alone no longer caught it.)
    # Outside market hours the smile sets the odds anyway (below), so the trade keeps its narrow pair.
    try:
        closed = not market.is_open()
    except Exception:
        closed = False
    noise = spread_noise([r for r in chain if r["type"] == "call"], k1, k2)
    if not (closed and sk) and ("inverted" in why or (dig and (abs(dig[0] - ref) > 0.10
                                                             or (noise is not None and noise > MAX_NOISE)))):
        w1, w2 = quiet_pair([r for r in chain if r["type"] == "call"], level, (k1, k2))
        if (w1, w2) != (k1, k2):
            wide_dig = digital_from_spread([r for r in chain if r["type"] == "call" and r["strike"] in (w1, w2)],
                                           level, years)
            if wide_dig and abs(wide_dig[0] - ref) <= 0.10:
                k1, k2, dig, why = w1, w2, wide_dig, []
    # A reading over 10 points from the yardstick (the smile's skew-included odds, or one vol without a usable
    # smile) means the spread quotes are stale or out of step with the stock price (seen after hours: SPY at $752
    # with "61% to close above $755"), so use the one-vol answer and say so. Skew itself is in the yardstick: SPY's
    # one-week smile lifts a line just below the price ~12 points over one vol, which the old one-vol yardstick
    # mistook for stale quotes.
    stale = (bool(dig) and abs(dig[0] - ref) > 0.10) or "inverted" in why
    # Put-call parity: if the quotes imply a stock price well away from the last price, the spread's odds describe
    # a close relative to that other price. Then use the one-vol answer at the last price, and say what the quotes
    # imply. (A guard: on consistent quotes, e.g. live SPY Sat Nov 21, it stays quiet.)
    fwd = parity_forward(chain, sorted({k1, k2, *(dig[3] if dig else [])}), years) if dig else None
    off_step = bool(dig) and quotes_out_of_step(spot, fwd, vol, years)
    stale = stale or off_step
    # The trade's own call and put spreads must add up to the payout (parity, dividend-free): when they don't, the
    # calls and puts were quoted at different stock prices, so neither the call spread's odds nor a smile mixing
    # puts and calls can be read against the last price. Then the one-vol answer at the last price, and say so.
    split = calls_puts_disagree(chain, k1, k2, years)
    stale = stale or split
    # When the trade's strikes sit the same distance either side of the line, read the odds off that very spread
    # ((C(k1) - C(k2)) / (k2 - k1), the chance at its middle = the line), so YES's price is the odds shown. On an
    # even grid this is the same number as the reading above; on an uneven one (live SPY $699/$700/$705, trade
    # $695/$705) the finer pairs read 46.7% while the trade's own spread cost 50.2% of its payout.
    if dig and not stale and abs((k1 + k2) / 2 - level) <= 1e-6:
        own = digital_from_spread([r for r in chain if r["type"] == "call" and r["strike"] in (k1, k2)], level, years)
        if own and abs(own[0] - ref) <= 0.10:
            dig = own
    # Mids of quotes too wide to trade (the same test as the "What a real order would pay" box; usual outside market
    # hours) are noise, not skew: live SPY $725, Wed 7:30 AM ET, read 59%, 65% and 74% on three refreshes a minute
    # apart, the YES cost moving with it ($56 to $73). Then use the one-vol answer and price at the line IV.
    lc = listed_costs(chain, k1, k2, exp, {})
    wide = bool(lc and lc["wide"])
    # When the trade's own spread can't be read (quotes too wide, out of date or inverted), the smile still can: a
    # straight line through ~10-30 strikes' implied vols averages out the noise one $1 spread can't. Use its odds,
    # and price the trade's two strikes at the smile's vols, so YES still costs about the odds shown and the ladder
    # of lines falls as the line rises (live SPY Nov 27, weekend quotes: one-vol 60% at $685 beside a spread's 70% at
    # $690). Not when the quotes imply another stock price (off_step): the smile would describe that price too.
    # Outside market hours the smile is used even when one spread reads cleanly: the quotes are the last session's,
    # and a weekend reading of one spread drifts a few points with its quote noise (live Sat Nov 21, SPY Nov 27:
    # $690 read 69.7% from $687/$693 but $692 read 58.7% from $685/$699, the smile 65% and 63%).
    spread_ok = bool(dig) and not stale and not wide
    smile = bool(sk) and not off_step and not split and (closed or not spread_ok)
    if spread_ok and not smile:
        m_p, odds_source = dig[0], odds_label(dig[3], level)
    elif smile:
        why_not = ("the market is closed, and one spread's last quotes can blur its odds a few points" if closed
                   else "the spread quotes looked out of step" if stale
                   else "the trade's own quotes are too wide to read alone, usual outside market hours" if wide and dig
                   else "no tight spread quoted on the trade's strikes")
        m_p, odds_source = sk["p"], (f"the option smile near the line: implied volatilities of {sk['n']} listed "
                                     f"{u} options near {_money(level)} (skew included; {why_not})")
    else:
        from .strategy import RISK_FREE
        implied = fwd[0] * math.exp(-RISK_FREE * years) if off_step else at_own["price"] if moved and not split else None
        named = implied is not None and abs(implied / spot - 1) <= 0.05   # a wilder number is just broken quotes
        m_p, odds_source = m_p_flat, (f"one implied volatility (the option quotes were set as if {u} were near "
                                      f"${implied:,.2f}, not its last price ${spot:,.2f}, so their spreads would "
                                      f"misread the odds)" if named
                                      else "one implied volatility (the call and put quotes on these strikes "
                                           "disagree with each other, so they were set at different moments)" if split
                                      else "one implied volatility (the spread quotes looked out of date)" if stale
                                      else "one implied volatility (the listed quotes are too wide to read skew "
                                           "from, usual outside market hours)" if wide and dig
                                      else "one implied volatility (no tight spread quoted)")
    calls = [r for r in chain if r["type"] == "call"]
    # Price YES / NO at the listed mids of their own two strikes, each at its own IV (skew included), so the cost
    # agrees with the market's odds above it. Not when the odds already look stale (same snapshot of quotes).
    lv = leg_vols(calls, k1, k2, spot, years, vol) if vol_source == "market" and not stale and not wide else None
    if smile:
        lv = tuple(round(max(0.02, sk["vol"] + sk["slope"] * (k - level)), 4) for k in (k1, k2))
    sv = None
    if not lv and not wide and not stale:
        sv = spread_vol(calls, k1, k2, spot, years, vol)
        # Skew moves IV only a little across one strike gap, so a fit far from the line IV means stale or noisy
        # quotes (e.g. thin $1 strikes after hours): trust the line IV instead.
        sv = round(sv, 4) if sv and vol_source == "market" and abs(sv / vol - 1) <= 0.2 else None
    if smile:
        price_vol, price_source = round(sk["vol"], 4), "smile"
    elif lv:
        price_vol, price_source = round(vol, 4), "strikes"
    else:
        price_vol, price_source = (sv, "spread") if sv else ((vol, "line_iv") if vol_source == "market" else (None, "estimate"))
    rv60 = None
    try:
        _, closes = market.daily_closes(u)
        rv60 = market.realized_vol(closes, len(closes) - 1, 60) if len(closes) > 65 else None
    except Exception:
        pass
    move = expected_move(spot, chain, years, rv60, market.quote_years(exp)) if vol_source == "market" else None
    if move and move["big"] and u != "SPY":
        move["market_iv_rv"] = market_iv_rv(exp, years)
    sig = _signals(u)
    feats = make_features(m_p, sig, spot, level, vol, years)
    model = active_model()
    if model:
        b_p = predict(model, feats)
        tilt = _logit(b_p) - _logit(m_p)
    else:
        b_p, tilt = lean(m_p, sig["trend"], sig["ideas"])

    from . import practice_options
    yes_legs = [{"action": "Buy", "instrument": "option", "option_type": "call", "strike_price": k1, "expiration": exp.isoformat(), "quantity": 1},
                {"action": "Sell", "instrument": "option", "option_type": "call", "strike_price": k2, "expiration": exp.isoformat(), "quantity": 1}]
    no_legs = [{"action": "Buy", "instrument": "option", "option_type": "put", "strike_price": k2, "expiration": exp.isoformat(), "quantity": 1},
               {"action": "Sell", "instrument": "option", "option_type": "put", "strike_price": k1, "expiration": exp.isoformat(), "quantity": 1}]
    for l in yes_legs + no_legs:  # priced as one spread, rounded once, so YES + NO never tops the payout
        l["whole_cents"] = True
    if lv:
        kv = {k1: lv[0], k2: lv[1]}
        for l in yes_legs + no_legs:
            l["vol"] = kv[l["strike_price"]]
    width = round((k2 - k1) * 100, 2)
    sides = {}
    for side, legs in (("yes", yes_legs), ("no", no_legs)):
        try:
            q = practice_options.quote(u, legs, price_vol, keep_leg_vols=True)
            cost = round(max(1.0, min(width - 1.0, q["unit_value"])), 2)
        except Exception:
            cost = None
        # Breakeven at expiration: YES (call spread k1/k2) is worth (close - k1) x 100 between the strikes,
        # NO (put spread k2/k1) is worth (k2 - close) x 100, so neither breaks even exactly at the line.
        be = None if cost is None else round(k1 + cost / 100.0 if side == "yes" else k2 - cost / 100.0, 2)
        sides[side] = {"legs": legs, "cost": cost, "payout": width,
                       "profit": round(width - cost, 2) if cost is not None else None, "breakeven": be}
    return {"ticker": u, "spot": spot, "level": level, "expiration": exp.isoformat(), "days": (exp - t).days,
            "question": f"Will {u} close above ${level:,.2f} on {exp.strftime('%a %b')} {exp.day}?",
            "market_p": round(m_p, 4), "brain_p": round(b_p, 4), "tilt": round(tilt, 3),
            "vol": round(vol, 4), "vol_source": vol_source, "strikes": [k1, k2],
            "odds_source": odds_source, "market_p_flat_vol": round(m_p_flat, 4),
            "market_p_smile": round(sk["p"], 4) if sk else None,
            "price_vol": price_vol, "price_source": price_source, "leg_vols": list(lv) if lv else None,
            "reasons": _reasons(sig, u) + ([f"Its weights were learned from {model['n']} graded yes/no questions."] if model else []),
            "signals": sig, "features": feats, "brain_model": "learned" if model else "starting rules",
            "yes": sides["yes"], "no": sides["no"], "real_money": real_money_order(chain, k1, k2, exp),
            "listed": listed_costs(chain, k1, k2, exp, sides),
            "spread_note": spread_note(u, k1, k2, width, level),
            "move": dict(move, lines=move_text(u, move, exp, isinstance(info, dict) and bool(info.get("is_etf")))) if move else None}


def listed_costs(chain: list[dict], k1: float, k2: float, exp: date, sides: dict) -> Optional[dict]:
    """What the same spreads cost on the listed quotes right now, next to the practice price. Information only:
    practice trades keep filling at the practice price. Per side (per contract, $): bid = what selling the spread
    would get (buy leg's bid - sell leg's ask, floored at 0), ask = what paying up costs (buy leg's ask - sell leg's
    bid), mid, practice, and the odds YES/NO must beat to break even at the ask (ask / payout). `wide` when the quotes
    can't be traded as shown: a missing bid, an ask at or above the payout, or a bid/ask gap over 20% of the payout
    (usual outside market hours). None when either leg has no quote."""
    width = round((k2 - k1) * 100, 2)
    if width <= 0:
        return None

    def leg(kind, k):
        return next((r for r in chain if r["type"] == kind and r["strike"] == k and r["expiration"] == exp), None)
    out = {}
    for side, buy, sell in (("yes", leg("call", k1), leg("call", k2)), ("no", leg("put", k2), leg("put", k1))):
        if not buy or not sell or buy["ask"] <= 0 or sell["ask"] <= 0:
            return None
        ask = round((buy["ask"] - sell["bid"]) * 100, 2)
        bid = round(max(0.0, buy["bid"] - sell["ask"]) * 100, 2)
        mid = round((bid + ask) / 2, 2) if bid > 0 else None
        practice = (sides.get(side) or {}).get("cost")
        wide = bid <= 0 or ask >= width or (ask - bid) > 0.2 * width
        out[side] = {"bid": bid, "ask": ask, "mid": mid, "practice": practice, "wide": wide,
                     "odds_at_ask": round(min(1.0, ask / width), 4),
                     "odds_at_practice": round(practice / width, 4) if practice is not None else None}
    out["payout"] = width
    out["wide"] = out["yes"]["wide"] or out["no"]["wide"]
    # YES + NO always pay exactly `width` together, so on quotes from one moment both bids can't add up to more than
    # the payout, nor both asks to less (that would be free money). When they do, the call and put quotes were set at
    # different stock prices (live Sun Nov 22, NVDA $127/$133: bids $297 + $355 = $652 for a $600 payout).
    out["out_of_step"] = (out["yes"]["bid"] + out["no"]["bid"] > width + 0.005
                          or out["yes"]["ask"] + out["no"]["ask"] < width - 0.005)
    return out


def spread_note(u: str, k1: float, k2: float, width: float, level: Optional[float] = None) -> str:
    line = ""
    if level is not None and k1 < level < k2:
        lo, hi = level - k1, k2 - level
        line = (f"Its strikes sit ${lo:,.2f} either side of the ${level:,.2f} line, so YES's share of the payout is "
                f"about the market's odds of a close above it. " if abs(lo - hi) < 0.005 else
                f"Its strikes sit ${lo:,.2f} below and ${hi:,.2f} above the ${level:,.2f} line (no listed pair is "
                f"centred on it), so YES's share of the payout is about the market's odds of a close above "
                f"${(k1 + k2) / 2:,.2f}, the middle of the strikes, not the line. ")
    return (f"YES is a ${k1:,.2f}/${k2:,.2f} call spread: it pays the full ${width:,.0f} per contract if {u} closes at "
            f"or above ${k2:,.2f}, nothing at or below ${k1:,.2f}, and part of it in between. {line}NO is the matching "
            f"put spread, the mirror image. So the trade's result can differ from the yes/no answer when {u} closes "
            f"between the two strikes; the breakeven shows where each side starts to make money.")


def make_call(user_id: str, ticker: str, level: float, expiration: str, side: str, trade: bool = False,
              contracts: int = 1) -> dict:
    side = (side or "").lower()
    if side not in ("yes", "no"):
        raise YesNoError("Choose YES or NO.")
    q = quote(ticker, level, expiration)
    position_id = None
    exp = date.fromisoformat(q["expiration"])
    day = f"{exp.strftime('%a %b')} {exp.day}"
    what = f"{q['ticker']} above {_money(q['level'])} on {day}"
    msg = f"Logged: {side.upper()} on {what}. We'll grade it after that day's close."
    if trade:
        from . import practice_options
        try:
            r = practice_options.open_trade(user_id, q["ticker"], f"Close Call: {side.upper()} {q['ticker']} > ${q['level']:,.2f}"[:40],
                                            q[side]["legs"], contracts, q["question"],
                                            vol_override=q["price_vol"], keep_leg_vols=True)
        except practice_options.PracticeError as e:
            raise YesNoError(str(e))
        position_id = r.get("position_id")
        n = int(contracts or 1)
        # Our own words, not practice_options' generic "Opened 2 NVDA Close Call: NO NVDA > $185.00 contracts ...
        # Priced with the market's implied volatility" (it read garbled, and the price is the one shown above).
        msg = (f"Opened {side.upper()} on {what}: {n} contract{'s' if n > 1 else ''} with practice money "
               f"(about ${float(r.get('set_aside') or 0):,.0f} set aside), at the practice price shown above."
               + (" The market is closed, so it opened now at an estimate from the last prices; it doesn't wait "
                  "for the open." if r.get("market_closed") else "")
               + " It's in your Portfolio and settles at the close on " + day + ".")
    cid = f"yn-{uuid.uuid4().hex[:14]}"
    db.execute("""INSERT INTO yesno_calls (id, user_id, ticker, level, expiration, side, market_p, brain_p, spot,
                  strikes, cost, payout, contracts, position_id, created_at, features)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (cid, (user_id or "anonymous")[:80], q["ticker"], q["level"], q["expiration"], side, q["market_p"],
                q["brain_p"], q["spot"], f"{q['strikes'][0]},{q['strikes'][1]}", q[side]["cost"], q[side]["payout"],
                int(contracts or 1) if trade else 0, position_id, datetime.now(timezone.utc).isoformat(),
                db.dumps(q["features"])))
    return {"status": "success", "id": cid, "message": msg, "position_id": position_id}


def log_brain(ticker: str, level: float, expiration: str) -> Optional[str]:
    """The brain's own call (side = whichever its lean favors), for its public track record."""
    q = quote(ticker, level, expiration)
    if db.query_one("SELECT id FROM yesno_calls WHERE user_id = 'brain' AND ticker = ? AND level = ? AND expiration = ?",
                    (q["ticker"], q["level"], q["expiration"])):
        return None
    side = "yes" if q["brain_p"] >= 0.5 else "no"
    cid = f"yn-{uuid.uuid4().hex[:14]}"
    db.execute("""INSERT INTO yesno_calls (id, user_id, ticker, level, expiration, side, market_p, brain_p, spot,
                  strikes, cost, payout, contracts, position_id, created_at, features)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (cid, "brain", q["ticker"], q["level"], q["expiration"], side, q["market_p"], q["brain_p"], q["spot"],
                f"{q['strikes'][0]},{q['strikes'][1]}", None, None, 0, None, datetime.now(timezone.utc).isoformat(),
                db.dumps(q["features"])))
    return cid


BRAIN_TICKERS = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "JPM", "XOM", "NFLX", "COST", "AVGO")


def seed_daily(limit: int = 15) -> dict:
    """Once a trading day: the brain asks itself one question per big stock (nearest weekly expiration 5+ days out,
    line = today's price rounded to a strike) so its yes/no record builds every week, not just when users ask."""
    made, skipped = 0, 0
    for u in BRAIN_TICKERS[:limit]:
        try:
            e = expirations(u)
            t = _today()
            exp = next((x for x in e["expirations"] if (date.fromisoformat(x) - t).days >= 5), None)
            if not exp:
                skipped += 1
                continue
            step = _nice_step(e["spot"])
            if log_brain(u, round(e["spot"] / step) * step, exp):
                made += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    return {"made": made, "skipped": skipped}


# ----------------------------------------------------------------------------- grading

def _close_on(u: str, d: date) -> Optional[float]:
    dates, closes = market.daily_closes(u)
    if not dates or dates[-1] < d.isoformat():
        return None  # the expiration day's close isn't in yet
    i = max((j for j, x in enumerate(dates) if x <= d.isoformat()), default=None)
    return float(closes[i]) if i is not None else None


def grade_due(limit: int = 500) -> int:
    t = _today().isoformat()
    rows = db.query("SELECT id, ticker, level, expiration FROM yesno_calls WHERE graded_at IS NULL AND expiration < ? LIMIT ?",
                    (t, limit))
    n = 0
    for r in rows:
        try:
            c = _close_on(r["ticker"], date.fromisoformat(r["expiration"]))
        except Exception:
            c = None
        if c is None:
            continue
        db.execute("UPDATE yesno_calls SET close_price = ?, above = ?, graded_at = ? WHERE id = ?",
                   (c, 1 if c > float(r["level"]) else 0, datetime.now(timezone.utc).isoformat(), r["id"]))
        n += 1
    return n


def _view(r: dict) -> dict:
    out = {k: r[k] for k in ("id", "ticker", "level", "expiration", "side", "market_p", "brain_p", "spot", "cost",
                             "payout", "contracts", "position_id", "created_at", "close_price")}
    if r.get("graded_at"):
        happened = bool(r["above"])
        out["result"] = "right" if (r["side"] == "yes") == happened else "wrong"
    else:
        out["result"] = "open"
    return out


def mine(user_id: str) -> list[dict]:
    try:
        grade_due(100)
    except Exception:
        pass
    rows = db.query("SELECT * FROM yesno_calls WHERE user_id = ? ORDER BY created_at DESC LIMIT 100", ((user_id or "")[:80],))
    views = [_view(r) for r in rows]
    _attach_trades(user_id, views)
    return views


def _attach_trades(user_id: str, views: list[dict]) -> None:
    """An answer placed as a practice trade carries what the trade did. "Right" and "made money" can differ: a YES
    call spread that closes between its two strikes is right on the question but can still lose (below the
    breakeven), so the answer list shows both. Expired trades settle first (at the expiration-day close), the same
    step the Portfolio runs, so the two pages never disagree."""
    ids = [v["position_id"] for v in views if v.get("position_id")]
    if not ids:
        return
    from . import practice_options
    try:
        got = practice_options.outcomes(user_id, ids)
        if any(o["status"] == "open" for o in got.values()) and any(v["result"] != "open" for v in views):
            practice_options.positions(user_id)   # settles trades whose expiration-day close is in
            got = practice_options.outcomes(user_id, ids)
    except Exception:
        return
    for v in views:
        o = got.get(v.get("position_id") or "")
        if o:
            v["trade"] = o


def trades_total(views: list[dict]) -> Optional[dict]:
    """Close Call practice trades added up: the gain on settled or closed ones (same numbers as the Portfolio's
    closed list) and how many are still open. None when the user hasn't traded an answer."""
    t = [v["trade"] for v in views if v.get("trade")]
    if not t:
        return None
    done = [x for x in t if x["status"] == "closed" and x["pnl"] is not None]
    return {"settled": len(done), "pnl": round(sum(x["pnl"] for x in done), 2),
            "won": sum(1 for x in done if x["pnl"] > 0), "open": len(t) - len(done)}


MIN_VERDICT_DAYS = 5   # expiration days before the record says better / worse at all


def record_verdict(rows: list[dict]) -> dict:
    """Is the brain's lean beating the market's odds, or is that luck? Questions that close on the same day share one
    market move (15 stocks don't fall separately), so the error on the Brier gap is clustered by expiration day: each
    day counts once. 'too_early' until MIN_VERDICT_DAYS days are graded; then better / worse only past 2 errors."""
    by_day: dict = {}
    for r in rows:
        d = brier(float(r["market_p"]), bool(r["above"])) - brier(float(r["brain_p"]), bool(r["above"]))
        by_day.setdefault(str(r.get("expiration") or ""), []).append(d)
    n = sum(len(v) for v in by_day.values())
    days = len(by_day)
    if not n:
        return {"days": 0, "gain": None, "se": None, "verdict": "too_early"}
    gain = sum(sum(v) for v in by_day.values()) / n
    se = None
    if days >= 2:
        resid = sum((sum(v) - len(v) * gain) ** 2 for v in by_day.values())
        se = math.sqrt(resid * days / (days - 1)) / n
    if days < MIN_VERDICT_DAYS or se is None:
        verdict = "too_early"
    elif gain > 2 * se:
        verdict = "better"
    elif gain < -2 * se:
        verdict = "worse"
    else:
        verdict = "about_same"
    return {"days": days, "gain": round(gain, 5), "se": round(se, 5) if se is not None else None, "verdict": verdict}


MIN_MY_RECORD = 5   # graded answers before the user's record shows at all


def my_record(views: list[dict]) -> dict:
    """The user's own Close Call record, set against the market's odds at the moment they answered: being right on
    a 90% favourite says little, so 'right X of Y' is shown beside how many the market's odds alone expected
    (sum of the odds it gave each chosen side). Same question answered twice counts once. Like the brain's record,
    answers that close on the same day share one market move, so the luck band is clustered by expiration day and
    nothing beyond 'within luck' is said before MIN_VERDICT_DAYS days. Information only: read by nothing else."""
    seen: dict = {}
    for v in views:
        if v.get("result") not in ("right", "wrong") or v.get("market_p") is None:
            continue
        seen.setdefault((v.get("ticker"), float(v.get("level") or 0), v.get("expiration"), v.get("side")), v)
    rows = list(seen.values())
    open_n = sum(1 for v in views if v.get("result") == "open")
    n = len(rows)
    if n < MIN_MY_RECORD:
        return {"graded": n, "open": open_n, "min": MIN_MY_RECORD, "verdict": "too_few"}
    by_day: dict = {}
    right = expected = 0.0
    for r in rows:
        p = float(r["market_p"]) if r["side"] == "yes" else 1.0 - float(r["market_p"])
        hit = 1.0 if r["result"] == "right" else 0.0
        right += hit
        expected += p
        by_day.setdefault(str(r.get("expiration") or ""), []).append(hit - p)
    days = len(by_day)
    gap = right - expected
    se = None
    if days >= 2:
        mean = gap / n
        resid = sum((sum(d) - len(d) * mean) ** 2 for d in by_day.values())
        se = math.sqrt(resid * days / (days - 1))
    if days < MIN_VERDICT_DAYS or se is None:
        verdict = "too_early"
    elif gap > 2 * se:
        verdict = "ahead"
    elif gap < -2 * se:
        verdict = "behind"
    else:
        verdict = "within_luck"
    return {"graded": n, "open": open_n, "right": int(right), "expected": round(expected, 1),
            "avg_odds": round(expected / n, 3), "days": days, "gap": round(gap, 1),
            "se": round(se, 1) if se is not None else None, "verdict": verdict, "min_days": MIN_VERDICT_DAYS}


def my_record_for(user_id: str) -> dict:
    views = mine(user_id)
    out = my_record(views)
    out["trades"] = trades_total(views)
    return out


def _disagrees(market_p, brain_p) -> bool:
    """The brain's lean takes the other side from the market's odds (one at or above 50%, the other below). Its lean
    is a small nudge on the market's odds, so this is the only place its side can differ from the market's."""
    return (float(brain_p) >= 0.5) != (float(market_p) >= 0.5)


def brain_questions(limit: int = 12, graded: bool = False) -> list[dict]:
    """Public: the brain's own daily questions, newest asked first, each with the market's odds and the brain's at
    the time of asking and, once graded, the expiration-day close and right / wrong. Users' questions stay private.
    graded=True: only graded ones, latest expiration first. The newest-asked list is all open questions most days
    (it asks ~11 a day, 5+ days out), so without this the record's right / wrong answers never show."""
    n = max(1, min(int(limit), 60))
    if graded:
        rows = db.query("SELECT * FROM yesno_calls WHERE user_id = 'brain' AND graded_at IS NOT NULL "
                        "ORDER BY expiration DESC, created_at DESC LIMIT ?", (n,))
    else:
        rows = db.query("SELECT * FROM yesno_calls WHERE user_id = 'brain' ORDER BY created_at DESC LIMIT ?", (n,))
    out = []
    for r in rows:
        v = {k: r[k] for k in ("ticker", "level", "expiration", "side", "spot", "close_price")}
        v["asked"] = str(r.get("created_at") or "")[:10]
        v["market_p"] = round(float(r["market_p"]), 3)
        v["brain_p"] = round(float(r["brain_p"]), 3)
        v["disagrees"] = _disagrees(r["market_p"], r["brain_p"])
        v["result"] = _view(r)["result"]
        out.append(v)
    return out


def scorecard() -> dict:
    """Public: how the brain's lean has done against the market's odds on graded questions (all askers)."""
    try:
        recent = brain_questions()
    except Exception:
        recent = []
    try:
        graded_recent = brain_questions(graded=True)
    except Exception:
        graded_recent = []
    brain_open = int((db.query_one("SELECT COUNT(*) AS n FROM yesno_calls WHERE graded_at IS NULL AND user_id = 'brain'")
                      or {}).get("n") or 0)  # the brain's own; "open" below counts every asker's
    rows = db.query("SELECT market_p, brain_p, above, side, user_id, expiration FROM yesno_calls WHERE graded_at IS NOT NULL")
    seen = {}
    for r in rows:
        seen.setdefault((r["market_p"], r["brain_p"], r["above"]), r)  # same question asked twice counts once
    rows = list(seen.values())
    n = len(rows)
    if not n:
        return {"graded": 0, "recent": recent, "graded_recent": graded_recent, "brain_open": brain_open,
                "open": int((db.query_one("SELECT COUNT(*) AS n FROM yesno_calls WHERE graded_at IS NULL") or {}).get("n") or 0)}
    bm = sum(brier(float(r["market_p"]), bool(r["above"])) for r in rows) / n
    bb = sum(brier(float(r["brain_p"]), bool(r["above"])) for r in rows) / n
    lean_right = sum(1 for r in rows if (float(r["brain_p"]) >= 0.5) == bool(r["above"])) / n
    market_right = sum(1 for r in rows if (float(r["market_p"]) >= 0.5) == bool(r["above"])) / n
    v = record_verdict(rows)
    open_n = int((db.query_one("SELECT COUNT(*) AS n FROM yesno_calls WHERE graded_at IS NULL") or {}).get("n") or 0)
    users = [r for r in db.query("SELECT side, above FROM yesno_calls WHERE graded_at IS NOT NULL AND user_id NOT IN ('brain', 'anonymous')")]
    split = [r for r in rows if _disagrees(r["market_p"], r["brain_p"])]
    disagree = {"n": len(split), "right": sum(1 for r in split if (float(r["brain_p"]) >= 0.5) == bool(r["above"])),
                "days": len({str(r.get("expiration") or "") for r in split})}
    st = model_status() or {}
    learning = {k: st.get(k) for k in ("active", "graded", "test_n", "brier_gain", "t", "note", "at")}
    return {"learning": learning, "graded": n, "recent": recent, "graded_recent": graded_recent, "disagree": disagree, "open": open_n, "brain_open": brain_open, "brier_market": round(bm, 4), "brier_brain": round(bb, 4),
            "brain_better": v["verdict"] == "better", "brain_side_right": round(lean_right, 3),
            "market_side_right": round(market_right, 3), "days": v["days"], "brier_gain": v["gain"], "brier_se": v["se"],
            "verdict": v["verdict"], "min_days": MIN_VERDICT_DAYS,
            "people_graded": len(users),
            "people_right": round(sum(1 for r in users if (r["side"] == "yes") == bool(r["above"])) / len(users), 3) if users else None}


def daily() -> dict:
    """Hourly cron hook: grade anything past expiration; once a trading day (during market hours, so the option
    quotes are live) let the brain ask its own questions."""
    out = {"graded": grade_due()}
    try:
        st = model_status() or {}
        if (st.get("at") or "")[:10] != datetime.now(timezone.utc).date().isoformat():
            out["learn"] = {k: v for k, v in learn().items() if k != "w"}
    except Exception as e:
        out["learn"] = f"failed: {e}"
    now = market.now_ny()
    day = now.date().isoformat()
    if now.weekday() >= 5 or not ((10, 0) <= (now.hour, now.minute) < (15, 30)):
        out["seed"] = "outside market hours"
        return out
    if db.query_one("SELECT v FROM kv_cache WHERE k = 'yesno:day'") == {"v": day}:
        out["seed"] = "already today"
        return out
    out["seed"] = seed_daily()
    db.execute("DELETE FROM kv_cache WHERE k = 'yesno:day'")
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", ("yesno:day", day, datetime.now(timezone.utc).isoformat()))
    return out


# ----------------------------------------------------------------------------- learning (feeds the brain)
#
# Every question is stored with the features the brain saw at the moment of asking (point in time). Once enough are
# graded, a small logistic model learns how much each signal should move the market's odds. It goes live only if,
# on the newest questions it never trained on, it beats the market's own odds (lower Brier score, paired t >= 1.5),
# the same "prove it on unseen data" rule as the rest of the brain. Until then the starting rules (small, capped) run.

FEATS = ("m_logit", "trend", "ideas", "crowd", "dist_sd")
MIN_LEARN = 200
TEST_SHARE = 0.3
MIN_T = 1.5


def make_features(market_p: float, sig: dict, spot: float, level: float, vol: float, years: float) -> dict:
    sd = max(1e-6, vol * math.sqrt(max(years, 1 / 365)))
    return {"m_logit": round(_logit(market_p), 5), "trend": float(sig.get("trend") or 0.0),
            "ideas": float(sig["ideas"]) if sig.get("ideas") is not None else 0.0,
            "crowd": float(sig["crowd"]) if sig.get("crowd") is not None else 0.0,
            "dist_sd": round(max(-4.0, min(4.0, math.log(spot / level) / sd)), 5)}


def _x(f: dict) -> list[float]:
    return [1.0] + [float(f.get(k) or 0.0) for k in FEATS]


def predict(model: dict, f: dict) -> float:
    z = sum(w * x for w, x in zip(model["w"], _x(f)))
    return min(0.99, max(0.01, _sig(z)))


def fit(rows: list[tuple[dict, bool]], l2: float = 1.0, steps: int = 400) -> list[float]:
    """Logistic regression by Newton steps, started at 'trust the market' (weight 1 on the market's log-odds)."""
    import numpy as np
    X = np.array([_x(f) for f, _ in rows])
    y = np.array([1.0 if a else 0.0 for _, a in rows])
    w = np.zeros(X.shape[1]); w[1] = 1.0
    prior = w.copy()
    for _ in range(min(steps, 50)):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + l2 * (w - prior)
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-7:
            break
    return [round(float(v), 6) for v in w]


def _graded_rows() -> list[dict]:
    rows = db.query("""SELECT id, features, above, market_p, expiration, created_at, ticker, level FROM yesno_calls
                       WHERE graded_at IS NOT NULL AND features IS NOT NULL ORDER BY created_at""")
    seen, out = set(), []
    for r in rows:
        key = (r["ticker"], r["level"], r["expiration"], (r["created_at"] or "")[:10])
        if key in seen:
            continue  # the same question asked by several people counts once
        seen.add(key)
        f = db.loads(r["features"], None)
        if f:
            out.append({"f": f, "above": bool(r["above"]), "market_p": float(r["market_p"]),
                        "expiration": r["expiration"], "created_at": r["created_at"]})
    return out


def learn() -> dict:
    """Nightly: walk-forward test, then (only if it beats the market's odds) refit on everything and go live."""
    rows = _graded_rows()
    res = {"at": datetime.now(timezone.utc).isoformat(), "graded": len(rows), "active": False}
    if len(rows) < MIN_LEARN:
        res["note"] = f"waiting for {MIN_LEARN} graded questions"
        _kv_put("yesno:model", res)
        return res
    cut = int(len(rows) * (1 - TEST_SHARE))
    test = rows[cut:]
    first_test = min(r["created_at"] for r in test)[:10]
    train = [r for r in rows[:cut] if r["expiration"] < first_test]  # no question still open when testing starts
    if len(train) < MIN_LEARN // 2:
        res["note"] = "not enough questions finished before the test window"
        _kv_put("yesno:model", res)
        return res
    w = fit([(r["f"], r["above"]) for r in train])
    m = {"w": w}
    d = [brier(r["market_p"], r["above"]) - brier(predict(m, r["f"]), r["above"]) for r in test]
    mean = sum(d) / len(d)
    sd = (sum((x - mean) ** 2 for x in d) / max(1, len(d) - 1)) ** 0.5
    t = mean / (sd / math.sqrt(len(d))) if sd > 0 else 0.0
    res.update(test_n=len(test), train_n=len(train), brier_gain=round(mean, 5), t=round(t, 2),
               brier_market=round(sum(brier(r["market_p"], r["above"]) for r in test) / len(test), 4))
    if mean > 0 and t >= MIN_T:
        res.update(active=True, w=fit([(r["f"], r["above"]) for r in rows]), n=len(rows), feats=list(FEATS))
    else:
        res["note"] = "didn't beat the market's odds on unseen questions; starting rules stay"
    _kv_put("yesno:model", res)
    return res


def _kv_put(k: str, v: dict) -> None:
    db.execute("DELETE FROM kv_cache WHERE k = ?", (k,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (k, db.dumps(v), datetime.now(timezone.utc).isoformat()))


def model_status() -> Optional[dict]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = 'yesno:model'")
    return db.loads(row["v"], None) if row else None


def active_model() -> Optional[dict]:
    m = model_status()
    return m if m and m.get("active") and m.get("w") and m.get("feats") == list(FEATS) else None


# ----------------------------------------------------------------------------- real money (ready, switched off)
#
# The practice trade and the real one are the same two listed contracts. real_money_order() builds the order a
# broker takes for a two-leg spread (Alpaca multi-leg "mleg", limit at the mid of the net price, opening only, fully
# defined risk). It is NOT sent anywhere: user real money is off (brokerage.enabled() is false) until a securities
# lawyer signs off, and brokerage.py doesn't place spreads yet. When it does, it takes this payload through the same
# preview -> confirm -> per-order cap path as every other real order.

def real_money_order(chain: list[dict], k1: float, k2: float, exp: date) -> dict:
    def leg(kind, k):
        return next((r for r in chain if r["type"] == kind and r["strike"] == k and r["expiration"] == exp), None)
    out = {}
    for side, buy, sell in (("yes", leg("call", k1), leg("call", k2)), ("no", leg("put", k2), leg("put", k1))):
        if not buy or not sell or buy["ask"] <= 0 or sell["bid"] < 0:
            out[side] = None
            continue
        natural = buy["ask"] - sell["bid"]                       # pay the ask, get the bid: the worst fill
        mid = (buy["bid"] + buy["ask"]) / 2 - (sell["bid"] + sell["ask"]) / 2
        limit = round(max(0.01, min(natural, mid)), 2)
        out[side] = {"order": {"order_class": "mleg", "type": "limit", "time_in_force": "day", "qty": "1",
                               "limit_price": f"{limit:.2f}",
                               "legs": [{"symbol": buy["symbol"], "side": "buy", "ratio_qty": "1", "position_intent": "buy_to_open"},
                                        {"symbol": sell["symbol"], "side": "sell", "ratio_qty": "1", "position_intent": "sell_to_open"}]},
                     "net_cost": round(limit * 100, 2), "worst_fill": round(natural * 100, 2),
                     "max_loss": round(limit * 100, 2), "max_gain": round((k2 - k1 - limit) * 100, 2)}
    try:
        from . import brokerage
        on = brokerage.enabled()
    except Exception:
        on = False
    out["available"] = False   # flips only when spreads are wired into brokerage.preview/place
    out["switch"] = "on" if on else "off"
    out["note"] = "Practice money for now. Real money opens after legal sign-off."
    return out
