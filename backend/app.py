# backend/app.py
# ✅ Main entry point for the FastAPI app — handles routers, AI engine, feedback, and brokerage features

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import os

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
from backend.routes.alpaca_router import router as alpaca_router
from backend.routes.execution_router import router as execution_router
from backend.routes.pnl_router import router as pnl_router
from backend.routes.market_router import router as market_router

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

# === Register Routes ===
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(feedback_router, prefix="/feedback", tags=["Feedback"])
app.include_router(feedback_predictor, prefix="/predict", tags=["Predictor"])
app.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(strategy_router, prefix="/strategy", tags=["Strategy"])
app.include_router(strategy_logger_router, prefix="/strategy-log", tags=["Strategy Logger"])
app.include_router(alpaca_router, prefix="/alpaca", tags=["Alpaca"])
app.include_router(execution_router, prefix="/alpaca", tags=["Execution"])
app.include_router(pnl_router, prefix="/pnl", tags=["PnL"])
app.include_router(market_router, prefix="/market", tags=["Market"])

# === Schemas ===
class BeliefRequest(BaseModel):
    belief: str

class FeedbackRequest(BaseModel):  # ✅ Still useful for schema consistency
    belief: str
    strategy: str
    feedback: str  # "good" or "bad"

# === AI Endpoint ===
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    """
    Accepts a user belief and returns an AI-generated strategy.
    """
    try:
        result = run_ai_engine(request.belief)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Local Debug (optional)
if __name__ == "__main__":
    import uvicorn
    print("\n🔍 ROUTES LOADED:")
    for route in app.routes:
        print(f"{route.path} -> {route.name}")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
