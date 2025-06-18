# backend/ai_engine/ai_engine.py

from backend.belief_parser import clean_belief, detect_asset_and_direction
from backend.strategy_selector import select_strategy

def run_ai_engine(belief: str) -> dict:
    print(f"[AI ENGINE] Received belief: {belief}")

    # Step 1: Clean the belief
    cleaned = clean_belief(belief)
    print(f"[AI ENGINE] Cleaned belief: {cleaned}")

    # Step 2: Detect direction and asset class
    asset_info = detect_asset_and_direction(cleaned)
    print(f"[AI ENGINE] Parsed direction/confidence: {asset_info}")

    # Step 3: Select a strategy (FIXED ✅ passing direction explicitly)
    direction = asset_info.get("direction", "neutral")
    strategy = select_strategy(asset_info, direction)
    print(f"[AI ENGINE] Strategy: {strategy}")

    # Step 4: Return output as response
    return {
        "input_belief": belief,
        "cleaned": cleaned,
        "asset_info": asset_info,
        "strategy": strategy
    }
