# asset_selector.py
# Updated to accept tags and optional ticker (instead of full belief string)

def select_asset_class(tags: list, ticker: str = "") -> str:
    """
    Determines the most relevant asset class based on parsed tags and optional ticker.

    Args:
        tags (list): Keywords extracted from belief
        ticker (str): Optional ticker symbol for override logic

    Returns:
        str: One of ['stocks', 'options', 'etf', 'bonds', 'crypto']
    """
    tags = [t.lower() for t in tags]

    if any(x in tags for x in ["bond", "treasury", "yield", "interest", "fixed income"]):
        return "bonds"
    elif any(x in tags for x in ["stock", "equity", "share"]):
        return "stocks"
    elif any(x in tags for x in ["etf", "fund", "index", "spy", "qqq"]):
        return "etf"
    elif any(x in tags for x in ["crypto", "bitcoin", "btc", "eth", "ethereum", "solana"]):
        return "crypto"
    else:
        return "options"
