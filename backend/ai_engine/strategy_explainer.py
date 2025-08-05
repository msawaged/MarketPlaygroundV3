"""
strategy_explainer.py — Converts structured strategy objects into natural language explanations.
Used by ai_engine.py to make outputs understandable for end-users and training logs.
"""

def generate_strategy_explainer(strategy: dict, belief: str = "", ticker: str = "") -> str:
    """
    Generate a human-readable explanation for a given strategy.
    
    Args:
        strategy (dict): The structured strategy dictionary.
        belief (str): Optional original belief text for context.
        ticker (str): Optional ticker symbol involved in the strategy.
        
    Returns:
        str: A detailed explanation of the strategy in plain English.
    """
    try:
        strategy_type = strategy.get("type", "unknown").lower()
        expiration = strategy.get("expiration", "an upcoming date")
        trade_legs = strategy.get("trade_legs", [])

        if strategy_type == "bull call spread":
            return (
                f"This is a bullish options strategy involving buying a call at a lower strike and "
                f"selling a call at a higher strike, both with the same expiration ({expiration}). "
                f"It profits if {ticker} rises before {expiration}, while limiting potential loss."
            )

        elif strategy_type == "bear put spread":
            return (
                f"This bearish options strategy involves buying a put and selling another put at a lower strike, "
                f"both expiring on {expiration}. It profits if {ticker} falls significantly before then."
            )

        elif strategy_type == "call option":
            return (
                f"This strategy involves buying a call option on {ticker}, giving you the right to buy the stock "
                f"at a specific strike price before {expiration}. Profits increase if {ticker} rises."
            )

        elif strategy_type == "put option":
            return (
                f"This involves purchasing a put option on {ticker}, allowing you to sell the stock at a set price "
                f"before {expiration}. It profits if {ticker} drops below the strike price."
            )

        elif strategy_type == "long stock":
            return (
                f"This strategy involves purchasing shares of {ticker} directly, expecting the price to increase. "
                f"There is no expiration — you hold the stock until you choose to sell."
            )

        elif strategy_type == "short stock":
            return (
                f"This is a short-selling strategy where you borrow and sell {ticker} stock now, hoping to buy it back "
                f"at a lower price. It profits if the stock drops."
            )

        elif strategy_type == "bond ladder":
            return (
                f"This strategy involves buying bonds with staggered maturities (a 'ladder') to spread interest rate risk "
                f"and provide steady returns. Useful for long-term income."
            )

        elif strategy_type == "forex long":
            return (
                f"This is a long position on a currency pair. You profit if the base currency strengthens relative to the quote."
            )

        elif strategy_type == "forex short":
            return (
                f"This is a short position on a currency pair. You profit if the base currency weakens relative to the quote."
            )

        else:
            # Generic fallback based on trade legs
            leg_descriptions = []
            for leg in trade_legs:
                action = leg.get("action", "N/A")
                opt_type = leg.get("option_type", "")
                strike = leg.get("strike_price", "unknown strike")
                leg_descriptions.append(f"{action} {opt_type} @ {strike}")

            legs_str = "; ".join(leg_descriptions) if leg_descriptions else "various legs"
            return (
                f"This strategy consists of {legs_str} expiring on {expiration}. "
                f"It is designed to express a view on {ticker}'s price movement."
            )

    except Exception as e:
        return f"Explanation unavailable due to error: {str(e)}"
