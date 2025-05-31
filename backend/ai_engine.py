# ai_engine.py
# Translates a natural-language market belief into a full options strategy,
# dynamically detecting the ticker and handling “slow” / neutral prompts.

def process_prompt(prompt):
    """
    Input:  natural-language string, e.g. "TSLA will have a slow day"
    Output: dict with keys:
      - type: strategy name
      - example: full Buy/Sell legs + detected ticker + expiry
      - payout: multiplier string
      - mode: game mode
    """
    prompt = prompt.lower()

    # 1) Detect a ticker in the prompt (basic list—expand as you like)
    tickers = ["tsla", "nvda", "aapl", "spy", "qqq"]
    detected = next((t for t in tickers if t in prompt), "AAPL").upper()

    # 2) Check for bearish language → Put Spread
    bearish = ["crash", "drop", "tank", "plummet", "bearish"]
    if any(word in prompt for word in bearish):
        return {
            "type": "Put Spread",
            "example": f"Buy {detected} 400p / Sell {detected} 395p, Exp. Tomorrow",
            "payout": "1.8x",
            "mode": "1v1"
        }

    # 3) Check for bullish language → Call Spread
    bullish = ["skyrocket", "pump", "explode", "bullish"]
    if any(word in prompt for word in bullish):
        return {
            "type": "Call Spread",
            "example": f"Buy {detected} 180c / Sell {detected} 185c, Exp. Friday",
            "payout": "2.1x",
            "mode": "Solo"
        }

    # 4) Check for neutral/slow language → Iron Condor
    neutral = ["flat", "neutral", "±", "won't move", "10%", "slow", "sluggish", "slow day"]
    if any(word in prompt for word in neutral):
        return {
            "type": "Iron Condor",
            "example": (
                f"Sell {detected} 420c / Buy {detected} 430c / "
                f"Sell {detected} 390p / Buy {detected} 380p, Exp. Friday"
            ),
            "payout": "2.4x",
            "mode": "AI Suggest"
        }

    # 5) Fallback = simple call spread on the detected ticker
    return {
        "type": "Default Strategy",
        "example": f"Buy {detected} 150c / Sell {detected} 155c, Exp. Friday",
        "payout": "1.9x",
        "mode": "Solo"
    }
