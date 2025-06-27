# backend/strategy_outcome_logger.py

import csv
import os
from datetime import datetime

# 📍 Path to the outcome CSV file
OUTCOME_LOG = os.path.join(os.path.dirname(__file__), "strategy_outcomes.csv")

def log_strategy_outcome(strategy: dict, belief: str, ticker: str, pnl_percent: float, result: str, notes: str = ""):
    """
    Logs the outcome of an executed strategy to a CSV file.

    Parameters:
    - strategy (dict): The strategy dict returned by select_strategy()
    - belief (str): Original belief text from user
    - ticker (str): Ticker traded
    - pnl_percent (float): Profit or loss as a percentage (e.g. 12.5 or -8.3)
    - result (str): One of 'win', 'loss', or 'neutral'
    - notes (str): Optional string to tag the entry (e.g. 'user-verified')
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

# 🧪 Local test block — run this file directly to simulate a logged result
if __name__ == "__main__":
    # Fake strategy for testing
    test_strategy = {
        "type": "bull call spread",
        "risk_level": "high",
        "description": "Buy AAPL 200c / Sell AAPL 215c",
        "suggested_allocation": "20%",
        "explanation": "Bullish strategy"
    }

    # Simulated logging call
    log_strategy_outcome(
        strategy=test_strategy,
        belief="I think AAPL will rise after earnings",
        ticker="AAPL",
        pnl_percent=18.25,
        result="win",
        notes="simulated test"
    )
