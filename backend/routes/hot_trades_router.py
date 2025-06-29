# backend/routes/hot_trades_router.py
# ✅ Exposes a public /hot_trades endpoint to show trending strategies

from fastapi import APIRouter
from typing import List, Dict, Any
import json
import os
from collections import Counter

router = APIRouter()

STRATEGY_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "strategy_log.json")

@router.get("/hot_trades", response_model=List[Dict[str, Any]])
def get_hot_trades():
    """
    Returns top 5 most frequently suggested strategies over the past 100 entries.
    """
    if not os.path.exists(STRATEGY_LOG_FILE):
        return []

    with open(STRATEGY_LOG_FILE, "r") as f:
        try:
            logs = json.load(f)[-100:]  # Only look at most recent 100 logs
        except json.JSONDecodeError:
            return []

    # Count strategy types
    strategy_counter = Counter()
    examples = {}

    for entry in logs:
        raw_strat = entry.get("strategy", {})

        # 👇 Safely parse if strategy is stringified JSON
        if isinstance(raw_strat, str):
            try:
                strat = json.loads(raw_strat)
            except json.JSONDecodeError:
                continue  # skip malformed entries
        elif isinstance(raw_strat, dict):
            strat = raw_strat
        else:
            continue

        strat_type = strat.get("type", "unknown")
        strategy_counter[strat_type] += 1
        if strat_type not in examples:
            examples[strat_type] = strat

    # Return top 5 strategies with metadata
    top_strats = strategy_counter.most_common(5)
    result = []

    for strat_type, count in top_strats:
        strat = examples[strat_type]
        strat["usage_count"] = count
        result.append(strat)

    return result
