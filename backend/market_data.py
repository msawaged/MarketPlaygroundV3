# backend/market_data.py
# 🔁 Real-time market data fetching using yfinance

import yfinance as yf
from datetime import datetime

def get_live_price(ticker: str) -> float:
    """
    Returns the latest price for a given ticker symbol.
    """
    try:
        data = yf.Ticker(ticker)
        price = data.history(period="1d")["Close"].iloc[-1]
        print(f"[market_data] ✅ Live price for {ticker}: {price}")
        return price
    except Exception as e:
        print(f"[market_data] ❌ Error fetching live price for {ticker}: {e}")
        return -1

def get_expiry_dates(ticker: str, max_dates: int = 3) -> list:
    """
    Returns a list of upcoming option expiration dates.
    """
    try:
        data = yf.Ticker(ticker)
        expiries = data.options[:max_dates]
        print(f"[market_data] ✅ Expiry dates for {ticker}: {expiries}")
        return expiries
    except Exception as e:
        print(f"[market_data] ❌ Error fetching expiries for {ticker}: {e}")
        return []

def get_option_strikes(ticker: str, expiry: str) -> list:
    """
    Returns available option strike prices for a given ticker and expiry.
    """
    try:
        option_chain = yf.Ticker(ticker).option_chain(expiry)
        calls = option_chain.calls['strike'].tolist()
        puts = option_chain.puts['strike'].tolist()
        strikes = sorted(set(calls + puts))
        print(f"[market_data] ✅ Option strikes for {ticker} on {expiry}: {strikes[:5]}...")
        return strikes
    except Exception as e:
        print(f"[market_data] ❌ Error fetching option strikes: {e}")
        return []
