# backend/alpaca_orders.py

"""
Alpaca Order Handler:
- Fetches past orders (all or filled)
- Supports unified trade execution via execute_order()
"""

import os
import requests
from dotenv import load_dotenv
from backend.broker_interface import BrokerInterface  # Interface for all brokers

# === ✅ Force-load .env from backend ===
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=dotenv_path)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# ✅ Debug log to verify .env keys loaded correctly
print("🔑 ALPACA_API_KEY loaded:", "✔️" if ALPACA_API_KEY else "❌ MISSING")
print("🔑 ALPACA_SECRET_KEY loaded:", "✔️" if ALPACA_SECRET_KEY else "❌ MISSING")


class AlpacaExecutor(BrokerInterface):
    """
    Alpaca trade executor that conforms to BrokerInterface.
    Allows unified strategy execution through execute_order().
    """

    def execute_order(self, strategy: dict, user_id: str = "anonymous") -> dict:
        """
        Executes a simple stock/option order via Alpaca.
        NOTE: Options trading requires Alpaca Options API or workaround.
        """

        try:
            ticker = strategy.get("ticker")
            direction = strategy.get("direction", "").lower()
            allocation = strategy.get("suggested_allocation", "10%")
            quantity = 1  # TODO: Replace with logic based on user's cash + allocation

            side = "buy" if "bull" in direction or "long" in direction else "sell"
            order_type = "market"
            time_in_force = "gtc"

            payload = {
                "symbol": ticker,
                "qty": quantity,
                "side": side,
                "type": order_type,
                "time_in_force": time_in_force,
            }

            print(f"📤 Alpaca order payload: {payload}")

            url = f"{ALPACA_BASE_URL}/v2/orders"
            response = requests.post(url, headers=HEADERS, json=payload)

            print(f"✅ Alpaca response: {response.status_code} — {response.text}")
            response.raise_for_status()

            return {
                "status": "success",
                "message": f"{side.upper()} order placed for {ticker}",
                "order": response.json()
            }

        except Exception as e:
            print(f"❌ Alpaca execution failed: {e}")
            return {
                "status": "error",
                "message": f"Failed to execute order for {strategy.get('ticker')}",
                "error": str(e)
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
