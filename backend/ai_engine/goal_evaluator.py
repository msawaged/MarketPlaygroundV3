# backend/ai_engine/goal_evaluator.py

"""
This module evaluates financial goals mentioned in a user belief,
including multiplier targets (e.g. "2x", "double my money"), profit goals (e.g. "make $1000"),
risk preservation, and timeframes (e.g. "next week", "in 3 months").
"""

import re
from typing import Optional, Dict, Union

def evaluate_goal_from_belief(belief: str) -> Dict[str, Optional[Union[str, float]]]:
    """
    Parses the user belief and extracts structured goal info:
    - goal_type: "multiply", "profit_target", "preserve_capital", or "unspecified"
    - multiplier: Optional[float] (e.g. 2.0 for 2x)
    - timeframe: Optional[str] (e.g. "next week", "in 3 months")

    Args:
        belief (str): Natural language user belief

    Returns:
        dict: {
            "goal_type": str,
            "multiplier": Optional[float],
            "timeframe": Optional[str]
        }
    """
    belief = belief.lower()
    goal_type = "unspecified"
    multiplier = None
    timeframe = None

    # ✅ Match: "2x", "5.5x", etc.
    match_x = re.search(r"(\d+(\.\d+)?)x", belief)
    if match_x:
        multiplier = float(match_x.group(1))
        goal_type = "multiply"

    # ✅ Match: "double my money", "triple my money"
    elif "double my money" in belief:
        goal_type = "multiply"
        multiplier = 2.0
    elif "triple my money" in belief:
        goal_type = "multiply"
        multiplier = 3.0

    # ✅ Match: "make $1000", "earn $500"
    elif re.search(r"(make|earn)\s*\$?(\d+(\.\d+)?)", belief):
        match = re.search(r"(make|earn)\s*\$?(\d+(\.\d+)?)", belief)
        if match:
            goal_type = "profit_target"
            multiplier = float(match.group(2))

    # ✅ Match: Capital preservation
    elif "preserve capital" in belief or "protect my downside" in belief:
        goal_type = "preserve_capital"
        multiplier = None

    # ✅ Timeframe extraction: "next week", "in 3 months", "by Friday", etc.
    time_keywords = [
        r"next\s+(week|month|quarter|year)",
        r"in\s+\d+\s+(day|days|week|weeks|month|months|year|years)",
        r"by\s+(monday|tuesday|wednesday|thursday|friday|next\s+\w+)",
        r"this\s+(week|month|quarter|year)"
    ]
    for pattern in time_keywords:
        match = re.search(pattern, belief)
        if match:
            timeframe = match.group(0)
            break

    return {
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe
    }
