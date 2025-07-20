# backend/alpaca_portfolio.py

"""
Fetches and formats live positions from Alpaca for real-time portfolio sync.
"""

import requests
import os
from dotenv import load_dotenv

# Load API keys
load_dotenv()
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def get_live_positions():
    """
    Fetches current open positions from Alpaca (real-time).
    """
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS)
        response.raise_for_status()
        positions = response.json()

        formatted = []
        for pos in positions:
            formatted.append({
                "symbol": pos.get("symbol"),
                "qty": float(pos.get("qty")),
                "avg_entry_price": float(pos.get("avg_entry_price")),
                "current_price": float(pos.get("current_price")),
                "unrealized_pl": float(pos.get("unrealized_pl")),
                "market_value": float(pos.get("market_value"))
            })

        return formatted

    except Exception as e:
        print(f"[ERROR] Failed to fetch live Alpaca positions: {e}")
        return []
