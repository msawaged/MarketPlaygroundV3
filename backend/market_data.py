# backend/market_data.py
# ✅ Primary market data functions for MarketPlayground AI.
# 🌐 Finnhub is primary source; Alpaca and yfinance used as backups.
# ⚠️ Fallbacks exist for local development/testing.

import yfinance as yf
from finnhub_client import get_finnhub_price, get_finnhub_high_low
import os
import requests
from typing import Tuple, Optional  # add
from backend.utils.symbol_universe import is_tradable_symbol


# Minimal Alpaca REST config (uses your existing env vars)
_ALPACA_KEY = os.getenv("ALPACA_API_KEY")
_ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
_ALPACA_DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")
_ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() in ("1", "true", "yes")

def _alpaca_headers():
    return {
        "APCA-API-KEY-ID": _ALPACA_KEY or "",
        "APCA-API-SECRET-KEY": _ALPACA_SECRET or "",
        "accept": "application/json",
    }

def _get_latest_price_alpaca(ticker: str) -> float:
    """Last trade from Alpaca data API."""
    url = f"{_ALPACA_DATA_BASE}/v2/stocks/{ticker}/trades/latest"
    r = requests.get(url, headers=_alpaca_headers(), timeout=5)
    r.raise_for_status()
    data = r.json()
    price = data.get("trade", {}).get("p")
    if price is None:
        raise ValueError(f"Alpaca returned no price for {ticker}")
    return float(price)

def _get_weekly_high_low_alpaca(ticker: str) -> Tuple[float, float]:
    """7 daily bars via Alpaca; returns (high,max), (low,min)."""
    url = f"{_ALPACA_DATA_BASE}/v2/stocks/{ticker}/bars"
    params = {"timeframe": "1Day", "limit": 7, "adjustment": "all"}
    r = requests.get(url, headers=_alpaca_headers(), params=params, timeout=5)
    r.raise_for_status()
    data = r.json()
    bars = data.get("bars", [])
    if not bars:
        raise ValueError(f"Alpaca returned no bars for {ticker}")
    highs = [b.get("h") for b in bars if b.get("h") is not None]
    lows  = [b.get("l") for b in bars if b.get("l") is not None]
    if not highs or not lows:
        raise ValueError(f"Alpaca bars missing h/l for {ticker}")
    return float(max(highs)), float(min(lows))


def get_price(ticker: str) -> float:
    """Debug helper — use the guarded primary chain (Alpaca → Finnhub → yfinance)."""
    return get_latest_price(ticker)

def get_latest_price(ticker: str) -> float:
    """
    ✅ Primary: Alpaca
    🔁 Fallbacks: Finnhub → yfinance → hardcoded dev prices
    """
    # guard: only price symbols in Alpaca’s tradable universe
    if not is_tradable_symbol(ticker):
        raise ValueError(f"Untradable or unknown symbol: {ticker}")

    # Alpaca first (paid)
    try:
        return round(_get_latest_price_alpaca(ticker), 2)
    except Exception as e:
        print(f"[MARKET_DATA] Alpaca latest price failed for {ticker}: {e}")

    # Finnhub next
    try:
        price = get_finnhub_price(ticker)
        if price > 0:
            return round(float(price), 2)
    except Exception as e:
        print(f"[ERROR] Finnhub latest price failed for {ticker}: {e}")

    # yfinance fallback
    try:
        data = yf.Ticker(ticker).history(period="1d")
        return round(float(data['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"[ERROR] yfinance price failed for {ticker}: {e}")

    # 🚨 DEV fallback
    fallback_prices = {
        "AAPL": 190.25,
        "TSLA": 172.80,
        "SPY": 529.40,
        "QQQ": 469.55,
        "USO": 74.64,
    }
    print(f"[WARNING] Using fallback price for {ticker}")
    return fallback_prices.get(ticker.upper(), -1.0)


def get_weekly_high_low(ticker: str) -> tuple:
    """
    ✅ Primary: Finnhub
    🔁 Fallbacks: yfinance 7-day → hardcoded dev values
    """
    # guard: only price symbols in Alpaca’s tradable universe
    if not is_tradable_symbol(ticker):
        raise ValueError(f"Untradable or unknown symbol: {ticker}")
        
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

    # 🚨 DEV fallback
    print(f"[WARNING] Using fallback high/low for {ticker}")
    return (100.0, 90.0)


def get_option_expirations(ticker: str) -> list:
    """
    ✅ Primary: Alpaca (if supported in your plan in the future)
    🔁 Fallbacks: yfinance → curated defaults (for dev/testing)
    """
    # guard: only optionable & tradable symbols should pass upstream checks
    if not is_tradable_symbol(ticker):
        raise ValueError(f"Untradable or unknown symbol: {ticker}")

    # (Future) Alpaca options expirations here if available

    # yfinance fallback
    try:
        yf_t = yf.Ticker(ticker)
        expirations = yf_t.options
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
