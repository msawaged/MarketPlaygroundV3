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
    risk_profile: str = "moderate"  # ✅ NEW: user-defined risk profile
) -> dict:
    """
    Determine a recommended trading strategy based on all user inputs.

    Returns a dict like:
    {
        "type": "Call Spread",
        "description": "Buy AAPL 190c / Sell AAPL 195c",
        "risk_level": "medium",
        "suggested_allocation": "25%",
        "explanation": "Rationale behind this recommendation"
    }
    """
    # ✅ Ensure valid and rounded price
    latest_price = price_info["latest"] if isinstance(price_info, dict) else price_info
    latest_price = round(float(latest_price), 2)

    # ✅ Debug information
    print("\n[STRATEGY DEBUG]")
    print("  Belief:", belief)
    print("  Direction:", direction)
    print("  Ticker:", ticker)
    print("  Asset Class:", asset_class)
    print("  Confidence:", confidence)
    print("  Goal Type:", goal_type)
    print("  Multiplier:", multiplier)
    print("  Timeframe:", timeframe)
    print("  Risk Profile:", risk_profile)

    # ✅ Adjust suggested allocation based on risk profile
    def adjust_allocation(base_percent):
        if risk_profile == "conservative":
            return f"{int(base_percent * 0.6)}%"
        elif risk_profile == "aggressive":
            return f"{int(base_percent * 1.4)}%"
        return f"{base_percent}%"

    # === 🎯 Goal-Based Strategy Logic ===
    if goal_type == "double_money" and multiplier and multiplier >= 2.0:
        if asset_class == "options":
            if direction == "up":
                return {
                    "type": "Aggressive Call Spread",
                    "description": f"Buy {ticker} {int(latest_price * 1.05)}c / Sell {ticker} {int(latest_price * 1.15)}c",
                    "risk_level": "high",
                    "suggested_allocation": adjust_allocation(15),
                    "explanation": "This bullish spread offers high upside while managing cost—ideal for targeting 2x returns."
                }
            elif direction == "down":
                return {
                    "type": "Aggressive Put Spread",
                    "description": f"Buy {ticker} {int(latest_price * 0.95)}p / Sell {ticker} {int(latest_price * 0.85)}p",
                    "risk_level": "high",
                    "suggested_allocation": adjust_allocation(15),
                    "explanation": "This bearish spread limits risk while leveraging downside—aligned with your doubling goal."
                }
            else:
                return {
                    "type": "Long Straddle",
                    "description": f"Buy {ticker} {int(latest_price)}c + Buy {ticker} {int(latest_price)}p",
                    "risk_level": "high",
                    "suggested_allocation": adjust_allocation(20),
                    "explanation": "Straddles profit from large moves in any direction—best when direction is unclear but goal is high return."
                }

        elif asset_class == "stock":
            return {
                "type": "Leveraged ETF",
                "description": f"Buy 2x or 3x leveraged ETF related to {ticker}",
                "risk_level": "high",
                "suggested_allocation": adjust_allocation(20),
                "explanation": "Leveraged ETFs offer magnified exposure—ideal if you're targeting aggressive returns."
            }

    elif goal_type == "hedge":
        return {
            "type": "Protective Put",
            "description": f"Buy {ticker} {int(latest_price * 0.95)}p to hedge downside",
            "risk_level": "low",
            "suggested_allocation": adjust_allocation(10),
            "explanation": "Protective puts cap your downside—perfect for hedging an existing position."
        }

    elif goal_type == "income":
        return {
            "type": "Cash-Secured Put",
            "description": f"Sell {ticker} {int(latest_price * 0.95)}p for monthly income",
            "risk_level": "medium",
            "suggested_allocation": adjust_allocation(20),
            "explanation": "Selling puts generates income—works best for neutral-to-bullish views with capital to cover."
        }

    # === 🧭 Direction-Based Strategy Logic (Fallback) ===
    if asset_class == "options":
        if direction == "up":
            return {
                "type": "Call",
                "description": f"Buy {ticker} {int(latest_price * 1.05)}c",
                "risk_level": "medium",
                "suggested_allocation": adjust_allocation(25),
                "explanation": "Buying a call is a straightforward bullish bet with defined risk."
            }
        elif direction == "down":
            return {
                "type": "Put",
                "description": f"Buy {ticker} {int(latest_price * 0.95)}p",
                "risk_level": "medium",
                "suggested_allocation": adjust_allocation(25),
                "explanation": "Buying a put gives you direct downside exposure—good for bearish views."
            }

    elif asset_class == "stock":
        if direction == "up":
            return {
                "type": "Buy Stock",
                "description": f"Buy {ticker} at market price",
                "risk_level": "low",
                "suggested_allocation": adjust_allocation(30),
                "explanation": "Buying stock directly is the most straightforward long strategy with low risk."
            }
        elif direction == "down":
            return {
                "type": "Inverse ETF",
                "description": f"Buy inverse ETF or short {ticker}",
                "risk_level": "high",
                "suggested_allocation": adjust_allocation(10),
                "explanation": "Inverse ETFs or shorting can capture downside moves—best for high conviction bearish beliefs."
            }

    # === 🛑 Final Fallback ===
    return {
        "type": "Default Strategy",
        "description": f"Analyze {ticker} manually",
        "risk_level": "unknown",
        "suggested_allocation": adjust_allocation(10),
        "explanation": "No clear strategy detected. Consider refining your belief or reviewing manually."
    }
