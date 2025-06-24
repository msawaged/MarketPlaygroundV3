# finnhub_data.py
# ✅ Finnhub price fetching module (for dev usage only — up to 60 requests/min).
# Docs: https://finnhub.io/docs/api

import requests

# 🔐 Replace with your real Finnhub API key
FINNHUB_API_KEY = "d1c51a9r01qre5ajo99gd1c51a9r01qre5ajo9a0"

def get_latest_price_finnhub(ticker: str) -> float:
    """
    Fetch the latest price for a given ticker using Finnhub.
    """
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        latest_price = data.get("c")  # Current price
        if latest_price is not None:
            return round(float(latest_price), 2)
        else:
            print(f"[ERROR] No current price found in Finnhub response for {ticker}.")
            return -1.0
    except Exception as e:
        print(f"[ERROR] Finnhub latest price failed for {ticker}: {e}")
        return -1.0

def get_weekly_high_low_finnhub(ticker: str) -> tuple:
    """
    Approximate weekly high/low using daily candles from the past 7 days.
    """
    try:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={ticker}&resolution=D&count=7&token={FINNHUB_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get("s") != "ok":
            print(f"[ERROR] Finnhub candle data not OK for {ticker}: {data}")
            return (-1.0, -1.0)

        highs = data.get("h", [])
        lows = data.get("l", [])

        if highs and lows:
            return round(max(highs), 2), round(min(lows), 2)
        else:
            print(f"[ERROR] Empty high/low data in Finnhub response for {ticker}")
            return (-1.0, -1.0)

    except Exception as e:
        print(f"[ERROR] Finnhub high/low fetch failed for {ticker}: {e}")
        return (-1.0, -1.0)
