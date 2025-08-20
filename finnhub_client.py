# backend/finnhub_client.py
# ✅ Secure wrapper for Finnhub stock data API
# 🔐 Loads API key from .env — no hardcoded secrets

import os
import requests
from dotenv import load_dotenv

# ✅ Load environment variables from .env at runtime
load_dotenv()

# 🔐 Securely fetch your Finnhub API key
API_KEY = os.getenv("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"

def get_finnhub_price(ticker: str) -> float:
    """
    ✅ Fetch latest stock price using Finnhub.
    Returns -1.0 on failure.

    Args:
        ticker (str): e.g., "AAPL"

    Returns:
        float: Latest price or -1.0 if error
    """
    try:
        response = requests.get(
            f"{BASE_URL}/quote",
            params={"symbol": ticker, "token": API_KEY}
        )

        if response.status_code != 200:
            print(f"[❌ FINNHUB ERROR] {ticker} → HTTP {response.status_code} — {response.text}")
            return -1.0

        data = response.json()
        price = data.get("c", -1.0)

        if price == -1.0:
            print(f"[⚠️ FINNHUB WARNING] No current price ('c') for {ticker}. Raw data: {data}")

        return round(float(price), 2)
    except Exception as e:
        print(f"[ERROR] get_finnhub_price() failed for {ticker}: {e}")
        return -1.0

def get_finnhub_high_low(ticker: str) -> tuple:
    """
    ✅ Fetch daily high/low using Finnhub.
    Returns (-1.0, -1.0) on failure.

    Args:
        ticker (str)

    Returns:
        tuple: (high, low)
    """
    try:
        response = requests.get(
            f"{BASE_URL}/quote",
            params={"symbol": ticker, "token": API_KEY}
        )

        if response.status_code != 200:
            print(f"[❌ FINNHUB ERROR] {ticker} → HTTP {response.status_code} — {response.text}")
            return -1.0, -1.0

        data = response.json()
        high = data.get("h", -1.0)
        low = data.get("l", -1.0)

        if high == -1.0 or low == -1.0:
            print(f"[⚠️ FINNHUB WARNING] Missing high/low for {ticker}. Raw data: {data}")

        return round(float(high), 2), round(float(low), 2)
    except Exception as e:
        print(f"[ERROR] get_finnhub_high_low() failed for {ticker}: {e}")
        return -1.0, -1.0
