# backend/routes/hot_trades_router.py
# ✅ Enhanced /hot_trades with Polymarket signal blending

from fastapi import APIRouter
from typing import List, Dict, Any
import json
import os
import requests
from collections import Counter

router = APIRouter()

STRATEGY_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "strategy_log.json")

@router.get("/hot_trades", response_model=List[Dict[str, Any]])
def get_hot_trades():
    """
    Returns a mix of internal trending strategies + top Polymarket markets.
    """
    hot_trades = []

    # ✅ PART 1: Internal AI trending strategies (same logic as before)
    if os.path.exists(STRATEGY_LOG_FILE):
        try:
            with open(STRATEGY_LOG_FILE, "r") as f:
                logs = json.load(f)[-100:]
        except json.JSONDecodeError:
            logs = []
    else:
        logs = []

    strategy_counter = Counter()
    examples = {}

    for entry in logs:
        raw_strat = entry.get("strategy", {})
        if isinstance(raw_strat, str):
            try:
                strat = json.loads(raw_strat)
            except json.JSONDecodeError:
                continue
        elif isinstance(raw_strat, dict):
            strat = raw_strat
        else:
            continue

        strat_type = strat.get("type", "unknown")
        strategy_counter[strat_type] += 1
        if strat_type not in examples:
            examples[strat_type] = strat

    top_strats = strategy_counter.most_common(5)
    for strat_type, count in top_strats:
        strat = examples[strat_type]
        strat["usage_count"] = count
        strat["source"] = "AI Feedback"
        hot_trades.append(strat)

    # ✅ PART 2: Add Polymarket trends (no API key required)
    try:
        poly_res = requests.get("https://api.polymarket.com/v3/markets", timeout=5)
        if poly_res.status_code == 200:
            data = poly_res.json()
            top_markets = sorted(
                data.get("markets", []), 
                key=lambda x: x.get("volume24Hr", 0), 
                reverse=True
            )[:5]

            for market in top_markets:
                hot_trades.append({
                    "type": f"Polymarket: {market.get('question', 'Unknown')}",
                    "trade_legs": [],
                    "target_return": "Dynamic",
                    "max_loss": "Limited",
                    "time_to_target": "Market Resolution",
                    "explanation": market.get("description", ""),
                    "usage_count": int(market.get("volume24Hr", 0)),
                    "source": "Polymarket"
                })
    except Exception as e:
        print(f"⚠️ Failed to fetch Polymarket: {e}")

    return hot_trades
