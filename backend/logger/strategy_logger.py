# backend/logger/strategy_logger.py
# ✅ Handles strategy logging, retrieval, and hot trade display

import os
import json
from datetime import datetime
from typing import List, Dict, Any

# 📁 Path to store the strategy logs
STRATEGY_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "strategy_log.json")

def log_strategy(belief: str, strategy: Dict[str, Any], user_id: str = "anonymous"):
    """
    Appends a strategy entry to strategy_log.json.

    Parameters:
    - belief (str): The original user belief string.
    - strategy (dict): The strategy object to log.
    - user_id (str): User identifier.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "strategy": strategy
    }

    # Load existing logs or initialize new
    if os.path.exists(STRATEGY_LOG_FILE):
        with open(STRATEGY_LOG_FILE, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
    else:
        logs = []

    logs.append(entry)

    # Save
    with open(STRATEGY_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

def get_user_strategy_history(user_id: str = "anonymous") -> List[Dict[str, Any]]:
    """
    Returns all saved strategies for a given user.
    """
    if not os.path.exists(STRATEGY_LOG_FILE):
        return []

    with open(STRATEGY_LOG_FILE, "r") as f:
        try:
            logs = json.load(f)
        except json.JSONDecodeError:
            return []

    return [entry for entry in logs if entry.get("user_id") == user_id]

def get_latest_strategies(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Returns the most recent N strategies regardless of user.

    Parameters:
    - limit (int): Number of recent strategies to return

    Returns:
    - List of strategy log entries (most recent first)
    """
    if not os.path.exists(STRATEGY_LOG_FILE):
        return []

    with open(STRATEGY_LOG_FILE, "r") as f:
        try:
            logs = json.load(f)
        except json.JSONDecodeError:
            return []

    # Sort by timestamp descending, return top N
    sorted_logs = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
    return sorted_logs[:limit]
