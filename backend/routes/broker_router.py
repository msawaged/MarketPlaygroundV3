"""
broker_router.py
----------------
MarketPlayground-branded proxy endpoints that call Alpaca using the
user's stored token (via token_store). Paper vs live picked by 'env'.

Frontend calls only these routes. Your backend attaches tokens and
talks to Alpaca's Trading/Data APIs.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.broker.providers import alpaca_api

router = APIRouter(prefix="/broker", tags=["Broker"])

@router.get("/account")
def broker_account(user_id: str, env: str = Query("paper", pattern="^(paper|live)$")):
    status, payload = alpaca_api(user_id, env, "GET", "/v2/account")
    if status >= 400:
        raise HTTPException(status_code=status, detail=payload)
    # Return a trimmed payload your UI can use easily
    acc = payload if isinstance(payload, dict) else {}
    masked = (acc.get("account_number") or "XXXX")[-4:]
    return {
        "env": env,
        "id": acc.get("id"),
        "account_number_masked": f"****{masked}",
        "status": acc.get("status"),
        "currency": acc.get("currency"),
        "buying_power": acc.get("buying_power"),
        "equity": acc.get("equity") or acc.get("portfolio_value"),
        "raw": acc,  # keep for now; you can drop later
    }

@router.get("/positions")
def broker_positions(user_id: str, env: str = Query("paper", pattern="^(paper|live)$")):
    status, payload = alpaca_api(user_id, env, "GET", "/v2/positions")
    if status >= 400:
        raise HTTPException(status_code=status, detail=payload)
    return {"env": env, "positions": payload}

@router.get("/orders")
def broker_orders(user_id: str, env: str = Query("paper", pattern="^(paper|live)$"), status_filter: Optional[str] = None, limit: int = 50):
    params = {"limit": str(limit)}
    if status_filter:
        params["status"] = status_filter
    status_code, payload = alpaca_api(user_id, env, "GET", "/v2/orders", params=params)
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=payload)
    return {"env": env, "orders": payload}

@router.post("/place_order")
def broker_place_order(
    user_id: str,
    symbol: str,
    side: str,
    qty: Optional[int] = None,
    notional: Optional[float] = None,
    type: str = "market",
    time_in_force: str = "day",
    env: str = Query("paper", pattern="^(paper|live)$"),
):
    """
    Minimal order proxy for equities (options later use same endpoint with option symbols).
    Either qty or notional is required.
    """
    if not qty and not notional:
        raise HTTPException(status_code=400, detail="Provide qty or notional")
    body = {
        "symbol": symbol.upper().strip(),
        "side": side.lower().strip(),          # 'buy' or 'sell'
        "type": type.lower().strip(),          # 'market'|'limit'|...
        "time_in_force": time_in_force.lower().strip(),  # 'day'|'gtc'|...
    }
    if qty: body["qty"] = str(qty)
    if notional: body["notional"] = str(notional)

    status_code, payload = alpaca_api(user_id, env, "POST", "/v2/orders", json_body=body)
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=payload)
    return {"env": env, "order": payload}
