# backend/alpaca_client.py
# ✅ Alpaca API client for submitting trades and retrieving account/order info

import os
import requests
from dotenv import load_dotenv

# === Load .env keys ===
load_dotenv()
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# === Standard headers for API requests ===
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def get_account_info():
    """
    Returns account details from Alpaca (balance, buying power, etc).
    """
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch Alpaca account info: {e}")
        return None


def submit_market_buy(ticker: str, qty: int):
    """
    Submits a market buy order to Alpaca (paper trading).
    """
    try:
        order = {
            "symbol": ticker.upper(),
            "qty": qty,
            "side": "buy",
            "type": "market",
            "time_in_force": "gtc"
        }
        response = requests.post(f"{ALPACA_BASE_URL}/v2/orders", json=order, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to submit order: {e}")
        return None


def get_order_status(order_id: str):
    """
    Fetches the status of a specific order by ID from Alpaca.
    """
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/orders/{order_id}", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to get order status for {order_id}: {e}")
        return None
