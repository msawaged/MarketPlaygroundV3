# backend/strategy_outcome_logger.py

"""
Logs and tracks the performance of executed strategies (win/loss/PnL).
"""

import csv
import os
from datetime import datetime
from typing import List, Dict

# 📍 CSV log file path
OUTCOME_LOG = os.path.join(os.path.dirname(__file__), "strategy_outcomes.csv")

def log_strategy_outcome(strategy: dict, belief: str, ticker: str, pnl_percent: float, result: str, notes: str = ""):
    """
    Appends a strategy outcome to the log file for future analysis and leaderboard generation.

    Args:
        strategy (dict): Strategy returned by the AI engine
        belief (str): Original user belief
        ticker (str): Ticker traded
        pnl_percent (float): Strategy return (e.g., 12.5 for +12.5%)
        result (str): One of ['win', 'loss', 'neutral']
        notes (str): Optional annotation (e.g., 'verified', 'auto-eval', etc.)
    """
    log_entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "belief": belief,
        "strategy": strategy.get("type", "unknown"),
        "ticker": ticker,
        "pnl_percent": round(pnl_percent, 2),
        "result": result,
        "risk": strategy.get("risk_level", "unknown"),
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
    Reads the full list of logged strategy outcomes from the CSV file.

    Returns:
        List[Dict]: Each entry is one strategy outcome log.
    """
    if not os.path.exists(OUTCOME_LOG):
        return []

    with open(OUTCOME_LOG, mode="r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)

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
        notes="simulated test"
    )
