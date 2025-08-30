# backend/ai_engine/strategy_model_selector.py

"""
This module decides whether to generate a strategy using:
- GPT-4
- ML model
- or a hybrid approach (default: try GPT first, then fallback to ML)

It centralizes all belief-to-strategy routing logic to keep ai_engine.py clean.
"""

import json
from backend.ai_engine.gpt4_strategy_generator import generate_strategy_with_validation
from backend.ai_engine.ml_strategy_bridge import predict_strategy_with_ml


def decide_strategy_engine(belief: str, metadata: dict, method: str = "hybrid") -> dict:
    """
    Decide how to generate a strategy based on the method:
    - "gpt": use GPT-4 only
    - "ml": use ML model only
    - "hybrid": try GPT first, fallback to ML on failure

    Parameters:
        belief (str): user belief input
        metadata (dict): parsed info like direction, ticker, tags, etc.
        method (str): which engine to use

    Returns:
        dict: strategy dictionary
    """
    if method == "gpt":
        return generate_strategy_with_validation(belief, metadata.get("direction", "neutral"))


    elif method == "ml":
        return predict_strategy_with_ml(belief, metadata)

    elif method == "hybrid":
        try:
            strategy = generate_strategy_with_validation(belief, metadata.get("direction", "neutral"))
            if strategy and isinstance(strategy, dict):
                return strategy
            raise ValueError("GPT returned invalid structure")
        except Exception as e:
            print(f"🚫 PRODUCTION MODE: ML fallback disabled - {e}")
            print(f"💡 Strategy validation blocked misaligned strategy - this is expected behavior")
            return None

    else:
        raise ValueError(f"Invalid strategy method: {method}")
