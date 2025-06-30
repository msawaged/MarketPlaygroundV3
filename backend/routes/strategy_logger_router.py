# backend/routes/strategy_logger_router.py
# ✅ Handles user strategy history and top performer analysis

from fastapi import APIRouter, HTTPException, Query
from backend.logger.strategy_logger import get_user_strategy_history
import pandas as pd
import os

# Create router instance
router = APIRouter()

@router.get("/history")
def strategy_history(user_id: str = Query(default="anonymous")):
    """
    ✅ Fetch strategy history for a given user.

    Example:
    GET /strategy/history?user_id=test_user

    Returns:
    - JSON list of past strategies for the user
    """
    try:
        history = get_user_strategy_history(user_id)
        return {"user_id": user_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top_performers")
def top_performing_strategies(metric: str = Query(default="pnl"), top_n: int = Query(default=5)):
    """
    ✅ Returns top performing strategies based on a selected metric.

    Query Parameters:
    - metric: "pnl" | "win_rate" | "count"
    - top_n: number of top strategies to return

    Example:
    GET /strategy/top_performers?metric=pnl&top_n=5

    Returns:
    - List of top strategies by avg PnL / win rate / frequency
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="strategy_outcomes.csv not found")

        df = pd.read_csv(path)

        if df.empty or "strategy" not in df.columns:
            raise HTTPException(status_code=400, detail="No strategy data available")

        if metric == "pnl":
            # Average PnL per strategy
            top = df.groupby("strategy")["pnl_percent"].mean().sort_values(ascending=False).head(top_n)
            return top.reset_index().rename(columns={"pnl_percent": "avg_pnl"}).to_dict(orient="records")

        elif metric == "win_rate":
            # Win rate per strategy
            win_df = df[df["result"] == "win"]
            count_total = df.groupby("strategy").size()
            count_wins = win_df.groupby("strategy").size()
            win_rate = (count_wins / count_total).fillna(0).sort_values(ascending=False).head(top_n)
            return win_rate.reset_index().rename(columns={0: "win_rate"}).to_dict(orient="records")

        elif metric == "count":
            # Most frequently used strategies
            top = df["strategy"].value_counts().head(top_n)
            return top.reset_index().rename(columns={"index": "strategy", "strategy": "count"}).to_dict(orient="records")

        else:
            raise HTTPException(status_code=400, detail="Invalid metric. Use 'pnl', 'win_rate', or 'count'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
