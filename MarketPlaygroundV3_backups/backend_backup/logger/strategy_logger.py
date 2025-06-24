# backend/logger/strategy_logger.py
# ✅ Handles strategy logging and history retrieval per user

import os
import json
from datetime import datetime
from typing import List, Dict

# 📁 Path to store the strategy logs (placed one level up from logger/)
STRATEGY_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "strategy_log.json")

def log_strategy(belief: str, strategy: str, user_id: str = "anonymous"):
    """
    Appends a strategy entry to strategy_log.json.
    
    Args:
        belief (str): The original user belief.
        strategy (str): The strategy string returned by the AI engine.
        user_id (str): User identifier (default is 'anonymous').
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "strategy": strategy
    }

    # Load existing log or start a new list
    if os.path.exists(STRATEGY_LOG_FILE):
        with open(STRATEGY_LOG_FILE, "r") as f:
            logs = json.load(f)
    else:
        logs = []

    # Append and save
    logs.append(entry)
    with open(STRATEGY_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

def get_user_strategy_history(user_id: str = "anonymous") -> List[Dict]:
    """
    Returns all saved strategies for a given user.
    
    Args:
        user_id (str): User identifier to filter logs.
    
    Returns:
        List[Dict]: List of strategy log entries for the user.
    """
    if not os.path.exists(STRATEGY_LOG_FILE):
        return []

    with open(STRATEGY_LOG_FILE, "r") as f:
        logs = json.load(f)

    # Filter by user ID
    return [entry for entry in logs if entry.get("user_id") == user_id]
