# backend/routes/alpaca_router.py

"""
Router for Alpaca-related endpoints:
- GET /live_positions         → returns current open positions
- GET /account                → returns account info (cash, equity, etc.)
- GET /order_status/{order_id} → checks order status by ID
"""

from fastapi import APIRouter
from backend.alpaca_portfolio import get_live_positions
from backend.alpaca_client import get_account_info, get_order_status  # ✅ Added get_order_status

router = APIRouter()

@router.get("/live_positions")
def fetch_live_positions():
    """
    Returns live open positions from Alpaca (paper account).
    """
    positions = get_live_positions()
    return {"positions": positions}

@router.get("/account")
def fetch_account_info():
    """
    Returns Alpaca account details: cash, buying power, equity, etc.
    """
    account = get_account_info()
    return {"account": account}

@router.get("/order_status/{order_id}")
def fetch_order_status(order_id: str):
    """
    Returns the status of a specific Alpaca order by its ID.
    """
    status = get_order_status(order_id)
    return {"order_id": order_id, "status": status}
