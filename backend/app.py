# backend/app.py

"""
Main FastAPI entrypoint — modular routes, CORS, AI engine, Alpaca, analytics, and ingestion toggles.
"""

import os
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from collections import Counter

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

# === Local imports ===
from backend.user_models import init_db
from backend.ai_engine.ai_engine import run_ai_engine
from backend.alpaca_orders import AlpacaExecutor
from backend.feedback_handler import save_feedback_entry

# === Modular route imports ===
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

app = FastAPI(title="MarketPlayground AI Backend")

# === CORS for frontend integration ===
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

@app.options("/{rest_of_path:path}")
async def preflight_handler():
    return PlainTextResponse("OK", status_code=200)

init_db()

# === Seed strategy_outcomes.csv if missing ===
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

# === Register routers ===
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

# === Request schemas ===
class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = "anonymous"
    risk_profile: Optional[str] = "moderate"
    place_order: Optional[bool] = False

class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

@app.get("/")
def read_root():
    return {"message": "Welcome to MarketPlayground AI Backend"}

@app.get("/test_env")
def test_env():
    openai_key = os.getenv("OPENAI_API_KEY")
    return {"OPENAI_API_KEY": "Set" if openai_key else "Not Set"}

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

@app.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        save_feedback_entry(request.belief, request.strategy, request.feedback)
        return {"message": "✅ Feedback saved"}
    except Exception as e:
        print("\n❌ ERROR in /submit_feedback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to save feedback")

@app.post("/force_retrain", response_class=PlainTextResponse)
def force_retrain_now():
    try:
        from backend.train_all_models import train_all_models
        train_all_models()
        return "✅ Forced model retraining completed."
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrain failed: {str(e)}")

@app.post("/retrain", response_class=PlainTextResponse)
def retrain_from_ingestor():
    try:
        from backend.train_all_models import train_all_models
        train_all_models()
        return "✅ Retraining triggered by news ingestor."
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrain failed: {str(e)}")

# === ✅ Strategy Distribution Endpoint ===
@app.get("/analytics/strategy_distribution")
def strategy_distribution(
    asset_class: Optional[str] = Query(None),
    belief_contains: Optional[str] = Query(None)
):
    try:
        df = pd.read_csv(strategy_csv_path)
        if asset_class:
            df = df[df["strategy"].str.contains(asset_class, case=False, na=False)]
        if belief_contains:
            df = df[df["belief"].str.contains(belief_contains, case=False, na=False)]
        strategy_counts = Counter(df["strategy"])
        return dict(strategy_counts)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading strategy data: {e}")

# === ✅ Trending Strategies Leaderboard ===
@app.get("/analytics/trending_strategies")
def trending_strategies(limit: int = 5):
    try:
        df = pd.read_csv(strategy_csv_path)
        trending = df["strategy"].value_counts().head(limit).to_dict()
        return {"top_strategies": trending}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load trending strategies")

# === ✅ Top Tags / Topics Summary ===
@app.get("/analytics/top_tags")
def top_tags(limit: int = 10):
    try:
        if not os.path.exists(strategy_csv_path):
            return {"message": "strategy_outcomes.csv not found"}
        df = pd.read_csv(strategy_csv_path)
        if "tags" not in df.columns:
            return {"message": "tags column not found in CSV"}
        tags_series = df["tags"].dropna().str.split(",")
        all_tags = [tag.strip() for tags in tags_series for tag in tags]
        top = Counter(all_tags).most_common(limit)
        return {"top_tags": dict(top)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to compute top tags")

# === ✅ Ingestion Pause Toggle (read from ENV) ===
@app.get("/toggle/news_ingestion_status")
def news_ingestion_status():
    paused = os.getenv("PAUSE_NEWS_INGESTION", "false").lower() == "true"
    return {"paused": paused}

if __name__ == "__main__":
    import uvicorn
    print("\n🔍 ROUTES LOADED:")
    for route in app.routes:
        print(f"{route.path} -> {route.name}")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
