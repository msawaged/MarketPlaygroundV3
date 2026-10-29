"""
Practice options: buy or sell a multi-leg options trade with practice money, value it as the stock moves, close it.

Prices are estimates (Black-Scholes on the stock's live price and its 60-day volatility); the app says so. The server
re-prices every leg itself, so the client only chooses which contracts, never what they cost.

Money: opening sets aside the trade's worst case (or its cost, whichever is larger) from practice cash.
Closing returns that amount plus the trade's gain or loss:  cash back = set_aside + (value_now - value_at_open).
At expiration a trade settles automatically at what it's worth on that day.
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime
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


def _clean_legs(raw: list, ticker: str) -> list[dict]:
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
        legs.append({"action": action, "ticker": ticker, "instrument": "option", "option_type": kind.capitalize(),
                     "strike_price": round(k, 2), "expiration": exp.isoformat(), "quantity": qty})
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
    total = 0.0
    for l in legs:
        sign = 1 if l["action"] == "Buy" else -1
        if l["instrument"] == "stock":
            total += sign * spot * l["quantity"]
            continue
        t = max(0, (date.fromisoformat(l["expiration"]) - on).days) / 365.0
        total += sign * bs_price(spot, l["strike_price"], t, vol, l["option_type"].lower()) * 100 * l["quantity"]
    return total


def _priced(legs: list[dict], spot: float, vol: float) -> list[dict]:
    on = market.today()
    out = []
    for l in legs:
        if l["instrument"] == "option":
            t = max(1, (date.fromisoformat(l["expiration"]) - on).days) / 365.0
            l = dict(l, est_premium=round(bs_price(spot, l["strike_price"], t, vol, l["option_type"].lower()), 4))
        out.append(l)
    return out


def quote(ticker: str, legs_in: list) -> dict:
    ticker = (ticker or "").upper().strip()
    if not ticker or not market.asset_info(ticker):
        raise PracticeError("That isn't a stock we can trade.")
    legs = _clean_legs(legs_in, ticker)
    spot = float(market.latest_price(ticker))
    vol = _vol(ticker)
    entry = unit_value(legs, spot, vol)
    worst = float(library.economics(_priced(legs, spot, vol), spot)["max_loss"])
    set_aside = max(entry, worst, 1.0)
    return {"ticker": ticker, "legs": legs, "spot": spot, "vol": vol, "unit_value": entry, "unit_set_aside": set_aside}


def open_trade(user_id: str, ticker: str, structure: str, legs_in: list, contracts: int, belief: str = "") -> dict:
    contracts = int(contracts or 1)
    if not 1 <= contracts <= MAX_CONTRACTS:
        raise PracticeError(f"Choose between 1 and {MAX_CONTRACTS} contracts.")
    q = quote(ticker, legs_in)
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
                          datetime.now().isoformat()))
    return {"status": "success", "position_id": pid, "set_aside": round(need, 2),
            "message": f"Opened {contracts} {q['ticker']} {structure or 'options'} contract{'s' if contracts > 1 else ''} "
                       f"with practice money (about ${need:,.0f} set aside). Prices are estimates."}


def _settle(conn, row, value_now: float, when: Optional[str] = None) -> float:
    back = row["set_aside"] * row["contracts"] + (value_now - row["entry_value"]) * row["contracts"]
    back = max(0.0, back)
    conn.execute("UPDATE users SET cash_balance = cash_balance + ?, buying_power = buying_power + ? WHERE user_id = ?",
                 (Decimal(str(round(back, 2))), Decimal(str(round(back, 2))), row["user_id"]))
    conn.execute("UPDATE option_positions SET status = 'closed', closed_at = ?, close_value = ? WHERE position_id = ?",
                 (when or datetime.now().isoformat(), value_now, row["position_id"]))
    return back


def _expired(legs: list[dict]) -> Optional[date]:
    exps = [date.fromisoformat(l["expiration"]) for l in legs if l["instrument"] == "option"]
    last = max(exps) if exps else None
    return last if last and last <= market.today() else None


def positions(user_id: str) -> list[dict]:
    """Open option trades with what they're worth now. Trades past expiration settle here."""
    eng = _engine()
    out = []
    with eng._lock:
        with eng._get_db_connection() as conn:
            init(conn)
            rows = conn.execute("SELECT * FROM option_positions WHERE user_id = ? AND status = 'open' ORDER BY opened_at DESC",
                                (user_id,)).fetchall()
            for r in rows:
                legs = json.loads(r["legs"])
                try:
                    spot = float(market.latest_price(r["ticker"]))
                except Exception:
                    spot = None
                if spot is None:
                    continue
                exp = _expired(legs)
                v = unit_value(legs, spot, r["vol"], on=exp) if exp else unit_value(legs, spot, r["vol"])
                if exp:
                    _settle(conn, r, v)
                    continue
                pnl = (v - r["entry_value"]) * r["contracts"]
                out.append({
                    "position_id": r["position_id"], "ticker": r["ticker"], "structure": r["structure"],
                    "contracts": r["contracts"], "legs": legs, "spot": spot, "belief": r["belief"],
                    "set_aside": round(r["set_aside"] * r["contracts"], 2),
                    "value": round(r["set_aside"] * r["contracts"] + pnl, 2),
                    "pnl": round(pnl, 2), "pnl_pct": round(pnl / max(1.0, r["set_aside"] * r["contracts"]) * 100, 2),
                    "expiration": max(l["expiration"] for l in legs if l["instrument"] == "option"),
                    "opened_at": r["opened_at"], "estimated": True,
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
            spot = float(market.latest_price(r["ticker"]))
            v = unit_value(json.loads(r["legs"]), spot, r["vol"])
            back = _settle(conn, r, v)
            pnl = (v - r["entry_value"]) * r["contracts"]
    return {"status": "success", "cash_back": round(back, 2), "pnl": round(pnl, 2),
            "message": f"Closed. {'Gain' if pnl >= 0 else 'Loss'} of ${abs(pnl):,.0f} (estimated)."}
