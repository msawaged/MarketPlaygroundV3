# === FILE: backend/logger/strategy_logger.py ===
# ✅ Handles strategy logging, retrieval, and hot trade display

import os
import json
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# 🔧 Absolute path to strategy_log.json (now in data/)
BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STRATEGY_LOG_FILE = str(DATA_DIR / "strategy_log.json")

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


# === FILE: backend/utils/logger.py ===
# ✅ Unified logging utility: logs to local files + Supabase DB

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# ✅ Load environment variables from .env file
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Setup data directory
BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def write_training_log(message: str, source: str = "unknown"):
    """
    Logs training activity to:
    1. data/last_training_log.txt      — latest log snapshot
    2. data/retrain_worker.log         — full history log
    3. data/last_training_log.json     — JSON used by API
    4. Supabase (training_logs table)  — cloud storage
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"\n🕒 {timestamp} — {source}\n{message}\n"

    # ✅ 1. Save as latest plaintext snapshot
    last_txt_path = str(DATA_DIR / "last_training_log.txt")
    with open(last_txt_path, "w") as f:
        f.write(full_message)

    # ✅ 2. Append to rolling text log
    rolling_log_path = str(DATA_DIR / "retrain_worker.log")
    with open(rolling_log_path, "a") as f:
        f.write(full_message)

    # ✅ 3. Save JSON version for API access
    json_log_path = str(DATA_DIR / "last_training_log.json")
    with open(json_log_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "source": source,
            "message": message
        }, f)

    # ✅ 4. Push to Supabase training_logs table
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/training_logs",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                },
                json={
                    "created_at": timestamp,
                    "source": source,
                    "message": message
                }
            )
            response.raise_for_status()
            print("✅ Supabase log saved")
        except Exception as e:
            print(f"[⚠️ Supabase logging failed] {e}")

    # ✅ Also print to console for Render logs
    print(full_message.strip())


# === FILE: backend/strategy_outcome_logger.py ===
"""
Logs and tracks the performance of executed strategies (win/loss/PnL).
Includes summary statistics for dashboards or leaderboards.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter
from pathlib import Path

# 🔧 CSV log file path (now in data/)
BASE_DIR = Path(__file__).resolve().parents[1]  # repo root
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTCOME_LOG = str(DATA_DIR / "strategy_outcomes.csv")


def _coerce_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _strategy_type(s) -> str:
    """Return a readable strategy type; safe when s is None/not a dict."""
    return s.get("type", "unknown") if isinstance(s, dict) else "BLOCKED"


def _strategy_risk(s) -> str:
    return s.get("risk_level", "unknown") if isinstance(s, dict) else "unknown"


def log_strategy_outcome(strategy: Optional[dict],
                         belief: str,
                         ticker: str,
                         pnl_percent: float,
                         result: str,
                         notes: str = "",
                         user_id: Optional[str] = None,
                         holding_period_days: Optional[int] = None):
    """
    Logs the outcome of a strategy after execution or simulation.
    Safe when `strategy` is None (e.g., blocked/misaligned).
    """
    # If strategy is None, treat as blocked unless caller specified otherwise
    safe_result = result or ("blocked" if strategy is None else "pending")

    log_entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": (user_id or "anonymous"),
        "belief": str(belief or ""),
        "strategy": _strategy_type(strategy),
        "ticker": str(ticker or ""),
        "pnl_percent": round(_coerce_float(pnl_percent, 0.0), 2),
        "result": safe_result,
        "risk": _strategy_risk(strategy),
        "holding_period_days": holding_period_days if holding_period_days is not None else "",
        "notes": notes or "",
    }

    file_exists = os.path.isfile(OUTCOME_LOG)
    with open(OUTCOME_LOG, mode="a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_entry)
        print(f"✅ Strategy outcome logged:\n{log_entry}")


def log_strategy_result(result: Dict) -> None:
    """
    Convenience wrapper that logs directly from the engine `result` dict.
    Handles strategy=None (blocked) without crashing.
    """
    try:
        belief = str(result.get("belief", "") or result.get("input_belief", "") or "")
        user_id = result.get("user_id") or "anonymous"
        ticker = str(result.get("ticker") or "")
        strategy = result.get("strategy")  # may be None
        notes = result.get("notes") or result.get("reason") or "Strategy generated - awaiting execution/feedback"

        # If strategy is None → blocked; else pending by default
        status = "blocked" if not isinstance(strategy, dict) else "pending"

        log_strategy_outcome(
            strategy=strategy,
            belief=belief,
            ticker=ticker,
            pnl_percent=0.0,
            result=status,
            notes=notes,
            user_id=user_id,
            holding_period_days=None,
        )
    except Exception as e:
        print(f"⚠️ Failed to log strategy outcome safely (result wrapper): {e}")


def get_all_outcomes() -> List[Dict]:
    """Returns all strategy outcomes from the log."""
    if not os.path.exists(OUTCOME_LOG):
        return []
    with open(OUTCOME_LOG, mode="r", newline="") as f:
        return list(csv.DictReader(f))


def get_summary_stats(filter_ticker: Optional[str] = None,
                      filter_user: Optional[str] = None) -> Dict:
    """Computes summary statistics over all logged outcomes."""
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
    avg_pnl = sum(_coerce_float(e["pnl_percent"], 0.0) for e in entries) / total
    most_ticker = Counter(e["ticker"] for e in entries).most_common(1)[0][0]
    most_strategy = Counter(e["strategy"] for e in entries).most_common(1)[0][0]

    return {
        "total": total,
        "avg_pnl": round(avg_pnl, 2),
        "win_rate": f"{round((wins / total) * 100, 1)}%",
        "most_common_ticker": most_ticker,
        "most_common_strategy": most_strategy
    }