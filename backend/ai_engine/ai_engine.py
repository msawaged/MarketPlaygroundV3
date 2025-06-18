# backend/ai_engine/ai_engine.py
# ✅ Main AI logic that interprets user belief and outputs a strategy

from backend.belief_parser import clean_belief, detect_asset_and_direction
from backend.strategy_selector import select_strategy
from backend.asset_selector import detect_asset_class

def run_ai_engine(user_belief: str) -> dict:
    """
    Main interface to process a user belief into a tradable strategy.

    Args:
        user_belief (str): Natural-language belief, e.g. "TSLA will go up next week"

    Returns:
        dict: Strategy output including type, legs, asset, etc.
    """
    print(f"[AI ENGINE] Received belief: {user_belief}")

    # Step 1: Clean and parse the belief
    cleaned = clean_belief(user_belief)
    print(f"[AI ENGINE] Cleaned belief: {cleaned}")

    # Step 2: Detect asset class, direction, and confidence
    asset_info = detect_asset_and_direction(cleaned)
    print(f"[AI ENGINE] Parsed direction/confidence: {asset_info}")

    # Step 3: Fallback to asset class detector if not explicitly defined
    if not asset_info.get("asset_class"):
        asset_info["asset_class"] = detect_asset_class(cleaned)

    # Step 4: Generate a strategy based on parsed belief
    strategy = select_strategy(asset_info)
    print(f"[AI ENGINE] Selected strategy: {strategy}")

    return strategy
