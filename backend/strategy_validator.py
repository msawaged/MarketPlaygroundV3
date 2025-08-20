# backend/strategy_validator.py

import re

def parse_percent_move_from_belief(belief: str) -> float:
    """
    Extracts percentage move from a belief string.
    Example: "TSLA will go up 10%" → 10
    """
    match = re.search(r'(\d+(\.\d+)?)\s*%', belief)
    if match:
        return float(match.group(1))
    return None

def estimate_expected_profit_pct(strategy: dict) -> float:
    """
    Roughly estimates profit percent from a strategy dictionary.
    """
    strategy_type = strategy.get("type", "").lower()

    if "long call" in strategy_type:
        return 100.0
    if "bull call spread" in strategy_type:
        return 50.0
    if "buy stock" in strategy_type:
        return 10.0
    if "bond ladder" in strategy_type:
        return 5.0
    return 0.0

def evaluate_strategy_against_belief(belief: str, strategy: dict) -> dict:
    """
    Evaluates whether the strategy would profit if the belief is correct.
    Returns a dictionary of evaluation metrics.
    """
    result = {
        "would_profit": None,
        "estimated_profit_pct": None,
        "valid": False,
        "notes": ""
    }

    percent_move = parse_percent_move_from_belief(belief)
    if percent_move is None:
        result["notes"] = "❌ Could not detect % move in belief"
        return result

    expected_profit = estimate_expected_profit_pct(strategy)
    result["estimated_profit_pct"] = expected_profit

    if expected_profit >= percent_move:
        result["would_profit"] = True
        result["valid"] = True
        result["notes"] = "✅ If belief is true, strategy likely profits"
    else:
        result["would_profit"] = False
        result["notes"] = "⚠️ Strategy may underperform belief"

    return result
