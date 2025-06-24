# backend/goal_parser.py

import re

def parse_goal(prompt: str) -> dict:
    """
    Parses a user prompt for a financial goal like:
    - "2x my money"
    - "protect against downside"
    - "generate monthly income"
    - "maximize upside in the next month"

    Returns a dictionary with:
    - goal_type: 'double_money', 'hedge', 'income', 'maximize', 'unspecified'
    - multiplier: Optional float if a return target like "2x" is detected
    - timeframe: Optional string for time-based objectives (e.g., "next week")
    """

    prompt = prompt.lower()
    result = {
        "goal_type": "unspecified",
        "multiplier": None,
        "timeframe": None
    }

    # ✅ Detect multipliers like "2x", "3x", etc.
    multiplier_match = re.search(r'(\d+(\.\d+)?)x', prompt)
    if multiplier_match:
        result["goal_type"] = "double_money"
        result["multiplier"] = float(multiplier_match.group(1))

    # ✅ Detect downside protection or hedging goals
    if "protect" in prompt or "hedge" in prompt or "limit loss" in prompt or "reduce risk" in prompt:
        result["goal_type"] = "hedge"

    # ✅ Detect income generation goals
    if "generate income" in prompt or "monthly income" in prompt or "income strategy" in prompt:
        result["goal_type"] = "income"

    # ✅ Detect growth/maximization goals
    if "maximize" in prompt or "grow" in prompt or "increase returns" in prompt:
        result["goal_type"] = "maximize"

    # ✅ Detect common timeframe phrases
    timeframe_match = re.search(r"(this week|next week|this month|next month|in \d+ (day|week|month)s?)", prompt)
    if timeframe_match:
        result["timeframe"] = timeframe_match.group(1)

    return result
