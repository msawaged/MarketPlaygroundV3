# strategy_selector.py
# Selects a trading strategy based on parsed belief and optional price info

def select_strategy(
    belief: str,
    direction: str,
    confidence: str,
    asset_class: str,
    ticker: str = "",
    price_info=None  # can be dict or float
) -> str:
    """
    Selects the most appropriate trading strategy.

    Args:
        belief (str): Natural language belief.
        direction (str): 'bullish', 'bearish', or 'neutral'.
        confidence (str): 'high', 'medium', or 'low'.
        asset_class (str): 'stocks', 'options', 'crypto', 'bonds', 'etf'.
        ticker (str): Optional ticker for strategy context.
        price_info: Can be a dict like {'latest': 123.4} or a float like 123.4

    Returns:
        str: A simple strategy recommendation string.
    """

    # Format the price intelligently
    if isinstance(price_info, dict) and 'latest' in price_info:
        price_str = f" near ${price_info['latest']:.2f}"
    elif isinstance(price_info, float):
        price_str = f" near ${price_info:.2f}"
    else:
        price_str = ""

    # Crypto logic
    if asset_class == "crypto":
        return f"Buy {ticker or 'BTC'} if confidence is high{price_str}, otherwise wait"

    # Bonds logic
    if asset_class == "bonds":
        return "Long-duration bond ETF if expecting rate cuts"

    # ETF logic
    if asset_class == "etf":
        return f"Buy call options on {ticker} if bullish{price_str}, or protective puts if bearish"

    # Stocks/options logic
    if direction == "bullish" and confidence == "high":
        return f"Bull Call Spread on {ticker}{price_str}"
    elif direction == "bearish" and confidence == "high":
        return f"Bear Put Spread on {ticker}{price_str}"
    elif direction == "bullish":
        return f"Buy Call on {ticker}{price_str}"
    elif direction == "bearish":
        return f"Buy Put on {ticker}{price_str}"
    else:
        return f"Iron Condor on {ticker or 'underlying asset'}"
