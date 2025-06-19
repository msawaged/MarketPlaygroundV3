# backend/ai_engine/ai_engine.py

"""
This module powers the core belief-to-strategy AI logic.
It parses user beliefs and uses pre-trained models to generate
custom multi-asset trading strategies.
"""

from backend.belief_parser import parse_belief  # ✅ Correct absolute import for Render
from backend.strategy_selector import select_strategy  # ✅ Selects best-fit strategy
from backend.asset_selector import select_asset_class  # ✅ Determines whether to use stocks, options, crypto, etc.
from backend.market_data import get_latest_price, get_weekly_high_low  # ✅ Live pricing tools

def run_ai_engine(belief: str) -> dict:
    """
    Main function to process user belief and generate a strategy.

    Args:
        belief (str): Natural language belief, e.g. "TSLA will go down next week"

    Returns:
        dict: Suggested strategy with metadata
    """

    # Step 1: Parse belief into tags, direction, and ticker
    parsed = parse_belief(belief)
    direction = parsed.get("direction")
    ticker = parsed.get("ticker")
    tags = parsed.get("tags", [])
    confidence = parsed.get("confidence", 0.5)

    # Step 2: Choose asset class (e.g., options, stock, ETF) based on belief
    asset_class = select_asset_class(tags, ticker)

    # Step 3: Get market price info for the ticker
    price_info = get_latest_price(ticker)
    high_low_info = get_weekly_high_low(ticker)

    # Step 4: Generate a recommended strategy based on all inputs
    strategy = select_strategy(
        belief=belief,
        direction=direction,
        ticker=ticker,
        asset_class=asset_class,
        price_info=price_info,
        confidence=confidence
    )

    # Step 5: Return final structured response
    return {
        "strategy": strategy,
        "ticker": ticker,
        "asset_class": asset_class,
        "tags": tags,
        "direction": direction,
        "price_info": price_info,
        "high_low": high_low_info,
        "confidence": confidence
    }
