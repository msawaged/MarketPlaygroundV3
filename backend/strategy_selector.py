# backend/strategy_selector.py

"""
Selects the best-fit trading strategy based on parsed belief, asset class,
direction, confidence level, and user goal (e.g. 2x return, hedge, income).
"""

def select_strategy(
    belief: str,
    direction: str,
    ticker: str,
    asset_class: str,
    price_info: dict,
    confidence: float = 0.5,
    goal_type: str = None,
    multiplier: float = None,
    timeframe: str = None
) -> dict:
    """
    Determine a recommended trading strategy based on all user inputs.

    Returns a dict like:
    {
        "type": "Call Spread",
        "description": "Buy AAPL 190c / Sell AAPL 195c",
        "risk_level": "medium",
        "suggested_allocation": "25%"
    }
    """
    # Make sure price_info is always a dict
    latest_price = price_info["latest"] if isinstance(price_info, dict) else price_info
    latest_price = round(float(latest_price), 2)

    print("\n[STRATEGY DEBUG]")
    print("  Belief:", belief)
    print("  Direction:", direction)
    print("  Ticker:", ticker)
    print("  Asset Class:", asset_class)
    print("  Confidence:", confidence)
    print("  Goal Type:", goal_type)
    print("  Multiplier:", multiplier)
    print("  Timeframe:", timeframe)

    # === ✅ Goal-Based Strategy Logic ===
    if goal_type == "double_money" and multiplier and multiplier >= 2.0:
        if asset_class == "options":
            if direction == "up":
                return {
                    "type": "Aggressive Call Spread",
                    "description": f"Buy {ticker} {int(latest_price * 1.05)}c / Sell {ticker} {int(latest_price * 1.15)}c",
                    "risk_level": "high",
                    "suggested_allocation": "15%"
                }
            elif direction == "down":
                return {
                    "type": "Aggressive Put Spread",
                    "description": f"Buy {ticker} {int(latest_price * 0.95)}p / Sell {ticker} {int(latest_price * 0.85)}p",
                    "risk_level": "high",
                    "suggested_allocation": "15%"
                }
            else:
                # If direction is unclear, use straddle (volatility bet)
                return {
                    "type": "Long Straddle",
                    "description": f"Buy {ticker} {int(latest_price)}c + Buy {ticker} {int(latest_price)}p",
                    "risk_level": "high",
                    "suggested_allocation": "20%"
                }

        elif asset_class == "stock":
            return {
                "type": "Leveraged ETF",
                "description": f"Buy 2x or 3x leveraged ETF related to {ticker}",
                "risk_level": "high",
                "suggested_allocation": "20%"
            }

    elif goal_type == "hedge":
        return {
            "type": "Protective Put",
            "description": f"Buy {ticker} {int(latest_price * 0.95)}p to hedge downside",
            "risk_level": "low",
            "suggested_allocation": "10%"
        }

    elif goal_type == "income":
        return {
            "type": "Cash-Secured Put",
            "description": f"Sell {ticker} {int(latest_price * 0.95)}p for monthly income",
            "risk_level": "medium",
            "suggested_allocation": "20%"
        }

    # === ✅ Direction-Based Strategy Logic (Fallback) ===
    if asset_class == "options":
        if direction == "up":
            return {
                "type": "Call",
                "description": f"Buy {ticker} {int(latest_price * 1.05)}c",
                "risk_level": "medium",
                "suggested_allocation": "25%"
            }
        elif direction == "down":
            return {
                "type": "Put",
                "description": f"Buy {ticker} {int(latest_price * 0.95)}p",
                "risk_level": "medium",
                "suggested_allocation": "25%"
            }

    elif asset_class == "stock":
        if direction == "up":
            return {
                "type": "Buy Stock",
                "description": f"Buy {ticker} at market price",
                "risk_level": "low",
                "suggested_allocation": "30%"
            }
        elif direction == "down":
            return {
                "type": "Inverse ETF",
                "description": f"Buy inverse ETF or short {ticker}",
                "risk_level": "high",
                "suggested_allocation": "10%"
            }

    # === ✅ Final Fallback ===
    return {
        "type": "Default Strategy",
        "description": f"Analyze {ticker} manually",
        "risk_level": "unknown",
        "suggested_allocation": "10%"
    }
