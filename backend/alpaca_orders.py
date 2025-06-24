# backend/alpaca_orders.py

"""
Alpaca Order History Handler:
- Fetches all past orders
- Filters filled (executed) trades
"""

import os
import requests
from dotenv import load_dotenv

# Load Alpaca credentials from .env
load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def get_all_orders(status: str = "all", limit: int = 100):
    """
    Fetches all Alpaca orders (default: all statuses).
    Use status='filled' to get only completed trades.
    """
    try:
        url = f"{ALPACA_BASE_URL}/v2/orders"
        params = {
            "status": status,
            "limit": limit,
            "direction": "desc"
        }
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch Alpaca orders: {e}")
        return []


def get_filled_orders(limit: int = 100):
    """
    Returns only fully filled/completed orders.
    """
    all_orders = get_all_orders(status="filled", limit=limit)
    filled_orders = [order for order in all_orders if order.get("filled_at")]
    return filled_orders
