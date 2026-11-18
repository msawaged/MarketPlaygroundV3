"""
Practice options: buy or sell a multi-leg options trade with practice money, value it as the stock moves, close it.

Prices are estimates (Black-Scholes on the stock's live price and its 60-day volatility); the app says so. The server
re-prices every leg itself, so the client only chooses which contracts, never what they cost.

Money: opening sets aside the trade's worst case (or its cost, whichever is larger) from practice cash.
Closing returns that amount plus the trade's gain or loss:  cash back = set_aside + (value_now - value_at_open).
At expiration a trade settles automatically at what it's worth at that day's official close (the stock's closing
price on expiration day, not whatever it trades at when someone next opens the app).
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional

from . import library, market
from .strategy import bs_price

MAX_LEGS = 4
MAX_CONTRACTS = 1000


class PracticeError(Exception):
    pass


def _engine():
    from backend.paper_trading import paper_engine
    return paper_engine


def init(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS option_positions (
            position_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            structure TEXT NOT NULL,
            legs TEXT NOT NULL,
            contracts INTEGER NOT NULL,
            entry_value REAL NOT NULL,
            set_aside REAL NOT NULL,
            vol REAL NOT NULL,
            belief TEXT,
            status TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            close_value REAL
        )""")


def _clean_legs(raw: list, ticker: str, keep_leg_vols: bool = False) -> list[dict]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_LEGS:
        raise PracticeError("That trade doesn't look right. Try building it again.")
    today = market.today()
    legs = []
    for l in raw:
        if not isinstance(l, dict):
            raise PracticeError("That trade doesn't look right.")
        action = "Buy" if str(l.get("action", "")).lower().startswith("buy") else "Sell" if str(l.get("action", "")).lower().startswith("sell") else None
        if not action:
            raise PracticeError("That trade doesn't look right.")
        qty = int(l.get("quantity") or 1)
        if str(l.get("instrument")) == "stock":
            if qty not in (100,):
                qty = 100
            legs.append({"action": action, "ticker": ticker, "instrument": "stock", "quantity": qty})
            continue
        kind = str(l.get("option_type") or "").lower()
        k = float(l.get("strike_price") or 0)
        try:
            exp = date.fromisoformat(str(l.get("expiration"))[:10])
        except ValueError:
            raise PracticeError("That trade is missing an expiration date.")
        if kind not in ("call", "put") or k <= 0 or not 1 <= qty <= 2 or not (today < exp <= date(today.year + 3, 12, 31)):
            raise PracticeError("That trade doesn't look right. Try building it again.")
        leg = {"action": action, "ticker": ticker, "instrument": "option", "option_type": kind.capitalize(),
               "strike_price": round(k, 2), "expiration": exp.isoformat(), "quantity": qty}
        # A leg's own volatility (each strike at its own implied vol, "sticky strike"): only from server code
        # (Close Call), never from a request, so nobody can price their own practice trade.
        lv = l.get("vol") if keep_leg_vols else None
        if isinstance(lv, (int, float)) and math.isfinite(lv) and 0.05 <= lv <= 1.5:
            leg["vol"] = round(float(lv), 4)
        if keep_leg_vols and l.get("whole_cents") is True:  # Close Call: round the spread, not each leg (unit_value)
            leg["whole_cents"] = True
        legs.append(leg)
    if not any(l["instrument"] == "option" for l in legs):
        raise PracticeError("Use the regular trade button for shares.")
    return legs


def _vol(ticker: str) -> float:
    try:
        v = float(market.features(ticker)["vol60"])
    except Exception:
        v = 0.4
    return min(1.5, max(0.1, v if math.isfinite(v) else 0.4))


def unit_value(legs: list[dict], spot: float, vol: float, on: Optional[date] = None) -> float:
    """What one unit of the trade is worth now in dollars (bought legs +, sold legs -)."""
    on = on or market.today()
    # Close Call's YES / NO spreads (legs marked "whole_cents", server code only) round the whole trade to the
    # cent instead of each leg: rounding each leg moved a $250 spread by up to $1, so YES + NO could cost $251
    # for a $250 payout (buy both, lose $1 for sure). Rounded once, YES + NO = the discounted payout to the cent.
    whole = any(l.get("whole_cents") for l in legs)
    total = 0.0
    for l in legs:
        sign = 1 if l["action"] == "Buy" else -1
        if l["instrument"] == "stock":
            total += sign * spot * l["quantity"]
            continue
        t = max(0, (date.fromisoformat(l["expiration"]) - on).days) / 365.0
        # Option prices are quoted in whole cents, the same way the idea card shows them, so a spread the card
        # prices at $3.44 - $0.99 = $245 costs $245 here too (not $246 from unrounded model prices).
        px = bs_price(spot, l["strike_price"], t, l.get("vol") or vol, l["option_type"].lower())
        total += sign * (px if whole else round(px, 2)) * 100 * l["quantity"]
    return round(total, 2) if whole else total


def _priced(legs: list[dict], spot: float, vol: float) -> list[dict]:
    on = market.today()
    out = []
    for l in legs:
        if l["instrument"] == "option":
            t = max(1, (date.fromisoformat(l["expiration"]) - on).days) / 365.0
            l = dict(l, est_premium=round(bs_price(spot, l["strike_price"], t, l.get("vol") or vol, l["option_type"].lower()), 2))
        out.append(l)
    return out


def quote(ticker: str, legs_in: list, vol_override: Optional[float] = None, keep_leg_vols: bool = False) -> dict:
    ticker = (ticker or "").upper().strip()
    if not ticker or not market.asset_info(ticker):
        raise PracticeError("That isn't a stock we can trade.")
    legs = _clean_legs(legs_in, ticker, keep_leg_vols)
    spot = float(market.latest_price(ticker))
    vol, vol_source = _vol(ticker), "estimate"
    ivs = []
    for l in legs:  # price with the market's implied volatility when available (captures smile and skew)
        if l["instrument"] == "option":
            try:
                iv = market.option_iv(ticker, l["option_type"], l["strike_price"], date.fromisoformat(l["expiration"]))
            except Exception:
                iv = None
            if iv:
                ivs.append(iv)
    if ivs:
        vol, vol_source = min(1.5, max(0.05, sum(ivs) / len(ivs))), "market"
    if vol_override:  # one volatility for every leg (Yes / No prices YES and NO alike, so they add up to the payout)
        vol, vol_source = min(1.5, max(0.05, float(vol_override))), "market"
    entry = unit_value(legs, spot, vol)
    worst = float(library.economics(_priced(legs, spot, vol), spot)["max_loss"])
    set_aside = max(entry, worst, 1.0)
    return {"ticker": ticker, "legs": legs, "spot": spot, "vol": vol, "vol_source": vol_source,
            "unit_value": entry, "unit_set_aside": set_aside}


def open_trade(user_id: str, ticker: str, structure: str, legs_in: list, contracts: int, belief: str = "",
               vol_override: Optional[float] = None, keep_leg_vols: bool = False) -> dict:
    contracts = int(contracts or 1)
    if not 1 <= contracts <= MAX_CONTRACTS:
        raise PracticeError(f"Choose between 1 and {MAX_CONTRACTS} contracts.")
    q = quote(ticker, legs_in, vol_override, keep_leg_vols)
    need = q["unit_set_aside"] * contracts
    eng = _engine()
    with eng._lock:
        eng._initialize_user(user_id)
        with eng._get_db_connection() as conn:
            init(conn)
            cash = float(conn.execute("SELECT cash_balance FROM users WHERE user_id = ?", (user_id,)).fetchone()["cash_balance"])
            if need > cash + 1e-6:
                raise PracticeError(f"This needs about ${need:,.0f} and your practice account has ${cash:,.0f}.")
            pid = f"opt-{uuid.uuid4().hex[:12]}"
            conn.execute("UPDATE users SET cash_balance = cash_balance - ?, buying_power = buying_power - ? WHERE user_id = ?",
                         (Decimal(str(round(need, 2))), Decimal(str(round(need, 2))), user_id))
            conn.execute("""INSERT INTO option_positions (position_id, user_id, ticker, structure, legs, contracts, entry_value,
                            set_aside, vol, belief, status, opened_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (pid, user_id, q["ticker"], (structure or "Options")[:40], json.dumps(q["legs"]), contracts,
                          q["unit_value"], q["unit_set_aside"], q["vol"], (belief or "")[:300], "open",
                          _now_utc()))
    try:  # practice options open right away, even when the market is closed (unlike practice shares): say so
        closed = not market.clock().get("is_open", True)
    except Exception:
        closed = False
    return {"status": "success", "position_id": pid, "set_aside": round(need, 2), "market_closed": closed,
            "message": f"Opened {contracts} {q['ticker']} {structure or 'options'} contract{'s' if contracts > 1 else ''} "
                       f"with practice money (about ${need:,.0f} set aside). "
                       + ("Priced with the market's implied volatility." if q.get("vol_source") == "market" else "Prices are estimates.")
                       + (" The market is closed, so it opened now at an estimate from the last prices; it doesn't wait for the open."
                          if closed else "")}


def _now_utc() -> str:
    """Stored with its UTC offset: a bare server time read as the phone's local time put evening US closes on the next day."""
    return datetime.now(timezone.utc).isoformat()


def _expiry_close(exp: date) -> datetime:
    """4pm New York on expiration day, when an expiring trade settles."""
    return datetime.combine(exp, time(16), tzinfo=market.NY or timezone.utc)


def _aware(ts) -> Optional[datetime]:
    """A stored time as an aware datetime. Older rows have no offset: an expiry settle was written as 'T16:00:00'
    (meant New York), everything else was the server clock (UTC)."""
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    if d.tzinfo:
        return d
    if d.time() == time(16):
        return d.replace(tzinfo=market.NY or timezone.utc)
    return d.replace(tzinfo=timezone.utc)


def _settle(conn, row, value_now: float, when: Optional[str] = None) -> float:
    back = row["set_aside"] * row["contracts"] + (value_now - row["entry_value"]) * row["contracts"]
    back = max(0.0, back)
    conn.execute("UPDATE users SET cash_balance = cash_balance + ?, buying_power = buying_power + ? WHERE user_id = ?",
                 (Decimal(str(round(back, 2))), Decimal(str(round(back, 2))), row["user_id"]))
    conn.execute("UPDATE option_positions SET status = 'closed', closed_at = ?, close_value = ? WHERE position_id = ?",
                 (when or _now_utc(), value_now, row["position_id"]))
    return back


def _expired(legs: list[dict]) -> Optional[date]:
    exps = [date.fromisoformat(l["expiration"]) for l in legs if l["instrument"] == "option"]
    last = max(exps) if exps else None
    return last if last and last <= market.today() else None


def _past_expiry(legs: list[dict]) -> Optional[date]:
    """The expiration date once its 4pm New York close has passed (the trade can no longer be closed by hand)."""
    exp = _expired(legs)
    if exp and (exp < market.today() or market.now_ny() >= _expiry_close(exp)):
        return exp
    return None


def _settle_price(ticker: str, exp: date) -> Optional[float]:
    """The stock's official close on expiration day (or the last session before it, for a holiday expiry). None
    until that day is over and its bar is in: the trade waits rather than settling at a later price."""
    try:
        got = market.session_close_on(ticker, exp)
    except Exception:
        got = None
    return float(got[1]) if got else None


def positions(user_id: str) -> list[dict]:
    """Open option trades with what they're worth now. Trades past expiration settle here, at the expiration-day
    close; until that close is in, they show as 'settling' at their value at today's price."""
    eng = _engine()
    out = []
    with eng._lock:
        with eng._get_db_connection() as conn:
            init(conn)
            rows = conn.execute("SELECT * FROM option_positions WHERE user_id = ? AND status = 'open' ORDER BY opened_at DESC",
                                (user_id,)).fetchall()
            for r in rows:
                legs = json.loads(r["legs"])
                exp = _expired(legs)
                done = _past_expiry(legs)
                if done and done < market.today():
                    px = _settle_price(r["ticker"], done)
                    if px is not None:  # settled at what it was worth at the expiration-day close
                        _settle(conn, r, unit_value(legs, px, r["vol"], on=done), when=_expiry_close(done).isoformat())
                        continue
                try:
                    spot = float(market.latest_price(r["ticker"]))
                except Exception:
                    spot = None
                if spot is None:
                    continue
                v = unit_value(legs, spot, r["vol"], on=exp) if exp else unit_value(legs, spot, r["vol"])
                pnl = (v - r["entry_value"]) * r["contracts"]
                out.append({
                    "position_id": r["position_id"], "ticker": r["ticker"], "structure": r["structure"],
                    "contracts": r["contracts"], "legs": legs, "spot": spot, "belief": r["belief"],
                    "set_aside": round(r["set_aside"] * r["contracts"], 2),
                    "value": round(r["set_aside"] * r["contracts"] + pnl, 2),
                    "pnl": round(pnl, 2), "pnl_pct": round(pnl / max(1.0, r["set_aside"] * r["contracts"]) * 100, 2),
                    "expiration": max(l["expiration"] for l in legs if l["instrument"] == "option"),
                    "opened_at": r["opened_at"], "estimated": True, "settling": bool(done),
                })
    return out


def close(user_id: str, position_id: str) -> dict:
    eng = _engine()
    with eng._lock:
        with eng._get_db_connection() as conn:
            init(conn)
            r = conn.execute("SELECT * FROM option_positions WHERE position_id = ? AND user_id = ? AND status = 'open'",
                             (position_id, user_id)).fetchone()
            if not r:
                raise PracticeError("That trade is already closed.")
            if _past_expiry(json.loads(r["legs"])):
                raise PracticeError("This trade has expired. It settles at the closing price on expiration day, "
                                    "and the cash comes back once that price is in.")
            spot = float(market.latest_price(r["ticker"]))
            v = unit_value(json.loads(r["legs"]), spot, r["vol"])
            back = _settle(conn, r, v)
            pnl = (v - r["entry_value"]) * r["contracts"]
    return {"status": "success", "cash_back": round(back, 2), "pnl": round(pnl, 2),
            "message": f"Closed. {'Gain' if pnl >= 0 else 'Loss'} of ${abs(pnl):,.0f} (estimated)."}


def outcomes(user_id: str, ids: list[str]) -> dict:
    """What became of these trades (Close Call links its answers to them): money set aside, and once closed or
    settled, the gain on the same cash numbers as the Portfolio's closed list. Read only; settling happens in
    positions(). {position_id: {"cost", "status": "open" | "closed", "pnl", "expired"}}."""
    ids = [i for i in dict.fromkeys(ids or []) if i]
    if not ids:
        return {}
    out = {}
    eng = _engine()
    with eng._get_db_connection() as conn:
        init(conn)
        marks = ",".join("?" for _ in ids)
        rows = conn.execute(f"SELECT * FROM option_positions WHERE user_id = ? AND position_id IN ({marks})",
                            (user_id, *ids)).fetchall()
        for r in rows:
            held = r["set_aside"] * r["contracts"]
            o = {"cost": round(held, 2), "status": r["status"], "pnl": None, "expired": False}
            if r["status"] == "closed":
                back = max(0.0, held + ((r["close_value"] or 0.0) - r["entry_value"]) * r["contracts"])
                o["pnl"] = round(back - held, 2)
                exps = [l["expiration"] for l in json.loads(r["legs"]) if l.get("instrument") == "option"]
                shut = _aware(r["closed_at"])
                o["expired"] = bool(exps and shut and shut >= _expiry_close(date.fromisoformat(max(exps))))
            out[r["position_id"]] = o
    return out


def closed(user_id: str, limit: int = 50) -> list[dict]:
    """Closed or expired option trades, newest first. The gain is the cash that came back minus the cash set aside,
    the same numbers that moved the practice account (so a trade that settled at zero shows its whole set-aside lost)."""
    eng = _engine()
    out = []
    with eng._get_db_connection() as conn:
        init(conn)
        rows = conn.execute("SELECT * FROM option_positions WHERE user_id = ? AND status = 'closed' "
                            "ORDER BY closed_at DESC LIMIT ?", (user_id, limit)).fetchall()
        for r in rows:
            legs = json.loads(r["legs"])
            held = r["set_aside"] * r["contracts"]
            back = max(0.0, held + ((r["close_value"] or 0.0) - r["entry_value"]) * r["contracts"])
            exps = [l["expiration"] for l in legs if l.get("instrument") == "option"]
            exp = max(exps) if exps else None
            shut, opened = _aware(r["closed_at"]), _aware(r["opened_at"])
            # expired = settled at (or after) 4pm New York on expiration day; a close earlier that day is a normal close
            expired = bool(exp and shut and shut >= _expiry_close(date.fromisoformat(exp)))
            out.append({
                "kind": "options", "id": r["position_id"], "ticker": r["ticker"], "structure": r["structure"],
                "contracts": r["contracts"], "legs": legs, "belief": r["belief"] or None,
                "cost": round(held, 2), "proceeds": round(back, 2), "pnl": round(back - held, 2),
                "pnl_pct": round((back - held) / max(1.0, held) * 100, 2),
                "expiration": exp, "expired": expired,
                "opened_at": opened.isoformat() if opened else r["opened_at"],
                "closed_at": shut.isoformat() if shut else r["closed_at"], "estimated": True,
            })
    return out
