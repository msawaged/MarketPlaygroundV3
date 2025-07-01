"""
Alpaca Order Handler:
- Supports unified trade execution (stocks + options)
- Fetches past orders (all or filled)
"""

import os
import requests
from dotenv import load_dotenv
from backend.broker_interface import BrokerInterface  # Interface for all brokers

# === ✅ Load .env for Render and local use ===
dotenv_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=dotenv_path)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# ✅ Debug load confirmation
print("🔑 ALPACA_API_KEY loaded:", "✔️" if ALPACA_API_KEY else "❌ MISSING")
print("🔑 ALPACA_SECRET_KEY loaded:", "✔️" if ALPACA_SECRET_KEY else "❌ MISSING")


class AlpacaExecutor(BrokerInterface):
    """
    Alpaca trade executor for both stocks and options.
    """

    def execute_order(self, strategy: dict, user_id: str = "anonymous") -> dict:
        ticker = strategy.get("ticker")
        direction = strategy.get("direction", "").lower()
        asset_class = strategy.get("asset_class", "stock")
        allocation = strategy.get("suggested_allocation", "10%")

        # === 🚀 STOCK ORDER LOGIC ===
        if asset_class == "stock":
            try:
                side = "buy" if "bull" in direction or "long" in direction else "sell"
                payload = {
                    "symbol": ticker,
                    "qty": 1,  # TODO: calculate from user balance + allocation
                    "side": side,
                    "type": "market",
                    "time_in_force": "gtc"
                }
                print(f"📤 Alpaca STOCK order payload: {payload}")
                url = f"{ALPACA_BASE_URL}/v2/orders"
                response = requests.post(url, headers=HEADERS, json=payload)
                response.raise_for_status()

                return {
                    "status": "success",
                    "message": f"{side.upper()} stock order placed for {ticker}",
                    "order": response.json()
                }

            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed stock order for {ticker}",
                    "error": str(e)
                }

        # === 🚀 OPTIONS ORDER LOGIC ===
        elif asset_class == "options":
            try:
                # Basic logic assumes single-leg option (not spread)
                # You may replace this with parsing logic for spreads later
                description = strategy.get("description", "").lower()
                option_type = "call" if "call" in description else "put"
                side = "buy_to_open" if "bull" in direction or "long" in direction else "sell_to_open"

                contracts = description.split(" / ") if " / " in description else [description]
                orders = []

                for contract in contracts:
                    parts = contract.strip().split()
                    if len(parts) != 3:
                        continue
                    symbol, strike, suffix = parts
                    strike_price = strike.replace("c", "").replace("p", "")
                    option_type = "call" if "c" in strike else "put"

                    order_payload = {
                        "symbol": symbol,
                        "qty": 1,
                        "side": side,
                        "type": "market",
                        "time_in_force": "gtc",
                        "order_class": "simple",
                        "legs": [
                            {
                                "symbol": symbol,
                                "qty": 1,
                                "side": side,
                                "option_type": option_type,
                                "strike_price": float(strike_price),
                                "expiration_date": strategy.get("expiry_date"),
                            }
                        ]
                    }

                    print(f"📤 Alpaca OPTIONS order payload: {order_payload}")
                    url = f"{ALPACA_BASE_URL}/v1beta1/options/orders"
                    response = requests.post(url, headers=HEADERS, json=order_payload)
                    response.raise_for_status()
                    orders.append(response.json())

                return {
                    "status": "success",
                    "message": f"Options order(s) placed for {ticker}",
                    "order": orders
                }

            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed options order for {ticker}",
                    "error": str(e)
                }

        # === Unknown Asset Class ===
        else:
            return {
                "status": "error",
                "message": f"Unsupported asset class: {asset_class}",
                "error": "Only 'stock' and 'options' supported"
            }


def get_all_orders(status: str = "all", limit: int = 100):
    """
    Fetches all Alpaca stock orders (default: all statuses).
    """
    try:
        url = f"{ALPACA_BASE_URL}/v2/orders"
        params = {"status": status, "limit": limit, "direction": "desc"}
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch Alpaca orders: {e}")
        return []


def get_filled_orders(limit: int = 100):
    """
    Returns only fully filled/completed stock orders.
    """
    all_orders = get_all_orders(status="filled", limit=limit)
    return [o for o in all_orders if o.get("filled_at")]
