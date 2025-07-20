# backend/alpaca_client.py
# ✅ Alpaca API client using .env and logs outcomes

import os
import requests
import random
from dotenv import load_dotenv

# 🔁 Load environment variables from .env
load_dotenv()

# 🔐 Credentials from environment
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# ✅ Prepare API request headers
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

# 🧠 Import strategy outcome logger
from backend.strategy_outcome_logger import log_strategy_outcome


def get_account_info():
    """
    Fetches account details from Alpaca.
    """
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch Alpaca account info: {e}")
        return None


def submit_market_buy(ticker: str, qty: int, belief: str = None, strategy: dict = None):
    """
    Submits a market buy order and logs a simulated trade outcome.

    Args:
        ticker (str): Stock symbol (e.g., "AAPL")
        qty (int): Quantity of shares to buy
        belief (str): User belief that triggered trade
        strategy (dict): Strategy metadata to log
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
        order_data = response.json()

        print(f"✅ Order submitted: {order_data['id']} for {ticker} x{qty}")

        # 🎯 Simulated outcome logging (fake PnL for now)
        if strategy and belief:
            simulated_pnl = round(random.uniform(-10, 25), 2)
            result = "win" if simulated_pnl > 0 else "loss" if simulated_pnl < -2 else "neutral"

            log_strategy_outcome(
                strategy=strategy,
                belief=belief,
                ticker=ticker,
                pnl_percent=simulated_pnl,
                result=result,
                notes="alpaca execution (simulated)"
            )

        return order_data

    except Exception as e:
        print(f"[ERROR] Failed to submit order: {e}")
        return None


def get_order_status(order_id: str):
    """
    Fetches status of a specific order by ID.
    """
    try:
        response = requests.get(f"{ALPACA_BASE_URL}/v2/orders/{order_id}", headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to get order status for {order_id}: {e}")
        return None
