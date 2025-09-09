# backend/routes/strategy_router.py

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import math
import json

from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_handler import save_feedback_entry
from backend.logger.strategy_logger import log_strategy
from backend.alpaca_orders import AlpacaExecutor
from backend.utils.logger import write_training_log
from backend.strategy_outcome_logger import log_strategy_outcome, log_strategy_result  # ✅ added safe wrapper

import pandas as pd
import os
from datetime import datetime

router = APIRouter()

def sanitize_json_values(obj):
    """
    Recursively clean inf/nan values that break JSON serialization
    """
    if isinstance(obj, dict):
        return {k: sanitize_json_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj

class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = "anonymous"
    place_order: Optional[bool] = False

class FeedbackRequest(BaseModel):
    belief: str
    strategy: Dict[str, Any]
    feedback: str
    user_id: Optional[str] = "anonymous"

class OutcomeRequest(BaseModel):
    belief: str
    result: str
    pnl_percent: float
    user_id: Optional[str] = "anonymous"

@router.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    🔧 ENHANCED WITH PERFORMANCE MONITORING
    Generates strategy from belief, logs strategy to file and Supabase,
    and optionally executes via Alpaca.
    """
    # 📊 PERFORMANCE MONITORING: Debug print to confirm this function is called
    print("🚨 REAL STRATEGY FUNCTION CALLED! (strategy_router.py)")
    
    # 📊 PERFORMANCE MONITORING: Import metrics storage and start timer
    from backend.routes.debug_router import METRICS
    import time
    start = time.perf_counter()
    
    try:
        # 🤖 AI ENGINE: Generate strategy from user belief
        result = run_ai_engine(request.belief)
        result["user_id"] = request.user_id
        
        # 🧹 DATA CLEANING: Remove inf/nan values that break JSON
        result = sanitize_json_values(result)

        # 💾 FEEDBACK SYSTEM: Auto-save strategy generation as feedback
        save_feedback_entry(request.belief, result, "auto_generated", request.user_id)

        # 📝 STRATEGY LOGGING: Log to strategy files for analysis
        log_strategy(
            request.belief,
            result.get("explanation", "No explanation"),
            request.user_id,
            result.get("strategy", {})
        )

        # 📊 OUTCOME TRACKING: Log initial strategy outcome (safe on strategy=None)
        try:
            # Attach belief/user_id so the logger has full context
            result["belief"] = request.belief
            result["user_id"] = request.user_id
            log_strategy_result(result)  # ✅ safe wrapper: handles strategy=None (BLOCKED)
            # Cosmetic console line:
            strat = result.get("strategy")
            strat_name = strat.get("type", "unknown") if isinstance(strat, dict) else "BLOCKED"
            print(f"🟩 Strategy logged to outcomes: {strat_name} for {result.get('ticker','UNKNOWN')}")
        except Exception as e:
            print(f"⚠️ Failed to log strategy outcome (router): {e}")

        # 🗂️ TRAINING LOG: Save to Supabase for ML training data
        try:
            write_training_log(
                message=f"[STRATEGY GENERATED]\nBelief: {request.belief}\nUser: {request.user_id}\nStrategy: {result.get('strategy', {})}",
                source="strategy_router"
            )
        except Exception as e:
            print(f"[SUPABASE LOG ERROR] {e}")

        # 📈 TRADE EXECUTION: Execute trade via Alpaca if requested
        if request.place_order:
            executor = AlpacaExecutor()
            execution_response = executor.execute_order(result, request.user_id)
            result["execution_result"] = execution_response

        # 📊 PERFORMANCE MONITORING: Log successful completion with timing
        duration = (time.perf_counter() - start) * 1000
        METRICS["response_times"].append(duration)
        METRICS["logs"].append({
            "level": "SUCCESS",
            "message": f"process_belief completed - {duration:.0f}ms",
            "duration": f"{duration:.0f}ms",
            "timestamp": time.strftime("%H:%M:%S")
        })
        
        print(f"🔧 [DEBUG] SUCCESS! Duration: {duration:.0f}ms, Total logs: {len(METRICS['logs'])}")
        return result

    except Exception as e:
        # 📊 PERFORMANCE MONITORING: Log error with timing and details
        duration = (time.perf_counter() - start) * 1000
        METRICS["error_counts"][type(e).__name__] += 1
        METRICS["logs"].append({
            "level": "ERROR",
            "message": f"process_belief failed: {str(e)[:50]}",
            "duration": f"{duration:.0f}ms", 
            "timestamp": time.strftime("%H:%M:%S")
        })
        
        print(f"🔧 [DEBUG] ERROR! {type(e).__name__}: {str(e)[:50]}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Saves user feedback on a generated strategy.
    """
    save_feedback_entry(request.belief, request.strategy, request.feedback, request.user_id)
    return {"message": "✅ Feedback saved"}

@router.post("/mark_outcome")
def mark_strategy_outcome(request: OutcomeRequest):
    """
    Logs actual result (win/loss, PnL%) for a strategy previously generated.
    Appends to strategy_outcomes.csv.
    """
    try:
        path = os.path.join("backend", "strategy_outcomes.csv")
        exists = os.path.exists(path)

        outcome_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "belief": request.belief,
            "result": request.result.lower(),
            "pnl_percent": request.pnl_percent,
            "user_id": request.user_id
        }

        df = pd.DataFrame([outcome_entry])
        df.to_csv(path, mode="a", index=False, header=not exists)

        return {"message": "✅ Strategy outcome logged"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error logging outcome: {str(e)}")

@router.get("/summary")
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
        if df.empty or "belief" not in df.columns:
            raise HTTPException(status_code=400, detail="No strategy data available")

        if user_id:
            df = df[df["user_id"] == user_id]
            if df.empty:
                return {"message": f"No strategies found for user_id: {user_id}"}

        total = len(df)
        avg_pnl = round(df["pnl_percent"].mean(), 2) if "pnl_percent" in df else None
        win_ratio = round((df["result"] == "win").mean(), 2) if "result" in df else None
        top_beliefs = df["belief"].value_counts().head(5).to_dict()

        return {
            "user_id": user_id,
            "total_strategies": total,
            "avg_pnl_percent": avg_pnl,
            "win_ratio": win_ratio,
            "top_beliefs": top_beliefs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
