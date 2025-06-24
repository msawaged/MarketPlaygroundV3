# backend/routes/alpaca_router.py

"""
Router for Alpaca-related endpoints:
- GET /live_positions → returns current open trades
- GET /account        → returns account info (cash, buying power, etc.)
"""

from fastapi import APIRouter
from backend.alpaca_portfolio import get_live_positions
from backend.alpaca_client import get_account_info  # ✅ New: account info function

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
