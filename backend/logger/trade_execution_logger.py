# backend/logger/trade_execution_logger.py

"""
Logs all executed trades made via Alpaca to a persistent JSON file.
Each log entry includes the user ID, timestamp, ticker, quantity,
order ID, order status, and average fill price.

This log is used for execution analytics and PnL tracking.
"""

import os
import json
from datetime import datetime

# Path to execution log JSON file
EXECUTION_LOG_PATH = os.path.join("backend", "executed_trades.json")


def log_execution(user_id: str, execution: dict):
    """
    Appends a new executed trade to the persistent log file.

    Args:
        user_id (str): ID of the user making the trade.
        execution (dict): Contains order_id, ticker, quantity, status, filled_avg_price, etc.
    """
    # Create the log file if it doesn't exist
    if not os.path.exists(EXECUTION_LOG_PATH):
        with open(EXECUTION_LOG_PATH, "w") as f:
            json.dump([], f)

    # Add timestamp and user context
    entry = {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "execution": execution
    }

    # Append to the log file
    with open(EXECUTION_LOG_PATH, "r+") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = []

        data.append(entry)
        f.seek(0)
        json.dump(data, f, indent=2)

    print(f"📦 Execution logged for user {user_id}: {execution}")


def get_all_executions(user_id: str = None):
    """
    Retrieves all execution logs, optionally filtered by user ID.

    Args:
        user_id (str, optional): If provided, returns only entries for that user.

    Returns:
        List[dict]: List of execution entries.
    """
    if not os.path.exists(EXECUTION_LOG_PATH):
        return []

    with open(EXECUTION_LOG_PATH, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []

    if user_id:
        return [entry for entry in data if entry.get("user_id") == user_id]
    return data
