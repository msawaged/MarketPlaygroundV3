# backend/market_data.py
# Primary pricing functions for MarketPlayground AI.
# ✅ Finnhub is the primary data source.
# ⚠️ yfinance and hardcoded values are for development testing ONLY.

import yfinance as yf
from finnhub_client import get_finnhub_price, get_finnhub_high_low

def get_price(ticker: str) -> float:
    """
    Fetch latest 1-minute close price using yfinance.
    Used for quick intraday debugging. Not reliable for production.
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
    ✅ Primary: Finnhub latest price.
    ⚠️ Fallbacks: yfinance daily close → hardcoded test values.
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

    # ⚠️ HARD-CODED FALLBACKS FOR OFFLINE DEV TESTING ONLY
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
    ✅ Primary: Finnhub daily high/low.
    ⚠️ Fallbacks: yfinance 7-day high/low → hardcoded test values.
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

    # ⚠️ HARD-CODED FALLBACKS FOR OFFLINE DEV TESTING ONLY
    fallback_high_low = {
        "AAPL": (192.75, 186.80),
        "TSLA": (178.50, 168.40),
        "SPY": (532.10, 524.80),
        "QQQ": (474.20, 464.90)
    }
    print(f"[WARNING] Using fallback high/low for {ticker}")
    return fallback_high_low.get(ticker.upper(), (-1.0, -1.0))
