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

def run_ai_engine(belief: str, risk_profile: str = "moderate") -> dict:
    """
    Converts a user belief into a complete trade strategy suggestion.

    Args:
        belief (str): e.g. "I want to 2x my money betting TSLA will pop next week"
        risk_profile (str): e.g. "conservative", "moderate", "aggressive"

    Returns:
        dict: Structured trade recommendation
    """

    # ✅ Step 1: Parse belief into components
    parsed = parse_belief(belief)
    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)

    # ✅ Step 2: Parse goal intent (multiplier, timeframe, goal_type)
    goal = evaluate_goal(belief)
    goal_type = goal.get("goal_type")
    multiplier = goal.get("multiplier")
    timeframe = goal.get("timeframe")

    # ✅ Step 3: Convert to expiry date
    expiry_date = parse_timeframe_to_expiry(timeframe) if timeframe else None

    # ✅ Step 4: Infer asset class
    asset_class = select_asset_class(tags, ticker)

    # 🧠 Optional: Fallback logic if ticker is missing
    if not ticker:
        if "qqq" in tags or "nasdaq" in tags:
            ticker = "QQQ"
        elif "spy" in tags or "s&p" in tags:
            ticker = "SPY"
        else:
            ticker = "AAPL"  # hard fallback

    # 🧠 Optional: Smart direction override based on goal
    if not direction:
        if goal_type in ["double_money", "safe_growth"]:
            direction = "up"
        elif goal_type == "hedge":
            direction = "down"
        else:
            direction = "neutral"

    # ✅ Step 5: Market data lookup
    try:
        latest = get_latest_price(ticker)
    except Exception as e:
        print(f"[ERROR] get_latest_price() failed for {ticker}: {e}")
        latest = -1.0

    try:
        high_low_info = get_weekly_high_low(ticker)
    except Exception as e:
        print(f"[ERROR] get_weekly_high_low() failed for {ticker}: {e}")
        high_low_info = (-1.0, -1.0)

    price_info = {"latest": latest}

    # 🔍 Debugging Log
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
    print(f"→ High/Low Info: {high_low_info}")
    print("🧠 Selecting best strategy...\n")

    # ✅ Step 6: Strategy selection
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

    # ✅ Step 7: Strategy explanation for UI
    explanation = generate_strategy_explainer(
        belief, strategy, direction, goal_type, multiplier, timeframe, ticker
    )

    # ✅ Step 8: Output response object
    return {
        "strategy": strategy,
        "ticker": ticker,
        "asset_class": asset_class,
        "tags": tags,
        "direction": direction,
        "price_info": price_info,
        "high_low": high_low_info,
        "confidence": confidence,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe,
        "expiry_date": expiry_date,
        "risk_profile": risk_profile,
        "explanation": explanation
    }


def generate_strategy_explainer(belief, strategy, direction, goal_type, multiplier, timeframe, ticker):
    """
    Explains the reasoning behind the chosen strategy in plain English.
    """
    base = f"Based on your belief: '{belief}', "

    if goal_type == "double_money":
        base += "you want to double your money"
        if timeframe:
            base += f" within {timeframe}"
        base += ". "

    if direction == "up":
        base += f"The system interpreted this as a bullish outlook on {ticker}. "
    elif direction == "down":
        base += f"The system interpreted this as a bearish view on {ticker}. "
    elif direction == "neutral":
        base += f"The system expects volatility in {ticker}. "

    base += f"Thus, the '{strategy['type']}' strategy was chosen to match your objective."
    return base
