# backend/strategy_outcome_logger.py

"""
Logs and tracks the performance of executed strategies (win/loss/PnL).
Includes summary statistics for dashboards or leaderboards.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter

# 📍 CSV log file path
OUTCOME_LOG = os.path.join(os.path.dirname(__file__), "strategy_outcomes.csv")

def log_strategy_outcome(strategy: dict, belief: str, ticker: str, pnl_percent: float, result: str,
                         notes: str = "", user_id: Optional[str] = None, holding_period_days: Optional[int] = None):
    """
    Logs the outcome of a strategy after execution or simulation.

    Args:
        strategy (dict): Strategy returned by the AI engine
        belief (str): Original belief
        ticker (str): Ticker traded
        pnl_percent (float): Return percentage
        result (str): 'win', 'loss', or 'neutral'
        notes (str): Optional annotation
        user_id (str): Optional user identifier
        holding_period_days (int): Days between belief and outcome evaluation
    """
    log_entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id or "anonymous",
        "belief": belief,
        "strategy": strategy.get("type", "unknown"),
        "ticker": ticker,
        "pnl_percent": round(pnl_percent, 2),
        "result": result,
        "risk": strategy.get("risk_level", "unknown"),
        "holding_period_days": holding_period_days if holding_period_days is not None else "",
        "notes": notes
    }

    file_exists = os.path.isfile(OUTCOME_LOG)
    with open(OUTCOME_LOG, mode="a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_entry)
        print(f"✅ Strategy outcome logged:\n{log_entry}")

def get_all_outcomes() -> List[Dict]:
    """
    Returns all strategy outcomes from the log.

    Returns:
        List[Dict]: Full list of strategy outcome records.
    """
    if not os.path.exists(OUTCOME_LOG):
        return []
    with open(OUTCOME_LOG, mode="r", newline="") as f:
        return list(csv.DictReader(f))

def get_summary_stats(filter_ticker: Optional[str] = None,
                      filter_user: Optional[str] = None) -> Dict:
    """
    Computes summary statistics over all logged outcomes.

    Args:
        filter_ticker (str): If set, limits results to a specific ticker
        filter_user (str): If set, limits results to a specific user_id

    Returns:
        Dict: Summary stats (totals, averages, win/loss ratio, top strategies)
    """
    entries = get_all_outcomes()
    if filter_ticker:
        entries = [e for e in entries if e["ticker"] == filter_ticker]
    if filter_user:
        entries = [e for e in entries if e["user_id"] == filter_user]

    total = len(entries)
    if total == 0:
        return {
            "total": 0,
            "avg_pnl": 0,
            "win_rate": "0%",
            "most_common_ticker": None,
            "most_common_strategy": None
        }

    wins = sum(1 for e in entries if e["result"] == "win")
    avg_pnl = sum(float(e["pnl_percent"]) for e in entries) / total
    most_ticker = Counter(e["ticker"] for e in entries).most_common(1)[0][0]
    most_strategy = Counter(e["strategy"] for e in entries).most_common(1)[0][0]

    return {
        "total": total,
        "avg_pnl": round(avg_pnl, 2),
        "win_rate": f"{round((wins / total) * 100, 1)}%",
        "most_common_ticker": most_ticker,
        "most_common_strategy": most_strategy
    }

# 🧪 Run directly to simulate a test log
if __name__ == "__main__":
    test_strategy = {
        "type": "bull call spread",
        "risk_level": "high",
        "description": "Buy AAPL 200c / Sell AAPL 215c",
        "suggested_allocation": "20%",
        "explanation": "Bullish strategy"
    }

    log_strategy_outcome(
        strategy=test_strategy,
        belief="I think AAPL will rise after earnings",
        ticker="AAPL",
        pnl_percent=18.25,
        result="win",
        notes="simulated test",
        user_id="murad34",
        holding_period_days=7
    )

    print("\n📊 Summary Stats:", get_summary_stats())
