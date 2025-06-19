# market_data.py
# 📈 Fetches real-time or recent market data for use in AI strategy generation

import yfinance as yf
from datetime import datetime, timedelta

def get_latest_price(ticker: str) -> float:
    """
    Returns the latest closing price for the given ticker.
    """
    try:
        data = yf.download(ticker, period="1d", interval="1m")
        if data.empty:
            raise ValueError(f"No data found for {ticker}")
        latest_price = data["Close"].iloc[-1]
        return round(float(latest_price), 2)
    except Exception as e:
        print(f"[market_data] Error fetching price for {ticker}: {e}")
        return -1.0

def get_weekly_high_low(ticker: str):
    """
    Returns the high and low of the past 5 trading days.
    """
    try:
        data = yf.download(ticker, period="5d")
        if data.empty:
            raise ValueError(f"No data found for {ticker}")
        high = data["High"].max()
        low = data["Low"].min()
        return round(high, 2), round(low, 2)
    except Exception as e:
        print(f"[market_data] Error fetching range for {ticker}: {e}")
        return -1.0, -1.0
