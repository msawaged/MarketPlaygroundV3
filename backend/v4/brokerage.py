"""
Real-money groundwork (Stage 2): people connect their OWN Alpaca brokerage account and approve
every trade. Alpaca holds the money and runs the brokerage; MarketPlayground never touches funds.

SWITCHED OFF by default. Nothing here works until all of these are true:
  - MP_REAL_MONEY=on                         (after a securities lawyer signs off)
  - ALPACA_OAUTH_CLIENT_ID / _SECRET set     (app registered in the Alpaca dashboard; live use
                                              by other people needs Alpaca's approval)
  - MP_BROKER_ENV=paper|live                 (default paper: real accounts' practice side first)
  - optional MP_REAL_MONEY_PILOT=email1,email2  (only these MarketPlayground accounts)

Safety rails:
  - stocks/ETFs only (no options), buy or sell, dollar amount (notional) market orders
  - every order is previewed first; the preview expires after 2 minutes and must be confirmed
  - per-order cap MP_MAX_ORDER_USD (default 1000)
  - access tokens are encrypted at rest (key from MP_TOKEN_KEY); every order is logged
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import requests

from . import auth, db, market

AUTHORIZE_URL = "https://app.alpaca.markets/oauth/authorize"
TOKEN_URL = "https://api.alpaca.markets/oauth/token"
PREVIEW_SECONDS = 120


class BrokerError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enabled() -> bool:
    return os.getenv("MP_REAL_MONEY", "off").lower() in ("on", "true", "1", "yes")


def env() -> str:
    return "live" if os.getenv("MP_BROKER_ENV", "paper").lower() == "live" else "paper"


def api_base() -> str:
    return "https://api.alpaca.markets" if env() == "live" else "https://paper-api.alpaca.markets"


def max_order() -> float:
    return float(os.getenv("MP_MAX_ORDER_USD", "1000"))


def _pilot_ok(acc: dict) -> bool:
    pilot = [e.strip().lower() for e in os.getenv("MP_REAL_MONEY_PILOT", "").split(",") if e.strip()]
    return not pilot or acc["email"].lower() in pilot


def _fernet():
    from cryptography.fernet import Fernet
    secret = os.getenv("MP_TOKEN_KEY") or os.getenv("MP_ADMIN_TOKEN")
    if not secret:
        raise BrokerError("Server is missing MP_TOKEN_KEY.", 503)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def _require(token: Optional[str]) -> dict:
    if not enabled():
        raise BrokerError("Real-money trading isn't available yet. It's coming after the beta.", 403)
    try:
        acc = auth.require(token)
    except auth.AuthError as e:
        raise BrokerError(str(e), e.status)
    if not _pilot_ok(acc):
        raise BrokerError("Real-money trading is in a small private pilot right now.", 403)
    return acc


def status(token: Optional[str]) -> dict:
    out = {"enabled": enabled(), "env": env(), "max_order_usd": max_order(), "connected": False}
    if not enabled():
        return out
    acc = auth.account_for_token(token)
    if not acc:
        return out
    out["pilot"] = _pilot_ok(acc)
    row = db.query_one("SELECT connected_at, env FROM broker_links WHERE account_id = ?", (acc["id"],))
    if row and row["env"] == env():
        out["connected"] = True
        out["connected_at"] = row["connected_at"]
        try:
            a = _alpaca(acc, "GET", "/v2/account")
            out["account"] = {"buying_power": float(a.get("buying_power") or 0), "cash": float(a.get("cash") or 0),
                              "equity": float(a.get("equity") or 0), "status": a.get("status")}
        except BrokerError as e:
            out["account_error"] = str(e)
    return out


def connect_url(token: Optional[str]) -> str:
    acc = _require(token)
    cid = os.getenv("ALPACA_OAUTH_CLIENT_ID")
    if not cid:
        raise BrokerError("Server is missing ALPACA_OAUTH_CLIENT_ID.", 503)
    state = secrets.token_urlsafe(24)
    db.execute("DELETE FROM kv_cache WHERE k = ?", (f"oauth:{state}",))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (f"oauth:{state}", acc["id"], _now().isoformat()))
    return AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": os.getenv("ALPACA_OAUTH_REDIRECT_URI", ""),
        "state": state, "scope": "account:write trading", "env": env(),
    })


def finish_connect(code: str, state: str) -> str:
    """OAuth callback. Returns the account id that connected."""
    row = db.query_one("SELECT v, created_at FROM kv_cache WHERE k = ?", (f"oauth:{state}",))
    db.execute("DELETE FROM kv_cache WHERE k = ?", (f"oauth:{state}",))
    if not row or row["created_at"] < (_now() - timedelta(minutes=15)).isoformat():
        raise BrokerError("That connection link expired. Please try again.", 400)
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": code,
        "client_id": os.getenv("ALPACA_OAUTH_CLIENT_ID", ""), "client_secret": os.getenv("ALPACA_OAUTH_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("ALPACA_OAUTH_REDIRECT_URI", ""),
    }, timeout=15)
    if r.status_code != 200:
        raise BrokerError("Alpaca didn't accept the connection. Please try again.", 502)
    tok = r.json().get("access_token")
    if not tok:
        raise BrokerError("Alpaca didn't return an access token.", 502)
    enc = _fernet().encrypt(tok.encode()).decode()
    db.execute("DELETE FROM broker_links WHERE account_id = ?", (row["v"],))
    db.execute("INSERT INTO broker_links (account_id, broker, env, token_enc, connected_at) VALUES (?,?,?,?,?)",
               (row["v"], "alpaca", env(), enc, _now().isoformat()))
    return row["v"]


def disconnect(token: Optional[str]) -> None:
    acc = auth.require(token)
    db.execute("DELETE FROM broker_links WHERE account_id = ?", (acc["id"],))


def _alpaca(acc: dict, method: str, path: str, json_body: Optional[dict] = None) -> dict:
    row = db.query_one("SELECT token_enc FROM broker_links WHERE account_id = ? AND env = ?", (acc["id"], env()))
    if not row:
        raise BrokerError("Connect your Alpaca account first.", 409)
    tok = _fernet().decrypt(row["token_enc"].encode()).decode()
    r = requests.request(method, api_base() + path, headers={"Authorization": f"Bearer {tok}"}, json=json_body, timeout=15)
    if r.status_code == 401:
        db.execute("DELETE FROM broker_links WHERE account_id = ?", (acc["id"],))
        raise BrokerError("Your Alpaca connection expired. Please connect again.", 401)
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text
        except Exception:
            msg = r.text
        raise BrokerError(f"Alpaca said: {msg}", 400)
    return r.json() if r.content else {}


def preview(token: Optional[str], ticker: str, side: str, amount_usd: float, belief_id: Optional[str] = None,
            pick_id: Optional[str] = None) -> dict:
    acc = _require(token)
    side = (side or "").lower()
    if side not in ("buy", "sell"):
        raise BrokerError("Side must be buy or sell.")
    amount = round(float(amount_usd or 0), 2)
    if amount < 1:
        raise BrokerError("The smallest order is $1.")
    if amount > max_order():
        raise BrokerError(f"During the pilot the largest order is ${max_order():,.0f}.")
    info = market.asset_info(ticker.upper())
    if not info or not info.get("tradable"):
        raise BrokerError(f"{ticker.upper()} can't be traded right now.")
    price = market.latest_price(ticker.upper())
    a = _alpaca(acc, "GET", "/v2/account")
    bp = float(a.get("buying_power") or 0)
    warnings = []
    if side == "buy" and amount > bp:
        raise BrokerError(f"That's more than your buying power (${bp:,.2f}).")
    if side == "buy" and amount > 0.25 * float(a.get("equity") or amount):
        warnings.append("This is more than a quarter of your account. Consider a smaller amount.")
    clk = market.clock()
    if not clk.get("is_open"):
        warnings.insert(0, f"The market is closed. This order will wait and fill when it opens ({_when(clk.get('next_open'))}). "
                           "Prices can jump overnight, so the price you get may be very different from now.")
    pid = f"pv-{uuid.uuid4().hex[:16]}"
    order = {"symbol": ticker.upper(), "side": side, "type": "market", "time_in_force": "day",
             "notional": f"{amount:.2f}", "client_order_id": f"mp-{pid}"}
    db.execute("INSERT INTO broker_orders (id, account_id, env, created_at, status, ticker, side, notional, est_price, belief_id, pick_id, request, response) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (pid, acc["id"], env(), _now().isoformat(), "previewed", ticker.upper(), side, amount, price, belief_id, pick_id, db.dumps(order), None))
    return {
        "preview_id": pid, "env": env(), "ticker": ticker.upper(), "name": info.get("name"), "side": side,
        "amount_usd": amount, "est_price": price, "est_shares": round(amount / price, 4) if price else None,
        "buying_power": bp, "expires_in": PREVIEW_SECONDS, "warnings": warnings,
        "market_open": bool(clk.get("is_open")), "next_open": clk.get("next_open"),
        "plain": (f"You'll {'buy' if side == 'buy' else 'sell'} about ${amount:,.2f} of {ticker.upper()} "
                  f"(~{amount / price:.4f} shares at about ${price:,.2f}) in your own Alpaca account. "
                  "The final price can differ a little. You can lose money."),
    }


def _when(iso: Optional[str]) -> str:
    """'Thursday 9:30am ET' from an ISO time."""
    try:
        d = datetime.fromisoformat((iso or "").replace("Z", "+00:00")).astimezone(market.NY)
        return d.strftime("%A %-I:%M%p").replace("AM", "am").replace("PM", "pm") + " ET"
    except Exception:
        return "next trading day, 9:30am ET"


def place(token: Optional[str], preview_id: str, confirm: bool) -> dict:
    acc = _require(token)
    if not confirm:
        raise BrokerError("Please confirm the order.")
    row = db.query_one("SELECT * FROM broker_orders WHERE id = ? AND account_id = ?", (preview_id, acc["id"]))
    if not row:
        raise BrokerError("That order preview wasn't found.", 404)
    if row["status"] != "previewed":
        raise BrokerError("That order was already sent.", 409)
    if row["created_at"] < (_now() - timedelta(seconds=PREVIEW_SECONDS)).isoformat():
        db.execute("UPDATE broker_orders SET status = 'expired' WHERE id = ?", (preview_id,))
        raise BrokerError("That preview expired. Prices move, so please preview again.", 410)
    claimed = db.execute("UPDATE broker_orders SET status = 'sending' WHERE id = ? AND status = 'previewed'", (preview_id,))
    if claimed != 1:
        raise BrokerError("That order was already sent.", 409)  # two taps at once: only one goes through
    try:
        res = _alpaca(acc, "POST", "/v2/orders", db.loads(row["request"]))
    except BrokerError as e:
        db.execute("UPDATE broker_orders SET status = 'rejected', response = ? WHERE id = ?", (db.dumps({"error": str(e)}), preview_id))
        raise
    db.execute("UPDATE broker_orders SET status = 'sent', response = ? WHERE id = ?", (db.dumps(res), preview_id))
    return {"status": "sent", "order_id": res.get("id"), "alpaca_status": res.get("status"), "env": env()}
