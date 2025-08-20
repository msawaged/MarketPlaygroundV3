# backend/hot_trades.py

"""
📈 Hot Trades Aggregator — surfaces trending trade ideas across:
- Polymarket (API or scraped)
- Kalshi events (API or scraped)
- Upcoming earnings from yfinance
- Internal trending beliefs (future)
"""

import datetime
import requests
import yfinance as yf

def get_upcoming_earnings(tickers=["AAPL", "TSLA", "MSFT", "NFLX", "NVDA"]):
    """
    🔎 Pull upcoming earnings dates for a list of popular stocks using yfinance.
    Returns a list of dictionaries with ticker and earnings date.
    """
    earnings = []
    today = datetime.datetime.today().date()

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar
            if not cal.empty:
                date = cal.loc["Earnings Date"][0]
                if isinstance(date, (datetime.datetime, datetime.date)) and date.date() >= today:
                    earnings.append({
                        "ticker": ticker,
                        "source": "earnings_calendar",
                        "headline": f"{ticker} reports earnings on {date.strftime('%Y-%m-%d')}"
                    })
        except Exception as e:
            print(f"[ERROR] Earnings fetch failed for {ticker}: {e}")

    return earnings

def get_polymarket_trends():
    """
    ⚖️ Pull trending Polymarket predictions (simplified placeholder).
    In production, replace with real scraping/API logic.
    """
    sample_trades = [
        {
            "source": "polymarket",
            "headline": "Will Trump win the 2024 election?",
            "topic": "politics",
            "confidence": 0.68,
        },
        {
            "source": "polymarket",
            "headline": "Will inflation be below 3.5% by year end?",
            "topic": "economics",
            "confidence": 0.52,
        },
    ]
    return sample_trades

def get_kalshi_events():
    """
    📊 Placeholder for Kalshi market events.
    Future: scrape or API pull from Kalshi
    """
    return [
        {
            "source": "kalshi",
            "headline": "Will the Fed cut rates in September?",
            "topic": "interest rates",
            "confidence": 0.55
        },
        {
            "source": "kalshi",
            "headline": "Will Bitcoin be above $70K by August?",
            "topic": "crypto",
            "confidence": 0.60
        },
    ]

def get_hot_trades():
    """
    🔥 Aggregate hot trade ideas from all sources.
    Returns a unified list ready to be processed by the AI engine.
    """
    all_trades = []

    try:
        all_trades.extend(get_upcoming_earnings())
        all_trades.extend(get_polymarket_trends())
        all_trades.extend(get_kalshi_events())
    except Exception as e:
        print(f"[ERROR] Failed to load hot trades: {e}")

    return all_trades
