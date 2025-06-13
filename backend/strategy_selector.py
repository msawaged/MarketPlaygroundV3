# strategy_selector.py
# Smart strategy selector based on ML tags and ticker input
# Future-ready for ML-based leg optimization and contract pricing

from datetime import datetime, timedelta

def get_expiry_date(duration: str) -> str:
    """Returns a future expiry date string based on duration tag."""
    days = {"short": 7, "medium": 30, "long": 90}.get(duration, 30)
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def suggest_strategy(tags: dict, ticker: str) -> dict:
    """
    Suggests an options strategy based on parsed ML tags.
    
    Args:
        tags (dict): Tags like {'direction': 'bullish', 'duration': 'short', 'volatility': 'high'}
        ticker (str): Parsed asset ticker symbol (e.g. 'TSLA')
    
    Returns:
        dict: Strategy dictionary with keys: type, legs, expiry, payout
    """
    direction = tags.get("direction", "neutral")
    duration = tags.get("duration", "medium")
    volatility = tags.get("volatility", "medium")
    expiry = get_expiry_date(duration)

    # 🔮 Strategy logic — replace with ML later
    if direction == "bullish":
        strategy_type = "Call Debit Spread (Live)"
        legs = [f"Buy {ticker} ATM call", f"Sell {ticker} higher call"]
        payout = "2.0x"
    elif direction == "bearish":
        strategy_type = "Put Debit Spread (Live)"
        legs = [f"Buy {ticker} ATM put", f"Sell {ticker} lower put"]
        payout = "2.0x"
    elif direction == "neutral":
        strategy_type = "Iron Condor (Live)"
        legs = [
            f"Sell {ticker} lower put",
            f"Buy {ticker} even-lower put",
            f"Sell {ticker} higher call",
            f"Buy {ticker} even-higher call",
        ]
        payout = "2.0x"
    else:
        strategy_type = "Default Strategy"
        legs = [f"Buy {ticker} call", f"Sell {ticker} call"]
        payout = "1.5x"

    return {
        "type": strategy_type,
        "legs": legs,
        "expiry": expiry,
        "payout": payout
    }
