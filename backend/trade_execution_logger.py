# backend/trade_execution_logger.py

"""
Logs real trades submitted via Alpaca (execution-level logging).
Each entry includes order ID, status, quantity, and fill price.
"""

import os
import json
from datetime import datetime

EXECUTION_LOG_DIR = os.path.join("backend", "logs", "executions")
os.makedirs(EXECUTION_LOG_DIR, exist_ok=True)

def log_execution(user_id: str, execution_data: dict):
    """
    Save a trade execution record for a given user.
    """
    timestamp = datetime.utcnow().isoformat()
    execution_data["timestamp"] = timestamp

    filepath = os.path.join(EXECUTION_LOG_DIR, f"{user_id}_executions.json")

    # Load existing logs if any
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            user_log = json.load(f)
    else:
        user_log = []

    user_log.append(execution_data)

    with open(filepath, "w") as f:
        json.dump(user_log, f, indent=2)

    print(f"✅ Logged Alpaca execution for {user_id}")
