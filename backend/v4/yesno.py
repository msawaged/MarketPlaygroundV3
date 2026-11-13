"""
Close Call (Yes / No, 2026-11-12): "Will NVDA close above $150 on Fri Nov 21?" answered with real option prices.

A Nadex-style question without Nadex. Three numbers, in this order:
  1. The market's odds: the chance option prices imply that the stock finishes above the line on that expiration
     (Black-Scholes N(d2) with the implied volatility of the listed strike nearest the line). Over days or weeks the
     market's (risk-neutral) odds and real-world odds are very close, so we show it as plain odds.
  2. The brain's lean: the market's odds nudged by what the brain knows (the stock's MuLine trend and which way the
     app's recent ideas on it point). The nudge is small and capped (at most about 7 points), because the brain is
     proven on 90-day calls, not on one-week ones. Every lean is logged and graded so that changes with evidence.
  3. The trade: YES = a call spread (buy the strike at the line, sell the next one up); NO = a put spread (buy the
     next strike up, sell the one at the line). Fixed cost, fixed most-you-can-make, like a Nadex contract. Opened
     with practice money through practice_options, so it shows in Portfolio and settles at expiration like any
     other practice options trade.

Grading: after expiration, a question is right when the stock closed above the line and the answer was YES (or at or
below and the answer was NO). We keep the market's and the brain's odds at the moment of asking, so the scorecard can
say honestly whether the brain's lean beat the market's odds (Brier score: lower is better).

Nothing here touches existing features: own table (yesno_calls), own endpoints, trades via practice_options.open_trade.
"""
from __future__ import annotations

import math
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
    """(the listed strike at or just below the line, the next one up)."""
    ks = sorted(set(k for k in strikes if k > 0))
    lo = [k for k in ks if k <= level + 1e-9]
    if not lo:
        return None
    k1 = lo[-1]
    hi = [k for k in ks if k > k1]
    if not hi:
        return None
    return k1, hi[0]


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
        r.append(f"{u}'s MuLine trend is rising" + (f" (for {sig['trend_age']} trading days)" if sig.get("trend_age") else "") + ".")
    elif sig["trend"] < 0:
        r.append(f"{u}'s MuLine trend is falling" + (f" (for {sig['trend_age']} trading days)" if sig.get("trend_age") else "") + ".")
    if sig["ideas"] is not None:
        r.append(f"In the past {IDEA_DAYS} days the app suggested {u} {sig['ideas_n']:,} times: {sig['ideas_bull']:,} as a "
                 f"bullish idea, {sig['ideas_bear']:,} as a bearish one.")
    if not r:
        r.append("The brain has no strong read on this stock, so it stays with the market's odds.")
    return r


def quote(ticker: str, level: float, expiration: str) -> dict:
    u = (ticker or "").upper().strip()
    if not u or not market.asset_info(u):
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
    m_p = prob_above(spot, level, years, vol)
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
    width = round((k2 - k1) * 100, 2)
    sides = {}
    for side, legs in (("yes", yes_legs), ("no", no_legs)):
        try:
            q = practice_options.quote(u, legs, vol if vol_source == "market" else None)
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
            "reasons": _reasons(sig, u) + ([f"Its weights were learned from {model['n']} graded yes/no questions."] if model else []),
            "signals": sig, "features": feats, "brain_model": "learned" if model else "starting rules",
            "yes": sides["yes"], "no": sides["no"], "real_money": real_money_order(chain, k1, k2, exp),
            "spread_note": spread_note(u, k1, k2, width)}


def spread_note(u: str, k1: float, k2: float, width: float) -> str:
    return (f"YES is a ${k1:,.2f}/${k2:,.2f} call spread: it pays the full ${width:,.0f} per contract if {u} closes at "
            f"or above ${k2:,.2f}, nothing at or below ${k1:,.2f}, and part of it in between. NO is the matching put "
            f"spread, the mirror image. So the trade's result can differ from the yes/no answer when {u} closes between "
            f"the two strikes; the breakeven shows where each side starts to make money.")


def make_call(user_id: str, ticker: str, level: float, expiration: str, side: str, trade: bool = False,
              contracts: int = 1) -> dict:
    side = (side or "").lower()
    if side not in ("yes", "no"):
        raise YesNoError("Choose YES or NO.")
    q = quote(ticker, level, expiration)
    position_id = None
    msg = f"Logged: {side.upper()}. We'll grade it after the close on {q['expiration']}."
    if trade:
        from . import practice_options
        try:
            r = practice_options.open_trade(user_id, q["ticker"], f"Close Call: {side.upper()} {q['ticker']} > ${q['level']:,.2f}"[:40],
                                            q[side]["legs"], contracts, q["question"],
                                            vol_override=q["vol"] if q["vol_source"] == "market" else None)
        except practice_options.PracticeError as e:
            raise YesNoError(str(e))
        position_id = r.get("position_id")
        msg = r.get("message", msg) + " It's in your Portfolio."
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
    return [_view(r) for r in rows]


def scorecard() -> dict:
    """Public: how the brain's lean has done against the market's odds on graded questions (all askers)."""
    rows = db.query("SELECT market_p, brain_p, above, side, user_id FROM yesno_calls WHERE graded_at IS NOT NULL")
    seen = {}
    for r in rows:
        seen.setdefault((r["market_p"], r["brain_p"], r["above"]), r)  # same question asked twice counts once
    rows = list(seen.values())
    n = len(rows)
    if not n:
        return {"graded": 0, "open": int((db.query_one("SELECT COUNT(*) AS n FROM yesno_calls WHERE graded_at IS NULL") or {}).get("n") or 0)}
    bm = sum(brier(float(r["market_p"]), bool(r["above"])) for r in rows) / n
    bb = sum(brier(float(r["brain_p"]), bool(r["above"])) for r in rows) / n
    lean_right = sum(1 for r in rows if (float(r["brain_p"]) >= 0.5) == bool(r["above"])) / n
    open_n = int((db.query_one("SELECT COUNT(*) AS n FROM yesno_calls WHERE graded_at IS NULL") or {}).get("n") or 0)
    users = [r for r in db.query("SELECT side, above FROM yesno_calls WHERE graded_at IS NOT NULL AND user_id NOT IN ('brain', 'anonymous')")]
    st = model_status() or {}
    learning = {k: st.get(k) for k in ("active", "graded", "test_n", "brier_gain", "t", "note", "at")}
    return {"learning": learning, "graded": n, "open": open_n, "brier_market": round(bm, 4), "brier_brain": round(bb, 4),
            "brain_better": bb < bm, "brain_side_right": round(lean_right, 3),
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
