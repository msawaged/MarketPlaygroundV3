"""
Alpaca Order Handler:
- Supports unified trade execution (stocks + options)
- Fetches past orders (all or filled)
"""

import os
import requests
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from backend.broker_interface import BrokerInterface  # Interface for all brokers

# === Load .env for Render and local use ===
dotenv_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=dotenv_path)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# Debug load confirmation
print("ALPACA_API_KEY loaded:", "✅" if ALPACA_API_KEY else "❌ MISSING")
print("ALPACA_SECRET_KEY loaded:", "✅" if ALPACA_SECRET_KEY else "❌ MISSING")

# === Normalization helpers ====================================================

def _pick(d: Dict[str, Any], *paths, default=None):
    """
    Return the first non-empty value from d for any of the given paths.
    Path can be a string key ('symbol') or a tuple for nested ('order','symbol').
    """
    for p in paths:
        cur = d
        if isinstance(p, (list, tuple)):
            ok = True
            for part in p:
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    ok = False
                    break
            if ok and cur not in (None, ""):
                return cur
        else:
            v = d.get(p)
            if v not in (None, ""):
                return v
    return default

def _merge_envelopes(s: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shallow-merge common envelopes into a single dict for easier field picking.
    Does not overwrite existing top-level keys.
    """
    merged = dict(s or {})
    for k in ("strategy_data", "order", "strategy", "order_request"):
        v = s.get(k)
        if isinstance(v, dict):
            for kk, vv in v.items():
                merged.setdefault(kk, vv)
    # ensure legs present if any envelope has them
    if "legs" not in merged:
        for k in ("strategy_data", "order", "strategy", "order_request"):
            v = s.get(k)
            if isinstance(v, dict) and isinstance(v.get("legs"), list):
                merged["legs"] = v["legs"]
                break
    return merged

def _normalize_equity_order(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts any payload shape (top-level, order, strategy_data, strategy, order_request, legs[0])
    and returns Alpaca-ready equity order dict.
    Raises ValueError on missing/invalid essentials.
    """
    p = _merge_envelopes(payload or {})

    # Symbol from many possible locations
    symbol = _pick(
        p,
        "symbol", "ticker",
        ("order", "symbol"),
        ("strategy_data", "symbol"),
        ("strategy", "symbol"),
        ("order_request", "symbol"),
        ("instrument", "symbol"),
        ("asset", "symbol"),
        default=None
    )
    if not symbol and isinstance(p.get("legs"), list) and p["legs"]:
        symbol = p["legs"][0].get("symbol")

    side = (_pick(p, "side", ("order","side"), ("strategy_data","side"), ("strategy","side")) or "").lower()
    raw_qty = _pick(p, "qty", "quantity", "shares", ("order","qty"), ("strategy_data","qty"), ("strategy","qty"))
    typ = (_pick(p, "type", ("order","type"), ("strategy_data","type"), ("strategy","type")) or "market").lower()
    tif = (_pick(p, "time_in_force", "tif", ("order","time_in_force"), ("strategy_data","time_in_force"), ("strategy","time_in_force")) or "gtc").lower()
    lmt = _pick(p, "limit_price", ("order","limit_price"), ("strategy_data","limit_price"), ("strategy","limit_price"))
    stp = _pick(p, "stop_price", ("order","stop_price"), ("strategy_data","stop_price"), ("strategy","stop_price"))

    if not symbol or not isinstance(symbol, str):
        raise ValueError("Missing or invalid symbol")
    if side not in {"buy", "sell"}:
        raise ValueError("side must be 'buy' or 'sell'")

    try:
        qty = int(str(raw_qty)) if raw_qty is not None else 1
        if qty <= 0:
            raise ValueError
    except Exception:
        raise ValueError("qty must be a positive integer")

    order = {
        "symbol": symbol.upper(),
        "side": side,
        "qty": qty,
        "type": typ,
        "time_in_force": tif,
    }
    if lmt is not None:
        order["limit_price"] = float(lmt)
    if stp is not None:
        order["stop_price"] = float(stp)
    return order


class AlpacaExecutor(BrokerInterface):
    """
    Alpaca trade executor for both stocks and options.
    """

    def execute_order(self, strategy: dict, user_id: str = "anonymous") -> dict:
        """
        Accepts either legacy 'strategy' (ticker/direction/asset_class) or
        normalized envelopes (symbol/side/qty/type/time_in_force, possibly nested).
        """
        # Try to infer asset_class if not provided
        asset_class = (strategy or {}).get("asset_class")
        if not asset_class:
            legs = _merge_envelopes(strategy).get("legs")
            asset_class = "options" if isinstance(legs, list) and legs else "stock"

        # === STOCK ORDER LOGIC (normalized first, fallback to legacy) ===
        if asset_class == "stock":
            try:
                # Prefer normalized shape (works with router payload)
                order = _normalize_equity_order(strategy)

                url = f"{ALPACA_BASE_URL}/v2/orders"
                print(f"Alpaca STOCK order payload (normalized): {order}")
                response = requests.post(url, headers=HEADERS, json=order)
                # If Alpaca rejects the order, capture its response body for debugging
                if response.status_code >= 400:
                    try:
                        details = response.json()
                    except Exception:
                        details = {"text": response.text}
                    return {
                        "status": "error",
                        "message": "Alpaca rejected order",
                        "alpaca_status": response.status_code,
                        "alpaca_details": details,
                        "sent_order": order,
                    }

                # Otherwise treat as success
                return {
                    "status": "success",
                    "message": f"{order['side'].upper()} stock order placed for {order['symbol']}",
                    "order": response.json()
                }


            except ValueError as ve:
                # Normalization failed → fall back to legacy fields
                ticker = (strategy or {}).get("ticker")
                direction = (strategy or {}).get("direction", "").lower()
                side = "buy" if ("bull" in direction or "long" in direction) else "sell"
                legacy_payload = {
                    "symbol": ticker,
                    "qty": 1,  # TODO: compute from allocation/balance
                    "side": side,
                    "type": "market",
                    "time_in_force": "gtc",
                }
                print(f"Normalization failed ({ve}); using legacy stock payload: {legacy_payload}")
                try:
                    url = f"{ALPACA_BASE_URL}/v2/orders"
                    response = requests.post(url, headers=HEADERS, json=legacy_payload)
                    response.raise_for_status()
                    return {
                        "status": "success",
                        "message": f"{side.upper()} stock order placed for {ticker}",
                        "order": response.json()
                    }
                except Exception as e:
                    return {
                        "status": "error",
                        "message": f"Failed stock order for {ticker or '(unknown)'}",
                        "error": str(e)
                    }

            except Exception as e:
                # If HTTP call fails even with normalized order, report symbol/ticker cleanly
                sym = None
                try:
                    sym = _normalize_equity_order(strategy)["symbol"]
                except Exception:
                    sym = (strategy or {}).get("ticker")
                return {
                    "status": "error",
                    "message": f"Failed stock order for {sym or '(unknown)'}",
                    "error": str(e)
                }

        # === OPTIONS ORDER LOGIC (kept similar; small hardening) ===
        elif asset_class == "options":
            try:
                description = (strategy.get("description") or "").lower()
                direction = (strategy.get("direction") or "").lower()
                side = "buy_to_open" if ("bull" in direction or "long" in direction) else "sell_to_open"

                contracts = description.split(" / ") if " / " in description else [description]
                orders = []

                for contract in contracts:
                    parts = contract.strip().split()
                    if len(parts) != 3:
                        continue
                    symbol, strike, suffix = parts
                    strike_price = strike.replace("c", "").replace("p", "")
                    option_type = "call" if "c" in strike else "put"

                    order_payload = {
                        "symbol": symbol.upper(),
                        "qty": 1,
                        "side": side,
                        "type": "market",
                        "time_in_force": "gtc",
                        "order_class": "simple",
                        "legs": [
                            {
                                "symbol": symbol.upper(),
                                "qty": 1,
                                "side": side,
                                "option_type": option_type,
                                "strike_price": float(strike_price),
                                "expiration_date": strategy.get("expiry_date"),
                            }
                        ]
                    }

                    print(f"Alpaca OPTIONS order payload: {order_payload}")
                    url = f"{ALPACA_BASE_URL}/v1beta1/options/orders"
                    response = requests.post(url, headers=HEADERS, json=order_payload)
                    response.raise_for_status()
                    orders.append(response.json())

                # Prefer symbol if available; fallback to ticker for message
                merged = _merge_envelopes(strategy)
                ticker = strategy.get("ticker") or merged.get("symbol")
                return {
                    "status": "success",
                    "message": f"Options order(s) placed for {ticker or '(unknown)'}",
                    "order": orders
                }

            except Exception as e:
                merged = _merge_envelopes(strategy)
                ticker = strategy.get("ticker") or merged.get("symbol")
                return {
                    "status": "error",
                    "message": f"Failed options order for {ticker or '(unknown)'}",
                    "error": str(e)
                }

        # === Unknown Asset Class ===
        else:
            return {
                "status": "error",
                "message": f"Unsupported asset class: {asset_class}",
                "error": "Only 'stock' and 'options' supported"
            }


def get_all_orders(status: str = "all", limit: int = 100):
    """
    Fetches all Alpaca stock orders (default: all statuses).
    """
    try:
        url = f"{ALPACA_BASE_URL}/v2/orders"
        params = {"status": status, "limit": limit, "direction": "desc"}
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch Alpaca orders: {e}")
        return []


def get_filled_orders(limit: int = 100):
    """
    Returns only fully filled/completed stock orders.
    """
    all_orders = get_all_orders(status="filled", limit=limit)
    return [o for o in all_orders if o.get("filled_at")]