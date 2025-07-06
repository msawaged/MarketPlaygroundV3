# backend/logger/strategy_logger.py
# ✅ Handles strategy logging, retrieval, and hot trade display

import os
import json
from datetime import datetime
from typing import List, Dict, Any

# 📁 Absolute path to strategy_log.json
STRATEGY_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "strategy_log.json")

def ensure_log_file_exists():
    """
    Creates the log file with an empty list if it doesn't exist.
    Avoids file not found errors in cloud deployments like Render.
    """
    if not os.path.exists(STRATEGY_LOG_FILE):
        try:
            with open(STRATEGY_LOG_FILE, "w") as f:
                json.dump([], f)
        except Exception as e:
            print(f"[LOGGER ERROR] Could not create log file: {e}")

def log_strategy(belief: str, explanation: str, user_id: str = "anonymous", strategy: Dict[str, Any] = None):
    """
    Appends a strategy entry to strategy_log.json.

    Parameters:
    - belief: User's belief string
    - explanation: Strategy reasoning
    - user_id: Identifier for user
    - strategy: Dict containing selected strategy
    """
    ensure_log_file_exists()

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "explanation": explanation,
        "strategy": strategy or {}
    }

    try:
        with open(STRATEGY_LOG_FILE, "r") as f:
            logs = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logs = []

    logs.append(entry)

    try:
        with open(STRATEGY_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"[LOGGER ERROR] Failed to write strategy log: {e}")

def get_user_strategy_history(user_id: str = "anonymous") -> List[Dict[str, Any]]:
    """
    Returns all strategies for a specific user_id from strategy_log.json.
    """
    ensure_log_file_exists()

    try:
        with open(STRATEGY_LOG_FILE, "r") as f:
            logs = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

    # ✅ Normalize user_id and filter precisely
    return [entry for entry in logs if str(entry.get("user_id", "")).strip() == user_id.strip()]

def get_latest_strategies(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Returns the N most recent strategies (global, not user-specific).
    """
    ensure_log_file_exists()

    try:
        with open(STRATEGY_LOG_FILE, "r") as f:
            logs = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

    sorted_logs = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
    return sorted_logs[:limit]
