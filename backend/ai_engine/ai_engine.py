"""
Main AI Engine — Translates natural language beliefs into trading strategies.
Integrates belief parsing, goal evaluation, asset class selection, and strategy logic.
"""

import os
from backend.belief_parser import parse_belief
from backend.strategy_selector import select_strategy
from backend.market_data import get_latest_price, get_weekly_high_low
from backend.ai_engine.goal_evaluator import evaluate_goal_from_belief as evaluate_goal
from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
from backend.logger.strategy_logger import log_strategy

# ✅ Known equity tickers to override ETF classification errors
KNOWN_EQUITIES = {
    "AAPL", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "MSFT", "NFLX", "BAC", "JPM", "WMT"
}

def run_ai_engine(belief: str, risk_profile: str = "moderate", user_id: str = "anonymous") -> dict:
    """
    Converts a user belief into a complete trade strategy suggestion.
    """

    # ✅ Step 1: Parse belief into components
    parsed = parse_belief(belief)
    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)
    parsed_asset = parsed.get("asset_class", "options")

    # ✅ Step 2: Goal evaluation
    goal = evaluate_goal(belief)
    goal_type = goal.get("goal_type")
    multiplier = goal.get("multiplier")
    timeframe = goal.get("timeframe")

    # ✅ Step 3: Parse expiry date from timeframe
    expiry_date = parse_timeframe_to_expiry(timeframe) if timeframe else None

    # ✅ Step 4: Fallback for missing ticker
    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"

    # ✅ Step 5: Use parsed asset class — with manual override
    if parsed_asset == "etf" and ticker.upper() in KNOWN_EQUITIES:
        asset_class = "equity"
    else:
        asset_class = parsed_asset

    # ✅ Step 6: Smart override for bond asset class
    if asset_class == "bond" and ticker.upper() == "SPY":
        ticker = "TLT"  # You could also use "BND" depending on your use case

    # ✅ Step 7: Fallback direction if missing
    if not direction:
        if goal_type in ["double_money", "multiply", "safe_growth"]:
            direction = "up"
        elif goal_type in ["hedge", "protect"]:
            direction = "down"
        else:
            direction = "neutral"

    # ✅ Step 8: Market data
    try:
        latest = get_latest_price(ticker)
    except Exception as e:
        print(f"[ERROR] get_latest_price() failed for {ticker}: {e}")
        latest = -1.0

    try:
        high_low = get_weekly_high_low(ticker)
    except Exception as e:
        print(f"[ERROR] get_weekly_high_low() failed for {ticker}: {e}")
        high_low = (-1.0, -1.0)

    price_info = {"latest": latest}

    # 🧠 Debug info
    print("\n🔍 [AI ENGINE DEBUG INFO]")
    print(f"Belief: {belief}")
    print(f"→ Ticker: {ticker}")
    print(f"→ Direction: {direction}")
    print(f"→ Tags: {tags}")
    print(f"→ Confidence: {confidence}")
    print(f"→ Goal Type: {goal_type}")
    print(f"→ Multiplier: {multiplier}")
    print(f"→ Timeframe: {timeframe}")
    print(f"→ Expiry Date: {expiry_date}")
    print(f"→ Asset Class (Parsed): {asset_class}")
    print(f"→ Risk Profile: {risk_profile}")
    print(f"→ Price Info: {latest}")
    print(f"→ High/Low Info: {high_low}")
    print("🧠 Selecting best strategy...\n")

    # ✅ Step 9: Strategy generation
    strategy = select_strategy(
        belief=belief,
        direction=direction,
        ticker=ticker,
        asset_class=asset_class,
        price_info=price_info,
        confidence=confidence,
        goal_type=goal_type,
        multiplier=multiplier,
        timeframe=timeframe,
        expiry_date=expiry_date,
        risk_profile=risk_profile
    )

    # ✅ Step 10: Explanation
    explanation = generate_strategy_explainer(
        belief, strategy, direction, goal_type, multiplier, timeframe, ticker
    )

    # ✅ Step 11: Log strategy
    log_strategy(belief, explanation, user_id, strategy)

    return {
        "strategy": strategy,
        "ticker": ticker,
        "asset_class": asset_class,
        "tags": tags,
        "direction": direction,
        "price_info": price_info,
        "high_low": high_low,
        "confidence": confidence,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe,
        "expiry_date": expiry_date,
        "risk_profile": risk_profile,
        "explanation": explanation,
        "user_id": user_id
    }

def generate_strategy_explainer(belief, strategy, direction, goal_type, multiplier, timeframe, ticker):
    """
    Creates a user-friendly explanation based on belief and selected strategy.
    """
    base = f"Based on your belief: '{belief}', "

    if goal_type in ["double_money", "multiply"]:
        base += "you want to multiply your money"
        if multiplier:
            base += f" by {multiplier}x"
        if timeframe:
            base += f" within {timeframe}"
        base += ". "

    if direction == "up":
        base += f"The system interpreted this as a bullish view on {ticker}. "
    elif direction == "down":
        base += f"The system interpreted this as a bearish outlook on {ticker}. "
    else:
        base += f"The system expects neutral or sideways movement in {ticker}. "

    base += f"Hence, the '{strategy['type']}' strategy was selected to match your objective."
    return base
