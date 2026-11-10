"""
Real-money groundwork (Stage 2): people connect their OWN Alpaca brokerage account and approve
every trade. Alpaca holds the money and runs the brokerage; MarketPlayground never touches funds.

SWITCHED OFF by default. Nothing here works until all of these are true:
  - MP_REAL_MONEY=on                         (after a securities lawyer signs off)
  - ALPACA_OAUTH_CLIENT_ID / _SECRET set     (app registered in the Alpaca dashboard; live use
                                              by other people needs Alpaca's approval)
  - MP_BROKER_ENV=paper|live                 (default paper: real accounts' practice side first)
  - optional MP_REAL_MONEY_PILOT=email1,email2  (only these MarketPlayground accounts)

Personal mode (Murad's own account, 2026-11-10): instead of OAuth, the server can hold ONE set of Alpaca API keys
  - MP_BROKER_KEY_ID / MP_BROKER_SECRET_KEY  (kept apart from ALPACA_API_KEY, which is market data only)
  - then MP_REAL_MONEY_PILOT is REQUIRED and only those emails can trade (empty list = nobody, never everybody)

Safety rails:
  - stocks/ETFs: dollar amount (notional) market orders; selling closes what you hold
  - options: single listed contracts only (calls/puts), LIMIT orders, buy to open or sell to close what you hold;
    no selling options you don't own (no naked/uncovered positions), no spreads yet
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
from datetime import date, datetime, timedelta, timezone
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


def keys_mode() -> bool:
    """Personal mode: one Alpaca account's own API keys on the server (no OAuth)."""
    return bool(os.getenv("MP_BROKER_KEY_ID") and os.getenv("MP_BROKER_SECRET_KEY"))


def _pilot_list() -> list[str]:
    return [e.strip().lower() for e in os.getenv("MP_REAL_MONEY_PILOT", "").split(",") if e.strip()]


def _pilot_ok(acc: dict) -> bool:
    pilot = _pilot_list()
    if keys_mode():  # the keys belong to one person: never open them to "everyone"
        return bool(pilot) and acc["email"].lower() in pilot
    return not pilot or acc["email"].lower() in pilot


FUNDING_URL = "https://app.alpaca.markets/"


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
    out["mode"] = "keys" if keys_mode() else "oauth"
    out["funding_url"] = FUNDING_URL
    out["options"] = True
    row = None if keys_mode() else db.query_one("SELECT connected_at, env FROM broker_links WHERE account_id = ?", (acc["id"],))
    if (keys_mode() and out["pilot"]) or (row and row["env"] == env()):
        out["connected"] = True
        out["connected_at"] = row["connected_at"] if row else None
        try:
            a = _alpaca(acc, "GET", "/v2/account")
            out["account"] = {"buying_power": float(a.get("buying_power") or 0), "cash": float(a.get("cash") or 0),
                              "equity": float(a.get("equity") or 0), "status": a.get("status"),
                              "options_buying_power": float(a.get("options_buying_power") or a.get("buying_power") or 0),
                              "options_level": a.get("options_trading_level") if a.get("options_trading_level") is not None else a.get("options_approved_level")}
        except BrokerError as e:
            out["account_error"] = str(e)
    return out


def connect_url(token: Optional[str]) -> str:
    acc = _require(token)
    if keys_mode():
        raise BrokerError("This server uses its own Alpaca keys; there's nothing to connect.", 409)
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


def _alpaca(acc: dict, method: str, path: str, json_body: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    if keys_mode():
        if not _pilot_ok(acc):
            raise BrokerError("Real-money trading is in a small private pilot right now.", 403)
        headers = {"APCA-API-KEY-ID": os.getenv("MP_BROKER_KEY_ID", ""), "APCA-API-SECRET-KEY": os.getenv("MP_BROKER_SECRET_KEY", "")}
    else:
        row = db.query_one("SELECT token_enc FROM broker_links WHERE account_id = ? AND env = ?", (acc["id"], env()))
        if not row:
            raise BrokerError("Connect your Alpaca account first.", 409)
        tok = _fernet().decrypt(row["token_enc"].encode()).decode()
        headers = {"Authorization": f"Bearer {tok}"}
    kw = {"headers": headers, "json": json_body, "timeout": 15}
    if params:
        kw["params"] = params
    r = requests.request(method, api_base() + path, **kw)
    if r.status_code == 401 and keys_mode():
        raise BrokerError("Alpaca didn't accept the server's API keys. Check MP_BROKER_KEY_ID / MP_BROKER_SECRET_KEY.", 502)
    if r.status_code == 404 and method == "GET" and path.startswith("/v2/positions/"):
        return {}
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
            pick_id: Optional[str] = None, tp_pct: Optional[float] = None, sl_pct: Optional[float] = None) -> dict:
    acc = _require(token)
    tp, sl = _exit_pcts(tp_pct, sl_pct)
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
    meta = {"kind": "stock", "underlying": ticker.upper(), "symbol": ticker.upper(), "est_price": price}
    exits_out = None
    if (tp or sl) and side == "buy":
        # Exits live at Alpaca as a bracket (both) or OTO (one) order. Alpaca needs whole shares for those.
        shares = int(amount // price) if price else 0
        if shares < 1:
            raise BrokerError(f"Take-profit and max-loss need at least one whole share. ${amount:,.2f} doesn't buy one "
                              f"{ticker.upper()} share (about ${price:,.2f}).")
        amount = round(shares * price, 2)
        nd = 2 if price >= 1 else 4
        order = {"symbol": ticker.upper(), "side": "buy", "type": "market", "qty": str(shares), "time_in_force": "gtc",
                 "order_class": "bracket" if (tp and sl) else "oto", "client_order_id": f"mp-{pid}"}
        exits_out = {"tp_pct": tp, "sl_pct": sl}
        if tp:
            exits_out["tp_price"] = round(price * (1 + tp), nd)
            order["take_profit"] = {"limit_price": f"{exits_out['tp_price']:.{nd}f}"}
        if sl:
            exits_out["sl_price"] = round(price * (1 - sl), nd)
            order["stop_loss"] = {"stop_price": f"{exits_out['sl_price']:.{nd}f}"}
        meta.update(qty=shares, exits=exits_out)
        warnings.append(f"With exits, this buys {shares} whole share{'s' if shares != 1 else ''} (about ${amount:,.2f}). "
                        "Both exits wait at Alpaca until one fills, even if MarketPlayground is offline; "
                        "they stay until you cancel them in Alpaca's app.")
    _save_preview(pid, acc, ticker.upper(), side, amount, price, belief_id, pick_id, order, meta)
    exit_txt = ""
    if exits_out:
        parts = []
        if tp:
            parts.append(f"sell automatically at ${exits_out['tp_price']:,.2f} (+{tp * 100:g}%)")
        if sl:
            parts.append(f"at ${exits_out['sl_price']:,.2f} (-{sl * 100:g}%) to cap the loss")
        exit_txt = " Then Alpaca will " + " or ".join(parts) + ". A fast drop can sell below the stop price."
    return {
        "exits": exits_out,
        "preview_id": pid, "env": env(), "ticker": ticker.upper(), "name": info.get("name"), "side": side,
        "amount_usd": amount, "est_price": price, "est_shares": round(amount / price, 4) if price else None,
        "buying_power": bp, "expires_in": PREVIEW_SECONDS, "warnings": warnings,
        "market_open": bool(clk.get("is_open")), "next_open": clk.get("next_open"),
        "plain": (f"You'll {'buy' if side == 'buy' else 'sell'} about ${amount:,.2f} of {ticker.upper()} "
                  f"(~{amount / price:.4f} shares at about ${price:,.2f}) in your own Alpaca account. "
                  "The final price can differ a little. You can lose money.") + exit_txt,
    }


def _exit_pcts(tp_pct: Optional[float], sl_pct: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    """Fractions (0.5 = 50%). Take profit 1%..1000%; max loss 1%..95%."""
    tp = float(tp_pct) if tp_pct else None
    sl = float(sl_pct) if sl_pct else None
    if tp is not None and not (0.01 <= tp <= 10):
        raise BrokerError("Take profit must be between +1% and +1000%.")
    if sl is not None and not (0.01 <= sl <= 0.95):
        raise BrokerError("Max loss must be between 1% and 95%.")
    return tp, sl


def _clear_exits_for_sale(acc: dict, symbol: str) -> None:
    """Selling by hand: open stop/take-profit sells hold the shares or contracts, so cancel them first and turn the
    exits off (the person is closing the position themselves)."""
    try:
        open_orders = _alpaca(acc, "GET", "/v2/orders", params={"status": "open", "symbols": symbol, "nested": "true"}) or []
    except BrokerError:
        open_orders = []
    flat = []
    for o in open_orders if isinstance(open_orders, list) else []:
        flat.append(o)
        flat.extend(o.get("legs") or [])
    cancelled = 0
    for o in flat:
        if o.get("symbol") == symbol and o.get("side") == "sell" and o.get("id"):
            try:
                _alpaca(acc, "DELETE", f"/v2/orders/{o['id']}")
                cancelled += 1
            except BrokerError:
                pass
    db.execute("UPDATE broker_exits SET status = 'cancelled', note = ?, updated_at = ? WHERE account_id = ? AND symbol = ? "
               "AND status IN ('at_alpaca','waiting_fill','armed','tp_sent')",
               ("Replaced by your own sale.", _now().isoformat(), acc["id"], symbol))
    if cancelled:
        import time as _t
        _t.sleep(1.5)  # let Alpaca release the held shares/contracts


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
        req = db.loads(row["request"]) or {}
        if row["side"] == "sell":
            _clear_exits_for_sale(acc, row["ticker"])
        res = _alpaca(acc, "POST", "/v2/orders", req.get("order", req))
    except BrokerError as e:
        db.execute("UPDATE broker_orders SET status = 'rejected', response = ? WHERE id = ?", (db.dumps({"error": str(e)}), preview_id))
        raise
    db.execute("UPDATE broker_orders SET status = 'sent', response = ? WHERE id = ?", (db.dumps(res), preview_id))
    try:
        from . import exits
        exits.on_placed(acc, req.get("meta") or {}, res)
    except Exception as e:  # the order is already at Alpaca; say so rather than fail
        print(f"[broker] exits not recorded for {preview_id}: {e}")
        return {"status": "sent", "order_id": res.get("id"), "alpaca_status": res.get("status"), "env": env(),
                "warning": "The order was sent, but its take-profit/max-loss couldn't be saved. Set them in Alpaca's app."}
    return {"status": "sent", "order_id": res.get("id"), "alpaca_status": res.get("status"), "env": env()}


# ---------------------------------------------------------------------------------------------------------------
# Shared helpers, options, closing positions, order sync, and the public "real-money journey" (2026-11-10)
# ---------------------------------------------------------------------------------------------------------------
MAX_CONTRACTS = 20
_FINAL = {"filled", "canceled", "expired", "rejected", "replaced", "done_for_day", "stopped", "suspended"}


def _spy() -> Optional[float]:
    try:
        return float(market.latest_price("SPY"))
    except Exception:
        return None


def _save_preview(pid: str, acc: dict, symbol: str, side: str, notional: float, est_price: Optional[float],
                  belief_id: Optional[str], pick_id: Optional[str], order: dict, meta: dict) -> None:
    meta = dict(meta, spy=_spy())
    db.execute("INSERT INTO broker_orders (id, account_id, env, created_at, status, ticker, side, notional, est_price, belief_id, pick_id, request, response) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (pid, acc["id"], env(), _now().isoformat(), "previewed", symbol, side, notional, est_price, belief_id, pick_id,
                db.dumps({"order": order, "meta": meta}), None))


def _fmt_date(d) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def option_label(symbol: str, qty: Optional[float] = None) -> str:
    o = market.parse_occ(symbol)
    if not o:
        return symbol
    n = "" if qty is None else f"{qty:g} "
    plural = "s" if qty is not None and qty != 1 else ""
    return f"{n}{o['underlying']} ${o['strike']:g} {o['type']}{plural} expiring {_fmt_date(o['expiration'])}"


def _closed_warning() -> list[str]:
    clk = market.clock()
    if clk.get("is_open"):
        return []
    return [f"The market is closed. The order waits for the open ({_when(clk.get('next_open'))}); prices can be very different by then."]


def _find_contract(acc: dict, underlying: str, kind: str, strike: float, expiration: date) -> dict:
    js = _alpaca(acc, "GET", "/v2/options/contracts", params={
        "underlying_symbols": underlying, "type": kind, "status": "active", "limit": 500,
        "expiration_date_gte": max(date.today() + timedelta(days=1), expiration - timedelta(days=10)).isoformat(),
        "expiration_date_lte": (expiration + timedelta(days=10)).isoformat(),
        "strike_price_gte": f"{strike * 0.9:.2f}", "strike_price_lte": f"{strike * 1.1:.2f}"})
    rows = [c for c in (js.get("option_contracts") or []) if c.get("tradable", True) and c.get("symbol")]
    if not rows:
        raise BrokerError(f"No listed {underlying} {kind} near ${strike:g} expiring around {_fmt_date(expiration)} can be traded right now.")

    def dist(c):
        exp = date.fromisoformat(str(c["expiration_date"])[:10])
        return abs((exp - expiration).days) / 30.0 + abs(float(c["strike_price"]) - strike) / max(strike, 1.0) * 10
    return min(rows, key=dist)


def preview_option(token: Optional[str], underlying: str, option_type: str, strike: float, expiration: str,
                   contracts: int = 1, limit_price: Optional[float] = None, belief_id: Optional[str] = None,
                   pick_id: Optional[str] = None, tp_pct: Optional[float] = None, sl_pct: Optional[float] = None) -> dict:
    """Buy to open ONE kind of listed call or put, with a limit price. The most you can lose is what you pay."""
    acc = _require(token)
    tp, sl = _exit_pcts(tp_pct, sl_pct)
    kind = (option_type or "").lower()
    if kind not in ("call", "put"):
        raise BrokerError("Options here are single calls or puts.")
    qty = int(contracts or 0)
    if qty < 1 or qty > MAX_CONTRACTS:
        raise BrokerError(f"Choose between 1 and {MAX_CONTRACTS} contracts.")
    try:
        exp = date.fromisoformat(str(expiration)[:10])
    except ValueError:
        raise BrokerError("That idea is missing an expiration date.")
    u = underlying.upper().strip()
    c = _find_contract(acc, u, kind, float(strike), exp)
    sym = c["symbol"]
    real_k, real_exp = float(c["strike_price"]), date.fromisoformat(str(c["expiration_date"])[:10])
    q = market.option_quote(sym)
    if not q or q["ask"] <= 0:
        raise BrokerError(f"There's no live asking price for {option_label(sym)} right now. Try again during market hours.")
    lp = round(float(limit_price), 2) if limit_price else round(q["ask"], 2)
    if lp <= 0:
        raise BrokerError("The limit price must be above $0.")
    cost = round(qty * 100 * lp, 2)
    if cost > max_order():
        most = int(max_order() // (100 * lp))
        raise BrokerError(f"That's ${cost:,.2f}. During the pilot the largest order is ${max_order():,.0f}"
                          + (f" ({most} contract{'s' if most != 1 else ''} at this price)." if most >= 1 else ", and one contract costs more than that."))
    a = _alpaca(acc, "GET", "/v2/account")
    obp = float(a.get("options_buying_power") or a.get("buying_power") or 0)
    if cost > obp:
        raise BrokerError(f"That's more than your options buying power (${obp:,.2f}).")
    warnings = _closed_warning()
    if abs(real_k - float(strike)) > 0.005 or real_exp != exp:
        warnings.append(f"The idea used a ${float(strike):g} strike expiring {_fmt_date(exp)}. The closest listed contract is "
                        f"${real_k:g} expiring {_fmt_date(real_exp)}, so the numbers differ a little from the idea card.")
    days = (real_exp - date.today()).days
    if days <= 14:
        warnings.append(f"This contract expires in {days} day{'s' if days != 1 else ''}. Options this close to expiring can lose all their value fast.")
    if q["bid"] > 0 and (q["ask"] - q["bid"]) / ((q["ask"] + q["bid"]) / 2) > 0.15:
        warnings.append(f"Wide gap between buyers (${q['bid']:.2f}) and sellers (${q['ask']:.2f}). Selling later may cost you a lot of that gap.")
    if lp > q["ask"] * 1.05:
        warnings.append(f"Your limit (${lp:.2f}) is above the current asking price (${q['ask']:.2f}).")
    if lp < q["bid"]:
        warnings.append("Your limit is below what buyers are paying, so it probably won't fill.")
    if cost > 0.25 * float(a.get("equity") or cost):
        warnings.append("This is more than a quarter of your account. Consider a smaller amount.")
    be = real_k + lp if kind == "call" else real_k - lp
    pid = f"pv-{uuid.uuid4().hex[:16]}"
    order = {"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit", "limit_price": f"{lp:.2f}",
             "time_in_force": "day", "client_order_id": f"mp-{pid}"}
    meta = {"kind": "option", "underlying": u, "symbol": sym, "type": kind, "strike": real_k, "expiration": real_exp.isoformat(),
            "qty": qty, "est_price": lp}
    exits_out, exit_txt = None, ""
    if tp or sl:
        exits_out = {"tp_pct": tp, "sl_pct": sl, "tp_price": round(lp * (1 + tp), 2) if tp else None,
                     "sl_price": max(0.01, round(lp * (1 - sl), 2)) if sl else None}
        meta["exits"] = {"tp_pct": tp, "sl_pct": sl}  # prices are set from the real fill
        parts = []
        if sl:
            parts.append(f"a max-loss stop at about ${exits_out['sl_price']:.2f} (-{sl * 100:g}%) waits at Alpaca, renewed each "
                         "trading morning (option orders only last a day)")
        if tp:
            parts.append(f"MarketPlayground watches for about ${exits_out['tp_price']:.2f} (+{tp * 100:g}%) and sells when buyers "
                         "pay that, usually within seconds during market hours")
        exit_txt = " After it fills, " + "; ".join(parts) + ". Exact levels are set from your real fill price."
        warnings.append("Option stops sell at the market once triggered, so a fast drop or a wide gap can sell for less than the stop price.")
    _save_preview(pid, acc, sym, "buy", cost, lp, belief_id, pick_id, order, meta)
    return {
        "exits": exits_out,
        "preview_id": pid, "env": env(), "kind": "option", "contract": sym, "label": option_label(sym, qty),
        "side": "buy", "contracts": qty, "limit_price": lp, "bid": q["bid"], "ask": q["ask"], "total_usd": cost,
        "amount_usd": cost, "max_loss_usd": cost, "breakeven": round(be, 2), "expires_in": PREVIEW_SECONDS,
        "warnings": warnings, "buying_power": obp,
        "plain": (f"You'll buy {option_label(sym, qty)} at up to ${lp:.2f} a share (${lp * 100:,.2f} per contract): "
                  f"${cost:,.2f} at most, in your own Alpaca account. That's also the most you can lose. "
                  f"You make money at expiration only if {u} is {'above' if kind == 'call' else 'below'} ${be:,.2f}. "
                  "It's a limit order, so you never pay more than your limit, but it may not fill.") + exit_txt,
    }


def positions(token: Optional[str]) -> list[dict]:
    acc = _require(token)
    out = []
    for p in _alpaca(acc, "GET", "/v2/positions") or []:
        sym, qty = p.get("symbol", ""), float(p.get("qty") or 0)
        is_opt = p.get("asset_class") == "us_option" or market.parse_occ(sym) is not None
        out.append({"symbol": sym, "kind": "option" if is_opt else "stock", "qty": qty,
                    "label": option_label(sym, qty) if is_opt else f"{qty:g} share{'s' if qty != 1 else ''} of {sym}",
                    "avg_entry_price": float(p.get("avg_entry_price") or 0), "current_price": float(p.get("current_price") or 0),
                    "market_value": float(p.get("market_value") or 0), "unrealized_pl": float(p.get("unrealized_pl") or 0),
                    "unrealized_plpc": float(p.get("unrealized_plpc") or 0)})
    return out


def preview_close(token: Optional[str], symbol: str, qty: Optional[float] = None, limit_price: Optional[float] = None) -> dict:
    """Sell something you hold (all of it by default). Never opens a short or an uncovered option."""
    acc = _require(token)
    sym = (symbol or "").upper().strip()
    p = _alpaca(acc, "GET", f"/v2/positions/{sym}")
    held = float(p.get("qty") or 0) if p else 0.0
    if held <= 0:
        raise BrokerError(f"You don't hold any {sym} to sell.")
    n = held if not qty else float(qty)
    if n <= 0 or n > held + 1e-9:
        raise BrokerError(f"You hold {held:g}; you can sell up to that.")
    warnings = _closed_warning()
    pid = f"pv-{uuid.uuid4().hex[:16]}"
    o = market.parse_occ(sym)
    if o:
        n = int(n)
        if n < 1:
            raise BrokerError("Options sell in whole contracts.")
        q = market.option_quote(sym)
        if not q or q["bid"] <= 0:
            raise BrokerError(f"Nobody is bidding on {option_label(sym)} right now, so it can't be sold at a fair price. Try during market hours.")
        lp = round(float(limit_price), 2) if limit_price else round(q["bid"], 2)
        est = round(n * 100 * lp, 2)
        if lp > q["ask"] > 0:
            warnings.append("Your limit is above what sellers are asking, so it probably won't fill.")
        order = {"symbol": sym, "qty": str(n), "side": "sell", "type": "limit", "limit_price": f"{lp:.2f}",
                 "time_in_force": "day", "client_order_id": f"mp-{pid}"}
        _save_preview(pid, acc, sym, "sell", est, lp, None, None, order,
                      {"kind": "option", "underlying": o["underlying"], "type": o["type"], "strike": o["strike"],
                       "expiration": o["expiration"].isoformat(), "qty": n})
        plain = (f"You'll sell {option_label(sym, n)} at no less than ${lp:.2f} a share (about ${est:,.2f} in total). "
                 "It's a limit order, so it may not fill if prices move.")
        return {"preview_id": pid, "env": env(), "kind": "option", "side": "sell", "contract": sym, "label": option_label(sym, n),
                "contracts": n, "limit_price": lp, "bid": q["bid"], "ask": q["ask"], "amount_usd": est, "total_usd": est,
                "expires_in": PREVIEW_SECONDS, "warnings": warnings, "plain": plain}
    price = market.latest_price(sym)
    est = round(n * price, 2)
    order = {"symbol": sym, "qty": f"{n:g}", "side": "sell", "type": "market", "time_in_force": "day", "client_order_id": f"mp-{pid}"}
    _save_preview(pid, acc, sym, "sell", est, price, None, None, order, {"kind": "stock", "underlying": sym, "qty": n})
    return {"preview_id": pid, "env": env(), "kind": "stock", "side": "sell", "ticker": sym, "shares": n, "est_price": price,
            "amount_usd": est, "expires_in": PREVIEW_SECONDS, "warnings": warnings,
            "plain": (f"You'll sell {n:g} share{'s' if n != 1 else ''} of {sym} (about ${est:,.2f} at ${price:,.2f}) at the market price "
                      "in your own Alpaca account. The final price can differ a little.")}


def _sync(acc: dict, limit: int = 60) -> None:
    rows = db.query("SELECT id, response FROM broker_orders WHERE account_id = ? AND env = ? AND status = 'sent' ORDER BY created_at DESC",
                    (acc["id"], env()))[:limit]
    for r in rows:
        res = db.loads(r["response"]) or {}
        if not res.get("id") or res.get("status") in _FINAL:
            continue
        try:
            fresh = _alpaca(acc, "GET", f"/v2/orders/{res['id']}")
        except BrokerError:
            continue
        if fresh:
            db.execute("UPDATE broker_orders SET response = ? WHERE id = ?", (db.dumps(fresh), r["id"]))


def _order_rows(acc: dict) -> list[dict]:
    out = []
    for r in db.query("SELECT * FROM broker_orders WHERE account_id = ? AND env = ? AND status = 'sent' ORDER BY created_at",
                      (acc["id"], env())):
        req, res = db.loads(r["request"]) or {}, db.loads(r["response"]) or {}
        meta = req.get("meta") or {"kind": "option" if market.parse_occ(r["ticker"]) else "stock", "underlying": r["ticker"]}
        out.append({"id": r["id"], "created_at": r["created_at"], "symbol": r["ticker"], "side": r["side"], "meta": meta,
                    "belief_id": r["belief_id"], "status": res.get("status"),
                    "filled_qty": float(res.get("filled_qty") or 0), "filled_avg_price": float(res.get("filled_avg_price") or 0),
                    "filled_at": res.get("filled_at") or res.get("updated_at") or r["created_at"]})
    return out


def orders(token: Optional[str]) -> list[dict]:
    acc = _require(token)
    _sync(acc)
    rows = _order_rows(acc)
    for o in rows:
        o["label"] = option_label(o["symbol"], o["filled_qty"] or o["meta"].get("qty")) if o["meta"].get("kind") == "option" else o["symbol"]
    return list(reversed(rows))[:40]


def build_lots(fills: list[dict]) -> list[dict]:
    """FIFO lots from filled orders: every buy opens a lot, sells close the oldest lots first (partially if needed).
    Pure function so it can be tested. fills: {symbol, side, qty, price, at, spy, kind, belief_id}."""
    open_by: dict[str, list[dict]] = {}
    lots: list[dict] = []
    for f in sorted(fills, key=lambda x: x["at"]):
        if f["side"] == "buy":
            lot = {"symbol": f["symbol"], "kind": f["kind"], "qty": f["qty"], "entry": f["price"], "opened": f["at"],
                   "spy_entry": f.get("spy"), "belief_id": f.get("belief_id"), "closed": None, "exit": None, "spy_exit": None}
            lots.append(lot)
            open_by.setdefault(f["symbol"], []).append(lot)
            continue
        left = f["qty"]
        queue = open_by.get(f["symbol"], [])
        while left > 1e-9 and queue:
            lot = queue[0]
            take = min(left, lot["qty"])
            if take < lot["qty"] - 1e-9:  # split: the sold part closes, the rest stays open
                rest = dict(lot, qty=lot["qty"] - take)
                lot["qty"] = take
                lots.insert(next(i for i, x in enumerate(lots) if x is lot) + 1, rest)
                queue[0] = rest
            else:
                queue.pop(0)
            lot.update(closed=f["at"], exit=f["price"], spy_exit=f.get("spy"))
            left -= take
    return lots


def _owner() -> Optional[dict]:
    pilot = _pilot_list()
    if not pilot:
        return None
    return db.query_one("SELECT * FROM accounts WHERE lower(email) = ?", (pilot[0],))


_journey_cache: dict = {}


def journey_enabled() -> bool:
    return enabled() and os.getenv("MP_JOURNEY_PUBLIC", "off").lower() in ("on", "true", "1", "yes")


def journey() -> dict:
    """Public record of the owner's real-money trades: every filled trade, wins and losses, nothing hidden.
    Percentages only unless MP_JOURNEY_SHOW_DOLLARS=on. Cached for 60s."""
    import time as _t
    if not journey_enabled():
        return {"enabled": False}
    hit = _journey_cache.get("j")
    if hit and _t.time() - hit[0] < 60:
        return hit[1]
    acc = _owner()
    if not acc:
        return {"enabled": False}
    try:
        _sync(acc)
    except BrokerError:
        pass
    fills = []
    for o in _order_rows(acc):
        if o["filled_qty"] <= 0 or o["filled_avg_price"] <= 0:
            continue
        fills.append({"symbol": o["symbol"], "side": o["side"], "qty": o["filled_qty"], "price": o["filled_avg_price"],
                      "at": o["filled_at"], "spy": o["meta"].get("spy"), "kind": o["meta"].get("kind", "stock"), "belief_id": o["belief_id"]})
    lots = build_lots(fills)
    spy_now = _spy()
    dollars = os.getenv("MP_JOURNEY_SHOW_DOLLARS", "off").lower() in ("on", "true", "1", "yes")
    out_lots, invested, gained = [], 0.0, 0.0
    for lot in lots:
        mult = 100 if lot["kind"] == "option" else 1
        if lot["closed"]:
            px, spy_end = lot["exit"], lot["spy_exit"]
        else:
            if lot["kind"] == "option":
                q = market.option_quote(lot["symbol"])
                px = q["mid"] if q else None
            else:
                try:
                    px = market.latest_price(lot["symbol"])
                except Exception:
                    px = None
            spy_end = spy_now
        ret = (px / lot["entry"] - 1) if px else None
        spy_ret = (spy_end / lot["spy_entry"] - 1) if spy_end and lot["spy_entry"] else None
        cost = lot["qty"] * lot["entry"] * mult
        if ret is not None:
            invested += cost
            gained += cost * ret
        belief = db.query_one("SELECT text FROM beliefs WHERE id = ?", (lot["belief_id"],)) if lot["belief_id"] else None
        row = {"symbol": lot["symbol"], "kind": lot["kind"],
               "label": option_label(lot["symbol"]) if lot["kind"] == "option" else lot["symbol"],
               "opened": lot["opened"], "closed": lot["closed"], "status": "closed" if lot["closed"] else "open",
               "entry": round(lot["entry"], 4), "now_or_exit": round(px, 4) if px else None,
               "return": round(ret, 4) if ret is not None else None, "spy_return": round(spy_ret, 4) if spy_ret is not None else None,
               "vs_spy": round(ret - spy_ret, 4) if ret is not None and spy_ret is not None else None,
               "belief": belief["text"] if belief else None}
        if dollars:
            row.update(cost_usd=round(cost, 2), pl_usd=round(cost * ret, 2) if ret is not None else None)
        out_lots.append(row)
    closed = [l for l in out_lots if l["status"] == "closed" and l["return"] is not None]
    res = {"enabled": True, "env": env(), "name": (acc.get("name") or "").split(" ")[0] or None,
           "started": out_lots[0]["opened"] if out_lots else None, "trades": len(fills),
           "summary": {"positions": len(out_lots), "open": sum(1 for l in out_lots if l["status"] == "open"),
                       "closed": len(closed), "wins": sum(1 for l in closed if l["return"] > 0),
                       "return_on_invested": round(gained / invested, 4) if invested else None},
           "lots": list(reversed(out_lots)), "dollars": dollars, "as_of": _now().isoformat()}
    if dollars:
        res["summary"].update(invested_usd=round(invested, 2), pl_usd=round(gained, 2))
    _journey_cache["j"] = (_t.time(), res)
    return res
