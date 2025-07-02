# backend/routes/strategy_router.py
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.ai_engine.ai_engine import run_ai_engine  # 🧠 Belief → strategy engine
from backend.feedback_handler import save_feedback_entry  # 💾 Feedback logger
from backend.logger.strategy_logger import log_strategy  # 📝 Strategy history logger
from backend.alpaca_orders import AlpacaExecutor  # 🧾 Unified Alpaca execution

import pandas as pd
import os

router = APIRouter()

# === Request Schemas ===
class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = "anonymous"
    place_order: Optional[bool] = False  # 🆕 Optional flag to execute strategy

class FeedbackRequest(BaseModel):
    belief: str
    strategy: Dict[str, Any]
    feedback: str
    user_id: Optional[str] = "anonymous"

# === POST /strategy/process_belief ===
@router.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    Generates strategy from belief, logs strategy and feedback,
    and optionally executes it via Alpaca.
    """
    result = run_ai_engine(request.belief)
    result["user_id"] = request.user_id

    # ✅ Save to feedback log
    save_feedback_entry(request.belief, result, "auto_generated", request.user_id)

    # ✅ Save to strategy history log
    log_strategy(
        request.belief,
        result.get("explanation", "No explanation"),
        request.user_id,
        result.get("strategy", {})
    )

    # ✅ Optional trade execution
    if request.place_order:
        executor = AlpacaExecutor()
        execution_response = executor.execute_order(result, request.user_id)
        result["execution_result"] = execution_response

    return result

# === POST /strategy/submit_feedback ===
@router.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Saves user feedback on a generated strategy.
    """
    save_feedback_entry(request.belief, request.strategy, request.feedback, request.user_id)
    return {"message": "✅ Feedback saved"}

# === GET /strategy/summary ===
@router.get("/strategy/summary")
def strategy_summary(user_id: Optional[str] = Query(default=None)):
    """
    Returns summary metrics (PnL, win ratio, top strategies/tickers).
    Optionally filter by user_id.
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="strategy_outcomes.csv not found")

        df = pd.read_csv(path)
        if df.empty or "strategy" not in df.columns:
            raise HTTPException(status_code=400, detail="No strategy data available")

        # Optional filtering by user_id
        if user_id:
            df = df[df["user_id"] == user_id]
            if df.empty:
                return {"message": f"No strategies found for user_id: {user_id}"}

        # Compute metrics
        total = len(df)
        avg_pnl = round(df["pnl_percent"].mean(), 2) if "pnl_percent" in df else None
        win_ratio = round((df["result"] == "win").mean(), 2) if "result" in df else None
        top_strategies = df["strategy"].value_counts().head(5).to_dict() if "strategy" in df else {}
        top_tickers = df["ticker"].value_counts().head(5).to_dict() if "ticker" in df else {}

        return {
            "user_id": user_id,
            "total_strategies": total,
            "avg_pnl_percent": avg_pnl,
            "win_ratio": win_ratio,
            "top_strategies": top_strategies,
            "top_tickers": top_tickers
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
