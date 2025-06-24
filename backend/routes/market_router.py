# backend/routes/market_router.py

"""
Exposes market data (price, high/low) via FastAPI endpoints.
Calls backend.market_data functions using Finnhub + fallback logic.
"""

from fastapi import APIRouter, HTTPException
from backend.market_data import get_latest_price, get_weekly_high_low

router = APIRouter()

@router.get("/price")
def get_price_route(ticker: str):
    """
    Returns the latest price for a given ticker using Finnhub or fallback.
    Example: /market/price?ticker=AAPL
    """
    try:
        price = get_latest_price(ticker)
        if price < 0:
            raise ValueError("Price not found")
        return {"ticker": ticker.upper(), "latest_price": price}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}: {e}")

@router.get("/highlow")
def get_high_low_route(ticker: str):
    """
    Returns the weekly high/low for a given ticker.
    Example: /market/highlow?ticker=AAPL
    """
    try:
        high, low = get_weekly_high_low(ticker)
        if high < 0 or low < 0:
            raise ValueError("High/Low data not found")
        return {"ticker": ticker.upper(), "weekly_high": high, "weekly_low": low}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch high/low for {ticker}: {e}")
