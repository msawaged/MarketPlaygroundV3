# backend/ai_engine/goal_evaluator.py

"""
This module evaluates financial goals mentioned in a user belief
(e.g. 'double my money', '5x', 'make $1000') and returns a structured dictionary.
"""

import re
from typing import Optional, Dict

def evaluate_goal_from_belief(belief: str) -> Dict[str, Optional[float]]:
    """
    Parses the user belief and extracts structured goal info:
    - goal_type (e.g. "multiply", "profit_target", "preserve_capital", "unspecified")
    - multiplier (e.g. 2.0 for 2x)
    - timeframe (optional, not implemented yet but reserved)

    Args:
        belief (str): User input string

    Returns:
        dict: {
            "goal_type": str,
            "multiplier": Optional[float],
            "timeframe": Optional[str]  # Reserved for future use
        }
    """

    belief = belief.lower()
    goal_type = "unspecified"
    multiplier = None
    timeframe = None  # 🔮 Future: extract durations like "in 3 months", "by next week"

    # ✅ Handle "2x", "5x", etc.
    match_x = re.search(r"(\d+(\.\d+)?)x", belief)
    if match_x:
        multiplier = float(match_x.group(1))
        goal_type = "multiply"

    # ✅ Handle phrases like "double my money", "triple my money"
    elif "double my money" in belief:
        goal_type = "multiply"
        multiplier = 2.0
    elif "triple my money" in belief:
        goal_type = "multiply"
        multiplier = 3.0

    # ✅ Handle dollar targets like "make $1000", "earn $500"
    elif match := re.search(r"(make|earn)\s*\$?(\d+(\.\d+)?)", belief):
        goal_type = "profit_target"
        multiplier = float(match.group(2))

    # ✅ Handle protective or ri***REMOVED***averse language
    elif "preserve capital" in belief or "protect my downside" in belief:
        goal_type = "preserve_capital"
        multiplier = None

    # ✅ Return structured dictionary
    return {
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe
    }
