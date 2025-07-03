# backend/app.py
# ✅ Main FastAPI entrypoint — wires up all routes, AI engine, feedback, and Alpaca execution

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import traceback
import os
import pandas as pd

# === Local Imports ===
from backend.user_models import init_db
from backend.ai_engine.ai_engine import run_ai_engine
from backend.alpaca_orders import AlpacaExecutor
from backend.feedback_handler import save_feedback_entry

# === Routers (modularized routes) ===
from backend.routes.auth_router import router as auth_router
from backend.routes.feedback_router import router as feedback_router
from backend.routes.feedback_predictor import router as feedback_predictor
from backend.routes.portfolio_router import router as portfolio_router
from backend.routes.strategy_router import router as strategy_router
from backend.routes.strategy_logger_router import router as strategy_logger_router
from backend.routes.hot_trades_router import router as hot_trades_router
from backend.routes.alpaca_router import router as alpaca_router
from backend.routes.execution_router import router as execution_router
from backend.routes.pnl_router import router as pnl_router
from backend.routes.market_router import router as market_router
from backend.routes.analytics_router import router as analytics_router
from backend.routes.debug_router import router as debug_router

# === Initialize FastAPI ===
app = FastAPI(title="MarketPlayground AI Backend")

# ✅ CORS — Allow frontend access from localhost ports 3000 and 3001
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Handle CORS preflight (OPTIONS) requests — required for frontend requests
@app.options("/{rest_of_path:path}")
async def preflight_handler():
    return PlainTextResponse("OK", status_code=200)

# === Initialize SQLite DB if needed ===
init_db()

# ✅ Ensure strategy_outcomes.csv exists
strategy_csv_path = os.path.join("backend", "strategy_outcomes.csv")
if not os.path.exists(strategy_csv_path):
    df = pd.DataFrame([{
        "timestamp": datetime.utcnow().isoformat(),
        "belief": "I believe AAPL will go up",
        "strategy": "bull call spread",
        "ticker": "AAPL",
        "pnl_percent": 18.25,
        "result": "win",
        "risk": "moderate",
        "notes": "initial placeholder row"
    }])
    df.to_csv(strategy_csv_path, index=False)
    print("✅ Created starter strategy_outcomes.csv")

# === Register All Modular Routers ===
app.include_router(auth_router,              prefix="/auth",      tags=["Auth"])
app.include_router(feedback_router,          prefix="/feedback",  tags=["Feedback"])
app.include_router(feedback_predictor,       prefix="/predict",   tags=["Predictor"])
app.include_router(portfolio_router,         prefix="/portfolio", tags=["Portfolio"])
app.include_router(strategy_router,          prefix="/strategy",  tags=["Strategy"])
app.include_router(strategy_logger_router,   prefix="/strategy",  tags=["Strategy Logger"])
app.include_router(hot_trades_router,                            tags=["Hot Trades"])
app.include_router(alpaca_router,            prefix="/alpaca",    tags=["Alpaca"])
app.include_router(execution_router,         prefix="/alpaca",    tags=["Execution"])
app.include_router(pnl_router,               prefix="/pnl",       tags=["PnL"])
app.include_router(market_router,            prefix="/market",    tags=["Market"])
app.include_router(analytics_router,         prefix="/analytics", tags=["Analytics"])
app.include_router(debug_router,                                tags=["Debug"])

# === Request Body Schemas ===
class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = "anonymous"
    risk_profile: Optional[str] = "moderate"
    place_order: Optional[bool] = False

class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

# === Root Route for Health Check ===
@app.get("/")
def read_root():
    return {"message": "Welcome to MarketPlayground AI Backend"}

# === Primary Belief Endpoint — Processes via AI Engine ===
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    try:
        result = run_ai_engine(
            belief=request.belief,
            risk_profile=request.risk_profile,
            user_id=request.user_id
        )
        result["user_id"] = request.user_id

        if request.place_order:
            executor = AlpacaExecutor()
            result["execution_result"] = executor.execute_order(result, user_id=request.user_id)

        return result

    except Exception as e:
        print("\n❌ ERROR in /process_belief:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# === Alternate Strategy Route (used by frontend) ===
@app.post("/strategy/process_belief")
async def strategy_process_belief(request: Request):
    try:
        body = await request.json()
        belief = body.get("belief")
        user_id = body.get("user_id", "anonymous")
        risk_profile = body.get("risk_profile", "moderate")

        if not belief:
            raise HTTPException(status_code=400, detail="Belief is required")

        result = run_ai_engine(belief, risk_profile=risk_profile, user_id=user_id)
        return result

    except Exception as e:
        print("\n❌ ERROR in /strategy/process_belief:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# === Feedback Capture ===
@app.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        save_feedback_entry(request.belief, request.strategy, request.feedback)
        return {"message": "✅ Feedback saved"}
    except Exception as e:
        print("\n❌ ERROR in /submit_feedback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to save feedback")

# === Manual Retrain Trigger (backend UI or CLI) ===
@app.post("/force_retrain", response_class=PlainTextResponse)
def force_retrain_now():
    try:
        from backend.train_all_models import train_all_models
        train_all_models()
        return "✅ Forced model retraining completed."
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrain failed: {str(e)}")

# ✅ Auto-Retrain Trigger from News Ingestor
@app.post("/retrain", response_class=PlainTextResponse)
def retrain_from_ingestor():
    try:
        from backend.train_all_models import train_all_models
        train_all_models()
        return "✅ Retraining triggered by news ingestor."
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrain failed: {str(e)}")

# === Uvicorn Entry for Local Dev ===
if __name__ == "__main__":
    import uvicorn
    print("\n🔍 ROUTES LOADED:")
    for route in app.routes:
        print(f"{route.path} -> {route.name}")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
