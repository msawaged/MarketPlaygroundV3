# backend/market_data.py
# ✅ Primary market data functions for MarketPlayground AI.
# 🌐 Finnhub is primary source; Alpaca and yfinance used as backups.
# ⚠️ Fallbacks exist for local development/testing.

import yfinance as yf
from finnhub_client import get_finnhub_price, get_finnhub_high_low
import os
import requests

def get_price(ticker: str) -> float:
    """
    🔍 Intraday debug price via yfinance (1-minute interval).
    ⚠️ Not reliable for production.
    """
    try:
        data = yf.download(ticker, period="1d", interval="1m")
        if not data.empty:
            return round(data["Close"].iloc[-1], 2)
    except Exception as e:
        print(f"[ERROR] get_price() failed for {ticker}: {e}")
    return -1.0

def get_latest_price(ticker: str) -> float:
    """
    ✅ Primary: Finnhub
    🔁 Fallbacks: yfinance daily close → hardcoded dev prices
    """
    try:
        price = get_finnhub_price(ticker)
        if price > 0:
            return price
    except Exception as e:
        print(f"[ERROR] Finnhub price failed for {ticker}: {e}")

    try:
        data = yf.Ticker(ticker).history(period="1d")
        return round(float(data["Close"].iloc[-1]), 2)
    except Exception as e:
        print(f"[ERROR] yfinance price failed for {ticker}: {e}")

    # 🚨 DEV HARDCODED FALLBACKS
    fallback_prices = {
        "AAPL": 190.25,
        "TSLA": 172.80,
        "SPY": 529.40,
        "QQQ": 469.55
    }
    print(f"[WARNING] Using fallback price for {ticker}")
    return fallback_prices.get(ticker.upper(), -1.0)

def get_weekly_high_low(ticker: str) -> tuple:
    """
    ✅ Primary: Finnhub
    🔁 Fallbacks: yfinance 7-day → hardcoded dev values
    """
    try:
        high, low = get_finnhub_high_low(ticker)
        if high > 0 and low > 0:
            return high, low
    except Exception as e:
        print(f"[ERROR] Finnhub high/low failed for {ticker}: {e}")

    try:
        data = yf.Ticker(ticker).history(period="7d")
        high = data["High"].max()
        low = data["Low"].min()
        return round(float(high), 2), round(float(low), 2)
    except Exception as e:
        print(f"[ERROR] yfinance high/low failed for {ticker}: {e}")

    fallback_high_low = {
        "AAPL": (192.75, 186.80),
        "TSLA": (178.50, 168.40),
        "SPY": (532.10, 524.80),
        "QQQ": (474.20, 464.90)
    }
    print(f"[WARNING] Using fallback high/low for {ticker}")
    return fallback_high_low.get(ticker.upper(), (-1.0, -1.0))

def get_option_expirations(ticker: str) -> list:
    """
    ✅ Primary: Alpaca options API
    🔁 Fallback: yfinance.options
    🛟 Final fallback: dummy expirations to keep system working
    """
    # 🌐 Try Alpaca first
    try:
        url = f"https://data.alpaca.markets/v2/options/expirations/{ticker}"
        print(f"[DEBUG] Fetching Alpaca expirations: {url}")
        headers = {
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "expirations" in data and isinstance(data["expirations"], list):
            return data["expirations"]
    except requests.exceptions.HTTPError as http_err:
        print(f"[ERROR] Alpaca expirations failed for {ticker}: {http_err}")
    except Exception as e:
        print(f"[ERROR] Alpaca expirations general failure for {ticker}: {e}")

    # 🔁 Fallback: yfinance
    try:
        ticker_obj = yf.Ticker(ticker)
        expirations = ticker_obj.options
        if isinstance(expirations, list) and expirations:
            return expirations
    except Exception as e:
        print(f"[ERROR] yfinance expirations failed for {ticker}: {e}")

    # 🚨 Final fallback to avoid system breaking (test only)
    fallback_dates = [
        "2025-07-12",
        "2025-07-19",
        "2025-08-16",
        "2025-09-20"
    ]
    print(f"[WARNING] No valid expiration data for {ticker}. Using fallback dates.")
    return fallback_dates
