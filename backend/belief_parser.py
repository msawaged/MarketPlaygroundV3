# belief_parser.py
# Extracts the ticker from a belief using simple keyword matching

def detect_ticker(belief_text):
    """
    Detects a stock, ETF, or crypto ticker from the belief text.
    You can expand this dictionary or replace with named entity recognition later.

    Returns:
        str: Uppercase ticker (e.g., "TSLA")
    """
    tickers = {
        "tesla": "TSLA", "tsla": "TSLA",
        "apple": "AAPL", "aapl": "AAPL",
        "google": "GOOGL", "googl": "GOOGL",
        "meta": "META", "facebook": "META",
        "amazon": "AMZN", "amzn": "AMZN",
        "oil": "OIL", "crude": "OIL",
        "gold": "GOLD", "btc": "BTC", "bitcoin": "BTC",
        "eth": "ETH", "ethereum": "ETH",
        "qqq": "QQQ", "spy": "SPY"
    }

    belief_text = belief_text.lower()
    for key in tickers:
        if key in belief_text:
            return tickers[key]
    
    return "SPY"  # Default fallback
