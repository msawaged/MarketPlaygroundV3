# ai_engine.py
# Main engine: converts a belief into a trade strategy using AI/ML helpers

from belief_parser import clean_belief, detect_asset_and_direction
from strategy_selector import select_strategy


def run_ai_engine(belief: str) -> dict:
    """
    Orchestrates the belief analysis pipeline.

    Parameters:
    - belief (str): The user's natural language statement.

    Returns:
    - dict: A dictionary with asset, direction, strategy details.
    """

    # Step 1: Preprocess the belief to clean punctuation/noise
    cleaned = clean_belief(belief)

    # Step 2: Use ML to detect asset class and direction (up/down/neutral)
    asset_info = detect_asset_and_direction(cleaned)
    asset_class = asset_info.get("asset_class")
    direction = asset_info.get("direction")
    confidence = asset_info.get("confidence", 0.5)  # Default if missing

    # Safety check
    if not asset_class or not direction:
        return {"error": "Could not detect asset class or direction."}

    # Step 3: Select a strategy based on those predictions
    strategy = select_strategy(asset_class, direction, confidence)

    # Step 4: Return final strategy object
    return {
        "asset_class": asset_class,
        "direction": direction,
        "confidence": confidence,
        "strategy": strategy,
    }
