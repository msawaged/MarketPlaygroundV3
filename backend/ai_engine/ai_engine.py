# backend/ai_engine/ai_engine.py

"""
Main AI Engine module — translates natural language beliefs
into trading strategies using intelligent parsing and strategy selection.
"""

from backend.belief_parser import parse_belief               # ✅ Belief → direction, ticker, tags
from backend.strategy_selector import select_strategy        # ✅ Chooses strategy based on all inputs
from backend.asset_selector import select_asset_class        # ✅ Infers appropriate asset class
from backend.market_data import get_latest_price, get_weekly_high_low  # ✅ Price info
from backend.goal_parser import parse_goal                   # ✅ NEW: Parses goal prompts like "2x my money"

def run_ai_engine(belief: str) -> dict:
    """
    Main function to turn user belief into a complete strategy suggestion.

    Args:
        belief (str): e.g. "I want to 2x my money betting TSLA will pop next week"

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
    latest = get_latest_price(ticker)
    price_info = {"latest": latest}  # ✅ FIXED: wrap float in dict
    high_low_info = get_weekly_high_low(ticker)

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
        timeframe=timeframe
    )

    # ✅ Step 6: Return full response object
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
        "timeframe": timeframe
    }
