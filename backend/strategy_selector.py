# strategy_selector.py
# Selects the best trading strategy based on belief and asset type

def select_strategy(asset_type: str, direction: str, confidence: float = 0.5) -> dict:
    """
    Selects a trading strategy based on the asset class and market direction.

    Parameters:
    - asset_type: e.g., "stock", "etf", "crypto", "forex", "bond"
    - direction: "bullish", "bearish", or "neutral"
    - confidence: optional float (0 to 1) representing conviction

    Returns:
    - dict with keys: type, description, risk_level, suggested_allocation
    """
    strategy = {}

    if asset_type == "crypto":
        if direction == "bullish":
            strategy["type"] = "Buy Spot Crypto"
            strategy["description"] = "Buy the underlying crypto asset directly."
        elif direction == "bearish":
            strategy["type"] = "Short with Inverse Token"
            strategy["description"] = "Use an inverse token or short futures contract."
        else:
            strategy["type"] = "Hold Stablecoin"
            strategy["description"] = "Move funds to a stablecoin to reduce exposure."

    elif asset_type in ["stock", "etf"]:
        if direction == "bullish":
            strategy["type"] = "Buy Call Options"
            strategy["description"] = "Buy call options for leveraged upside exposure."
        elif direction == "bearish":
            strategy["type"] = "Buy Put Options"
            strategy["description"] = "Buy put options to profit from a decline."
        else:
            strategy["type"] = "Sell Iron Condor"
            strategy["description"] = "Profit from range-bound movement."

    elif asset_type == "forex":
        if direction == "bullish":
            strategy["type"] = "Buy Base Currency"
            strategy["description"] = "Go long on the base currency in the pair."
        elif direction == "bearish":
            strategy["type"] = "Sell Base Currency"
            strategy["description"] = "Short the base currency in the pair."
        else:
            strategy["type"] = "Enter Spread Trade"
            strategy["description"] = "Use a carry trade or spread-based neutral position."

    elif asset_type == "bond":
        if direction == "bullish":
            strategy["type"] = "Buy Long-Duration Bonds"
            strategy["description"] = "Gain from falling interest rates."
        elif direction == "bearish":
            strategy["type"] = "Short Treasury Futures"
            strategy["description"] = "Gain from rising interest rates."
        else:
            strategy["type"] = "Hold Short-Term Treasuries"
            strategy["description"] = "Minimize interest rate risk."

    else:
        strategy["type"] = "Default Strategy"
        strategy["description"] = "Buy diversified ETF or broad market asset."

    # Add metadata
    strategy["risk_level"] = "moderate"
    strategy["suggested_allocation"] = f"{round(confidence * 100)}% of trade capital"

    return strategy
