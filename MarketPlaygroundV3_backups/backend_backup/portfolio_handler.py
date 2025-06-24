# backend/portfolio_handler.py

import os
import json
from datetime import datetime

# === Path to the portfolio data file ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "user_portfolios.json")

# === Load existing data (or return empty dict) ===
def load_portfolios():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Portfolio file corrupted — starting fresh.")
    return {}

# === Save entire data store ===
def save_portfolios(data):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)

# === Save a trade for a user ===
def save_trade(user_id: str, belief: str, strategy: dict):
    portfolios = load_portfolios()
    trade_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "belief": belief,
        "strategy": strategy
    }
    if user_id not in portfolios:
        portfolios[user_id] = []
    portfolios[user_id].append(trade_entry)
    save_portfolios(portfolios)
    print(f"✅ Trade saved for user: {user_id}")

# === Fetch a user's full trade history ===
def get_portfolio(user_id: str):
    portfolios = load_portfolios()
    return portfolios.get(user_id, [])
