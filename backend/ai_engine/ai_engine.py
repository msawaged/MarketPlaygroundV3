# backend/ai_engine/ai_engine.py

"""
Main AI Engine module — translates natural language beliefs
into trading strategies using intelligent parsing and strategy selection.
"""

from backend.belief_parser import parse_belief               # ✅ Belief → direction, ticker, tags
from backend.strategy_selector import select_strategy        # ✅ Chooses strategy based on all inputs
from backend.asset_selector import select_asset_class        # ✅ Infers appropriate asset class
from backend.market_data import get_latest_price, get_weekly_high_low  # ✅ Price info
from backend.goal_parser import parse_goal                   # ✅ Parses prompts like "2x my money"

def run_ai_engine(belief: str, risk_profile: str = "moderate") -> dict:
    """
    Main function to turn user belief into a complete strategy suggestion.

    Args:
        belief (str): e.g. "I want to 2x my money betting TSLA will pop next week"
        risk_profile (str): e.g. "conservative", "moderate", "aggressive"

    Returns:
        dict: Structured recommendation with strategy, asset class, price info, etc.
    """

    # ✅ Step 1: Parse belief into direction, ticker, tags, and confidence
    parsed = parse_belief(belief)
    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)

    # ✅ Step 2: Parse user goal from belief (e.g. double money, hedge, etc.)
    goal = parse_goal(belief)
    goal_type = goal.get("goal_type")
    multiplier = goal.get("multiplier")
    timeframe = goal.get("timeframe")

    # ✅ Step 3: Choose asset class (e.g. options, stock, ETF) based on tags and ticker
    asset_class = select_asset_class(tags, ticker)

    # ✅ Step 4: Get current price and recent high/low for strategy calculation
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

    # ✅ Debug Print All Parsed Data for Diagnosis
    print("\n🔍 [AI ENGINE DEBUG INFO]")
    print(f"Belief: {belief}")
    print(f"→ Ticker: {ticker}")
    print(f"→ Direction: {direction}")
    print(f"→ Tags: {tags}")
    print(f"→ Confidence: {confidence}")
    print(f"→ Goal Type: {goal_type}")
    print(f"→ Multiplier: {multiplier}")
    print(f"→ Timeframe: {timeframe}")
    print(f"→ Asset Class: {asset_class}")
    print(f"→ Risk Profile: {risk_profile}")
    print(f"→ Price Info: {price_info['latest']}")
    print(f"→ High/Low Info: {high_low_info}")
    print("🧠 Selecting best strategy...\n")

    # ✅ Step 5: Generate strategy based on all available info
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
        risk_profile=risk_profile   # ✅ New argument
    )

    # ✅ Step 6: Generate user-friendly explanation for the strategy
    explanation = generate_strategy_explainer(
        belief, strategy, direction, goal_type, multiplier, timeframe, ticker
    )

    # ✅ Step 7: Return full response object
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
        "risk_profile": risk_profile,
        "explanation": explanation  # ✅ Human-readable rationale
    }


def generate_strategy_explainer(belief, strategy, direction, goal_type, multiplier, timeframe, ticker):
    """
    Creates a simple explanation for why the selected strategy was chosen.
    This is used to help users understand the logic behind the recommendation.
    """
    base = f"Based on your belief: '{belief}', "

    if goal_type == "double_money":
        base += f"you want to double your money"
        if timeframe:
            base += f" within {timeframe}"
        base += ". "

    if direction == "up":
        base += f"The system interpreted this as a bullish outlook on {ticker}. "
    elif direction == "down":
        base += f"The system interpreted this as a bearish view on {ticker}. "
    elif direction == "neutral":
        base += f"The system saw this as expecting volatility in {ticker}. "

    base += f"Thus, the '{strategy['type']}' strategy was chosen to match your objective."

    return base
