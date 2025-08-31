# backend/routes/alpaca_router.py

"""
Router for Alpaca-related endpoints:
- GET  /alpaca/live_positions          → returns current open positions
- GET  /alpaca/account                 → returns account info (cash, equity, etc.)
- GET  /alpaca/order_status/{order_id} → checks order status by ID
- GET  /alpaca/orders                  → returns full order history
- GET  /alpaca/orders/filled           → returns only filled (executed) trades
- GET  /alpaca/config                  → returns account configuration flags (incl. suspend_trade)
- POST /alpaca/unsuspend               → sets suspend_trade=false (unsuspends new orders)
"""

import os
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.alpaca_portfolio import get_live_positions
from backend.alpaca_client import get_account_info, get_order_status
from backend.alpaca_orders import get_all_orders, get_filled_orders  # ✅ order history

router = APIRouter()

# -----------------------------------------------------------------------------
# Server-held Alpaca credentials (no secrets required in client curls)
# -----------------------------------------------------------------------------
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# -----------------------------------------------------------------------------
# Existing endpoints
# -----------------------------------------------------------------------------
@router.get("/live_positions")
def fetch_live_positions():
    """Returns live open positions from Alpaca (paper account)."""
    positions = get_live_positions()
    return {"positions": positions}

@router.get("/account")
def fetch_account_info():
    """Returns Alpaca account details: cash, buying power, equity, etc."""
    account = get_account_info()
    return {"account": account}

@router.get("/order_status/{order_id}")
def fetch_order_status(order_id: str):
    """Returns the status of a specific Alpaca order by its ID."""
    status = get_order_status(order_id)
    return {"order_id": order_id, "status": status}

@router.get("/orders")
def fetch_all_orders():
    """Returns the full Alpaca order history (limit 100)."""
    orders = get_all_orders()
    return {"orders": orders}

@router.get("/orders/filled")
def fetch_filled_orders():
    """Returns only filled Alpaca orders (executed trades)."""
    orders = get_filled_orders()
    return {"filled_orders": orders}

# -----------------------------------------------------------------------------
# NEW: Config probe + Unsuspend endpoint
# -----------------------------------------------------------------------------
@router.get("/config")
def get_alpaca_config():
    """
    Return Alpaca account configurations (uses server-stored creds).
    Useful to check `suspend_trade` / `trade_suspended_by_user`.
    """
    try:
        r = requests.get(f"{ALPACA_BASE_URL}/v2/account/configurations", headers=HEADERS, timeout=15)
        return JSONResponse(status_code=r.status_code, content=r.json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch config: {e}")

@router.post("/unsuspend")
def alpaca_unsuspend_trading():
    """
    Turn OFF 'Suspend trading' (trade_suspended_by_user=false) via Alpaca configs.
    Uses server-held environment credentials; NO secrets in client requests.
    """
    try:
        r = requests.patch(
            f"{ALPACA_BASE_URL}/v2/account/configurations",
            headers=HEADERS,
            json={"suspend_trade": False},
            timeout=15,
        )
        # Surface Alpaca's body on error for clarity
        if r.status_code >= 400:
            try:
                details = r.json()
            except Exception:
                details = {"text": r.text}
            raise HTTPException(status_code=r.status_code, detail=details)

        return JSONResponse(status_code=200, content=r.json())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsuspend trading: {e}")
