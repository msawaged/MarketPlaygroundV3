# backend/routes/strategy_logger_router.py
# ✅ Handles user strategy history, top performers, and summary stats

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
    GET /strategy/history?user_id=test_user
    """
    try:
        history = get_user_strategy_history(user_id)
        return {"user_id": user_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top_performers")
def top_performing_strategies(metric: str = Query(default="pnl"), top_n: int = Query(default=5)):
    """
    ✅ Returns top performing strategies based on selected metric.
    GET /strategy/top_performers?metric=pnl&top_n=5
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="strategy_outcomes.csv not found")

        df = pd.read_csv(path)
        if df.empty or "strategy" not in df.columns:
            raise HTTPException(status_code=400, detail="No strategy data available")

        if metric == "pnl":
            top = df.groupby("strategy")["pnl_percent"].mean().sort_values(ascending=False).head(top_n)
            return top.reset_index().rename(columns={"pnl_percent": "avg_pnl"}).to_dict(orient="records")
        elif metric == "win_rate":
            win_df = df[df["result"] == "win"]
            count_total = df.groupby("strategy").size()
            count_wins = win_df.groupby("strategy").size()
            win_rate = (count_wins / count_total).fillna(0).sort_values(ascending=False).head(top_n)
            return win_rate.reset_index().rename(columns={0: "win_rate"}).to_dict(orient="records")
        elif metric == "count":
            top = df["strategy"].value_counts().head(top_n)
            return top.reset_index().rename(columns={"index": "strategy", "strategy": "count"}).to_dict(orient="records")
        else:
            raise HTTPException(status_code=400, detail="Invalid metric. Use 'pnl', 'win_rate', or 'count'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
def strategy_summary(user_id: str = Query(default=None)):
    """
    ✅ Provides summary statistics about strategies.
    GET /strategy/summary?user_id=tester_001
    Returns:
    - Total strategies logged
    - Avg PnL %
    - Win/Loss ratio
    - Most common tickers and strategies
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="strategy_outcomes.csv not found")

        df = pd.read_csv(path)
        if df.empty:
            raise HTTPException(status_code=400, detail="No strategy data available")

        if user_id:
            df = df[df["user_id"] == user_id]
            if df.empty:
                return {"message": f"No strategies found for user_id: {user_id}"}

        total = len(df)
        avg_pnl = df["pnl_percent"].mean()
        win_ratio = round((df["result"] == "win").mean(), 3)

        top_strategies = df["strategy"].value_counts().head(3).to_dict()
        top_tickers = df["ticker"].value_counts().head(3).to_dict()

        return {
            "user_id": user_id,
            "total_strategies": total,
            "avg_pnl_percent": round(avg_pnl, 2),
            "win_ratio": win_ratio,
            "top_strategies": top_strategies,
            "top_tickers": top_tickers,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
