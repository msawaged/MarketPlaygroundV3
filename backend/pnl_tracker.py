# backend/pnl_tracker.py

"""
Live PnL and equity snapshot engine for real-time dashboard use.
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import json

# Load environment variables
load_dotenv()
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

SNAPSHOT_LOG_PATH = os.path.join("backend", "equity_snapshots.json")


def get_live_pnl():
    """
    Returns open PnL across all positions + current equity.
    """
    try:
        positions = requests.get(f"{ALPACA_BASE_URL}/v2/positions", headers=HEADERS).json()
        account = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=HEADERS).json()

        total_unrealized = sum(float(p.get("unrealized_pl", 0)) for p in positions)
        equity = float(account.get("equity", 0))

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "open_unrealized_pl": round(total_unrealized, 2),
            "equity": round(equity, 2)
        }

    except Exception as e:
        print(f"[ERROR] Failed to get PnL snapshot: {e}")
        return {"error": str(e)}


def log_equity_snapshot():
    """
    Saves current equity and PnL to a daily log file.
    """
    snapshot = get_live_pnl()
    if "error" in snapshot:
        return snapshot

    if not os.path.exists(SNAPSHOT_LOG_PATH):
        with open(SNAPSHOT_LOG_PATH, "w") as f:
            json.dump([], f)

    with open(SNAPSHOT_LOG_PATH, "r+") as f:
        data = json.load(f)
        data.append(snapshot)
        f.seek(0)
        json.dump(data, f, indent=2)

    return snapshot
