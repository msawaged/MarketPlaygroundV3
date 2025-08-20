# backend/routes/alpaca_router.py

"""
Router for Alpaca-related endpoints:
- GET /live_positions          → returns current open positions
- GET /account                 → returns account info (cash, equity, etc.)
- GET /order_status/{order_id} → checks order status by ID
- GET /orders                  → returns full order history
- GET /orders/filled           → returns only filled (executed) trades
"""

from fastapi import APIRouter
from backend.alpaca_portfolio import get_live_positions
from backend.alpaca_client import get_account_info, get_order_status
from backend.alpaca_orders import get_all_orders, get_filled_orders  # ✅ New: order history

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

@router.get("/orders")
def fetch_all_orders():
    """
    Returns the full Alpaca order history (limit 100).
    """
    orders = get_all_orders()
    return {"orders": orders}

@router.get("/orders/filled")
def fetch_filled_orders():
    """
    Returns only filled Alpaca orders (executed trades).
    """
    orders = get_filled_orders()
    return {"filled_orders": orders}
