# market_data.py
# Safely updated to include all price-related functions needed by the backend.

import yfinance as yf

def get_price(ticker):
    """
    Fetch latest 1-minute close price (fast intraday lookup).
    """
    try:
        data = yf.download(ticker, period="1d", interval="1m")
        if not data.empty:
            return round(data["Close"].iloc[-1], 2)
        return None
    except Exception as e:
        print(f"[ERROR] get_price() failed for {ticker}: {e}")
        return None

def get_latest_price(ticker: str) -> float:
    """
    Fetch latest closing price using yfinance (daily close).
    """
    try:
        data = yf.Ticker(ticker).history(period="1d")
        latest_price = data["Close"].iloc[-1]
        return round(float(latest_price), 2)
    except Exception as e:
        print(f"[ERROR] get_latest_price() failed for {ticker}: {e}")
        return -1.0

def get_weekly_high_low(ticker: str) -> tuple:
    """
    Fetch weekly high/low prices using yfinance.
    """
    try:
        data = yf.Ticker(ticker).history(period="7d")
        high = data["High"].max()
        low = data["Low"].min()
        return round(float(high), 2), round(float(low), 2)
    except Exception as e:
        print(f"[ERROR] get_weekly_high_low() failed for {ticker}: {e}")
        return (-1.0, -1.0)
