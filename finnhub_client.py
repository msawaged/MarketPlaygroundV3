# finnhub_client.py
# Lightweight wrapper for accessing Finnhub stock data.
# ✅ For development use only — later move API key to .env before production.

import requests

# ✅ Your actual Finnhub API key
API_KEY = "d1c5qjpr01qre5ajss9gd1c5qjpr01qre5ajssa0"

BASE_URL = "https://finnhub.io/api/v1"

def get_finnhub_price(ticker: str) -> float:
    """
    Fetch the current stock price from Finnhub.
    Falls back to -1.0 if the API call fails.

    Args:
        ticker (str): Stock ticker symbol (e.g., "AAPL")

    Returns:
        float: Latest price or -1.0 on failure
    """
    try:
        response = requests.get(
            f"{BASE_URL}/quote",
            params={"symbol": ticker, "token": API_KEY}
        )
        data = response.json()
        return round(float(data.get("c", -1.0)), 2)
    except Exception as e:
        print(f"[ERROR] get_finnhub_price() failed for {ticker}: {e}")
        return -1.0

def get_finnhub_high_low(ticker: str) -> tuple:
    """
    Fetch the daily high and low price from Finnhub.

    Args:
        ticker (str): Stock ticker symbol

    Returns:
        tuple: (high, low) or (-1.0, -1.0) on failure
    """
    try:
        response = requests.get(
            f"{BASE_URL}/quote",
            params={"symbol": ticker, "token": API_KEY}
        )
        data = response.json()
        high = data.get("h", -1.0)
        low = data.get("l", -1.0)
        return round(float(high), 2), round(float(low), 2)
    except Exception as e:
        print(f"[ERROR] get_finnhub_high_low() failed for {ticker}: {e}")
        return -1.0, -1.0
