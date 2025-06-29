# backend/ai_engine/ai_engine.py

"""
Main AI Engine — Translates natural language beliefs into trading strategies.
Integrates belief parsing, goal evaluation, asset class selection, and strategy logic.
"""

from backend.belief_parser import parse_belief
from backend.strategy_selector import select_strategy
from backend.asset_selector import select_asset_class
from backend.market_data import get_latest_price, get_weekly_high_low
from backend.ai_engine.goal_evaluator import evaluate_goal_from_belief as evaluate_goal
from backend.ai_engine.expiry_utils import parse_timeframe_to_expiry
from backend.logger.strategy_logger import log_strategy  # ✅ Logs strategy for session history
from typing import Optional, Dict

# ✅ Known equity tickers to override ETF classification errors
KNOWN_EQUITIES = {
    "AAPL", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "MSFT", "NFLX", "BAC", "JPM", "WMT"
}

def run_ai_engine(belief: str, risk_profile: str = "moderate", user_id: str = "anonymous") -> dict:
    """
    Converts a user belief into a complete trade strategy suggestion.
    """

    # ✅ Step 1: Parse core belief
    parsed = parse_belief(belief)
    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)
    parsed_asset_class = parsed.get("asset_class", "options")

    # ✅ Step 2: Evaluate user goal from belief
    goal = evaluate_goal(belief)
    goal_type = goal.get("goal_type")
    multiplier = goal.get("multiplier")
    timeframe = goal.get("timeframe")

    # ✅ Step 3: Convert timeframe to expiry date
    expiry_date = parse_timeframe_to_expiry(timeframe) if timeframe else None

    # ✅ Step 4: Ticker fallback and asset class override
    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"

    if parsed_asset_class == "etf" and ticker.upper() in KNOWN_EQUITIES:
        asset_class = "equity"
    elif parsed_asset_class and parsed_asset_class != "options":
        asset_class = parsed_asset_class
    else:
        asset_class = select_asset_class(tags, ticker)

    # ✅ Step 5: Infer direction if not found
    if not direction:
        if goal_type in ["double_money", "multiply", "safe_growth"]:
            direction = "up"
        elif goal_type in ["hedge", "protect"]:
            direction = "down"
        else:
            direction = "neutral"

    # ✅ Step 6: Market data lookups
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

    # 🧠 Debug Info
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
    print(f"→ Asset Class: {asset_class}")
    print(f"→ Risk Profile: {risk_profile}")
    print(f"→ Price Info: {price_info['latest']}")
    print(f"→ High/Low Info: {high_low}")
    print("🧠 Selecting best strategy...\n")

    # ✅ Step 7: ML-powered strategy generation
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

    # ✅ Step 8: Generate explanation
    explanation = generate_strategy_explainer(
        belief, strategy, direction, goal_type, multiplier, timeframe, ticker
    )

    # ✅ Step 9: Log strategy for both session + hot_trades analysis
    log_strategy(belief, explanation, user_id, strategy)  # ✅ Modified to include full strategy

    # ✅ Step 10: Return full response
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

    if goal_type == "double_money" or goal_type == "multiply":
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
