# backend/strategy_selector.py

"""
Selects the best-fit trading strategy based on parsed belief, asset class,
direction, confidence level, user goal (e.g. 2x return, hedge, income),
and user risk profile (conservative, moderate, aggressive).
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
    timeframe: str = None,
    expiry_date: str = None,  # ✅ Added to avoid TypeError from extra input
    risk_profile: str = "moderate"
) -> dict:
    """
    Returns a complete recommendation based on belief analysis.

    Example Output:
    {
        "type": "Call Spread",
        "description": "Buy AAPL 190c / Sell AAPL 195c",
        "risk_level": "medium",
        "suggested_allocation": "25%",
        "explanation": "Rationale behind this recommendation"
    }
    """
    latest_price = price_info["latest"] if isinstance(price_info, dict) else price_info
    latest_price = round(float(latest_price), 2)

    # ✅ Debug logging
    print("\n[STRATEGY DEBUG]")
    print("  Belief:", belief)
    print("  Direction:", direction)
    print("  Ticker:", ticker)
    print("  Asset Class:", asset_class)
    print("  Confidence:", confidence)
    print("  Goal Type:", goal_type)
    print("  Multiplier:", multiplier)
    print("  Timeframe:", timeframe)
    print("  Expiry Date:", expiry_date)  # for future use
    print("  Risk Profile:", risk_profile)

    # ✅ Ri***REMOVED***based allocation adjustment
    def adjust_allocation(base_percent):
        if risk_profile == "conservative":
            return f"{int(base_percent * 0.6)}%"
        elif risk_profile == "aggressive":
            return f"{int(base_percent * 1.4)}%"
        return f"{base_percent}%"

    # === 🎯 GOAL-BASED STRATEGIES ===

    if goal_type == "double_money" and multiplier and multiplier >= 2.0:
        if asset_class == "options":
            if direction == "up":
                return {
                    "type": "Aggressive Call Spread",
                    "description": f"Buy {ticker} {int(latest_price * 1.05)}c / Sell {ticker} {int(latest_price * 1.15)}c",
                    "risk_level": "high",
                    "suggested_allocation": adjust_allocation(15),
                    "explanation": "Targeting 2x return? This bullish spread offers upside with controlled risk."
                }
            elif direction == "down":
                return {
                    "type": "Aggressive Put Spread",
                    "description": f"Buy {ticker} {int(latest_price * 0.95)}p / Sell {ticker} {int(latest_price * 0.85)}p",
                    "risk_level": "high",
                    "suggested_allocation": adjust_allocation(15),
                    "explanation": "A bearish spread offers capped risk while maximizing downside reward—aligned with your 2x goal."
                }
            else:
                return {
                    "type": "Long Straddle",
                    "description": f"Buy {ticker} {int(latest_price)}c + Buy {ticker} {int(latest_price)}p",
                    "risk_level": "high",
                    "suggested_allocation": adjust_allocation(20),
                    "explanation": "Uncertain direction? Straddles profit from big moves either way—suitable for bold 2x targets."
                }
        elif asset_class == "stock":
            return {
                "type": "Leveraged ETF",
                "description": f"Buy a 2x or 3x leveraged ETF tracking {ticker}",
                "risk_level": "high",
                "suggested_allocation": adjust_allocation(20),
                "explanation": "Leverage boosts exposure—best used short-term when aiming for large gains."
            }

    elif goal_type == "hedge":
        return {
            "type": "Protective Put",
            "description": f"Buy {ticker} {int(latest_price * 0.95)}p",
            "risk_level": "low",
            "suggested_allocation": adjust_allocation(10),
            "explanation": "This strategy acts like insurance—ideal if you want to limit downside on current holdings."
        }

    elif goal_type == "income":
        return {
            "type": "Cash-Secured Put",
            "description": f"Sell {ticker} {int(latest_price * 0.95)}p",
            "risk_level": "medium",
            "suggested_allocation": adjust_allocation(20),
            "explanation": "You collect income while potentially buying stock cheaper—great for passive returns."
        }

    elif goal_type == "safe_growth":
        return {
            "type": "Covered Call",
            "description": f"Buy {ticker} + Sell {ticker} {int(latest_price * 1.05)}c",
            "risk_level": "low",
            "suggested_allocation": adjust_allocation(30),
            "explanation": "Covered calls generate extra yield while holding stock—ideal for steady growth."
        }

    # === 🧭 FALLBACK: DIRECTION-BASED STRATEGIES ===

    if asset_class == "options":
        if direction == "up":
            return {
                "type": "Call",
                "description": f"Buy {ticker} {int(latest_price * 1.05)}c",
                "risk_level": "medium",
                "suggested_allocation": adjust_allocation(25),
                "explanation": "Simple bullish bet—defined risk with potential for high reward."
            }
        elif direction == "down":
            return {
                "type": "Put",
                "description": f"Buy {ticker} {int(latest_price * 0.95)}p",
                "risk_level": "medium",
                "suggested_allocation": adjust_allocation(25),
                "explanation": "Put options profit from price drops—clear match for bearish views."
            }

    elif asset_class == "stock":
        if direction == "up":
            return {
                "type": "Buy Stock",
                "description": f"Buy {ticker} at market price",
                "risk_level": "low",
                "suggested_allocation": adjust_allocation(30),
                "explanation": "Direct ownership of stock—best for long-term bullish beliefs."
            }
        elif direction == "down":
            return {
                "type": "Inverse ETF",
                "description": f"Buy inverse ETF or short {ticker}",
                "risk_level": "high",
                "suggested_allocation": adjust_allocation(10),
                "explanation": "Inverse ETFs mirror declines—best when confident the asset will fall."
            }

    # === 🛑 DEFAULT STRATEGY ===

    return {
        "type": "Default Strategy",
        "description": f"Analyze {ticker} manually",
        "risk_level": "unknown",
        "suggested_allocation": adjust_allocation(10),
        "explanation": "Unable to determine a clear match. Try adjusting your belief or goal."
    }
