# backend/alpaca_client.py
# ✅ Alpaca API client for placing test trades using paper trading keys

import os
import requests
from dotenv import load_dotenv

# Load keys from .env
load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def get_account_info():
    """
    Returns account information from Alpaca (for test mode).
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
    Submits a simple market buy order to Alpaca (paper).
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
