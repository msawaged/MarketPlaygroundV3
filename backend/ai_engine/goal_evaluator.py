# backend/ai_engine/goal_evaluator.py

"""
This module evaluates financial goals mentioned in a user belief,
including multiplier targets (e.g. "2x", "double my money"),
risk intentions (e.g. "hedge", "safe growth", "income"), and timeframes (e.g. "next week").
"""

import re
from typing import Optional, Dict, Union

def evaluate_goal_from_belief(belief: str) -> Dict[str, Optional[Union[str, float]]]:
    """
    Parses the user belief and extracts structured goal info:
    - goal_type: multiply, profit_target, hedge, income, safe_growth, preserve_capital, or unspecified
    - multiplier: Optional[float]
    - timeframe: Optional[str]

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

    # === 🎯 MULTIPLIER GOALS ===
    match_x = re.search(r"(\d+(\.\d+)?)x", belief)
    if match_x:
        multiplier = float(match_x.group(1))
        goal_type = "multiply"
    elif "double my money" in belief:
        goal_type = "multiply"
        multiplier = 2.0
    elif "triple my money" in belief:
        goal_type = "multiply"
        multiplier = 3.0

    # === 💰 PROFIT AMOUNT GOALS ===
    match_profit = re.search(r"(make|earn)\s*\$?(\d+(\.\d+)?)", belief)
    if match_profit:
        goal_type = "profit_target"
        multiplier = float(match_profit.group(2))

    # === 🛡️ HEDGE / PRESERVE GOALS ===
    elif any(kw in belief for kw in ["hedge", "protect", "limit downside", "reduce losses"]):
        goal_type = "hedge"
    elif any(kw in belief for kw in ["preserve capital", "avoid losses"]):
        goal_type = "preserve_capital"

    # === 💸 INCOME GOALS ===
    elif any(kw in belief for kw in ["generate income", "passive income", "monthly income", "extra cash"]):
        goal_type = "income"

    # === 🌱 SAFE GROWTH GOALS ===
    elif any(kw in belief for kw in ["safe growth", "steady returns", "low risk returns", "grow slowly"]):
        goal_type = "safe_growth"

    # === ⏳ TIMEFRAME DETECTION ===
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
