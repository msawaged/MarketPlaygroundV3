# backend/app.py
# ✅ Main entry point for the FastAPI app — handles routers, AI engine, feedback, and brokerage features

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import pandas as pd
from datetime import datetime
import traceback

# === Initialization ===
from backend.user_models import init_db
from backend.ai_engine.ai_engine import run_ai_engine

# === Modular Routers ===
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
from backend.routes.debug_router import router as debug_router  # ✅ NEW

# === Initialize FastAPI app ===
app = FastAPI(title="MarketPlayground AI Backend")

# ✅ Allow frontend (localhost:3000) to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Run DB setup ===
init_db()

# ✅ Auto-create strategy_outcomes.csv if missing
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

# === Register Routes ===
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(feedback_router, prefix="/feedback", tags=["Feedback"])
app.include_router(feedback_predictor, prefix="/predict", tags=["Predictor"])
app.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(strategy_router, prefix="/strategy", tags=["Strategy"])
app.include_router(strategy_logger_router, prefix="/strategy", tags=["Strategy Logger"])  
app.include_router(hot_trades_router, tags=["Hot Trades"])
app.include_router(alpaca_router, prefix="/alpaca", tags=["Alpaca"])
app.include_router(execution_router, prefix="/alpaca", tags=["Execution"])
app.include_router(pnl_router, prefix="/pnl", tags=["PnL"])
app.include_router(market_router, prefix="/market", tags=["Market"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
app.include_router(debug_router, tags=["Debug"])  # ✅ NEW

# === Schemas ===
class BeliefRequest(BaseModel):
    belief: str
    risk_profile: Optional[str] = "moderate"

class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

# === AI Endpoint (standard, backward compatible) ===
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    try:
        result = run_ai_engine(request.belief, risk_profile=request.risk_profile)
        return result
    except Exception as e:
        print("\n❌ ERROR in /process_belief:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# === NEW: Strategy Endpoint with Full Trace Logging ===
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

# ✅ NEW: Force retraining regardless of feedback count
@app.post("/force_retrain", response_class=PlainTextResponse)
def force_retrain_now():
    try:
        from backend.train_all_models import train_all_models
        train_all_models()
        return "✅ Forced model retraining completed."
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrain failed: {str(e)}")

# === Welcome Route ===
@app.get("/")
def read_root():
    return {"message": "Welcome to MarketPlayground AI Backend"}

# === Local Debug (optional) ===
if __name__ == "__main__":
    import uvicorn
    print("\n🔍 ROUTES LOADED:")
    for route in app.routes:
        print(f"{route.path} -> {route.name}")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
