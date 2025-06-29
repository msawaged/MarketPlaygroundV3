# backend/routes/analytics_router.py

from fastapi import APIRouter, Query
from typing import Optional
import pandas as pd
from collections import Counter
import os

router = APIRouter()

@router.get("/strategy_summary")
def strategy_summary(user_id: Optional[str] = None, ticker: Optional[str] = None, days: Optional[int] = None):
    """
    Returns stats from strategy_outcomes.csv including:
    - total count
    - win/loss ratio
    - average PnL
    - most common tickers / strategies
    Optional filters: user_id, ticker, days
    """
    file_path = os.path.join("backend", "strategy_outcomes.csv")
    
    if not os.path.exists(file_path):
        return {"detail": "No outcomes logged yet."}

    df = pd.read_csv(file_path)

    # Filter by user_id if provided
    if user_id and "user_id" in df.columns:
        df = df[df["user_id"] == user_id]

    # Filter by ticker if provided
    if ticker and "ticker" in df.columns:
        df = df[df["ticker"].str.upper() == ticker.upper()]

    # Filter by date if provided
    if days and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df[df["timestamp"] >= pd.Timestamp.now() - pd.Timedelta(days=days)]

    # Final defensive check
    if df.empty or "pnl_percent" not in df.columns:
        return {
            "total_strategies": 0,
            "average_pnl": 0,
            "win_loss_ratio": 0,
            "top_tickers": [],
            "top_strategies": [],
        }

    total = len(df)
    avg_pnl = df["pnl_percent"].mean()
    win_loss_ratio = round((df["pnl_percent"] > 0).sum() / max((df["pnl_percent"] <= 0).sum(), 1), 2)
    top_tickers = [t[0] for t in Counter(df["ticker"]).most_common(3)]
    top_strategies = [s[0] for s in Counter(df["strategy"]).most_common(3)]

    return {
        "total_strategies": total,
        "average_pnl": round(avg_pnl, 4),
        "win_loss_ratio": win_loss_ratio,
        "top_tickers": top_tickers,
        "top_strategies": top_strategies,
    }
