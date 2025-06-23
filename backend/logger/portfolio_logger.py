# backend/logger/portfolio_logger.py
# ✅ Handles logging and retrieval of user trade history for portfolio tracking

import os
import json
from datetime import datetime
from typing import List, Dict, Any

# 📍 Path to portfolio log file
PORTFOLIO_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "portfolio_log.json")

def log_trade(user_id: str, trade_data: Dict[str, Any]):
    """
    Logs a user's trade entry to the portfolio_log.json.

    Args:
        user_id (str): Identifier for the user
        trade_data (dict): The trade data to log (e.g., ticker, strategy, etc.)
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "trade": trade_data
    }

    if os.path.exists(PORTFOLIO_LOG_FILE):
        with open(PORTFOLIO_LOG_FILE, "r") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(entry)
    with open(PORTFOLIO_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

def get_user_portfolio(user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves the full portfolio (logged trades) for a specific user.

    Args:
        user_id (str): User identifier

    Returns:
        List[Dict]: List of trade entries
    """
    if not os.path.exists(PORTFOLIO_LOG_FILE):
        return []

    with open(PORTFOLIO_LOG_FILE, "r") as f:
        logs = json.load(f)

    return [entry for entry in logs if entry["user_id"] == user_id]
