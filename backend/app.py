# backend/app.py
# ✅ Main entry point for the FastAPI app — handles routers, AI engine, and feedback

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import os
import json
from datetime import datetime

from backend.user_models import init_db  # 🛠️ Initializes user table structure
from backend.ai_engine.ai_engine import run_ai_engine  # 🧠 Core AI strategy engine

# 🔗 Import routers directly (no circular imports)
from backend.routes.auth_router import router as auth_router
from backend.routes.feedback_router import router as feedback_router
from backend.routes.feedback_predictor import router as feedback_predictor
from backend.routes.portfolio_router import router as portfolio_router
from backend.routes.strategy_router import router as strategy_router
from backend.routes.strategy_logger_router import router as strategy_logger_router

# === Initialize FastAPI app ===
app = FastAPI(title="MarketPlayground AI Backend")

# === Run DB setup for user authentication tables ===
init_db()

# === Register routers (modular + clear prefixes) ===
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(feedback_router, prefix="/feedback", tags=["Feedback"])
app.include_router(feedback_predictor, prefix="/predict", tags=["Predictor"])
app.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])  # ✅ Handles /portfolio/save_trade etc
app.include_router(strategy_router, prefix="/strategy", tags=["Strategy"])
app.include_router(strategy_logger_router, prefix="/strategy-log", tags=["Strategy Logger"])

# === Request body schemas for AI and feedback endpoints ===
class BeliefRequest(BaseModel):
    belief: str

class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

# === POST /process_belief ===
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    try:
        result = run_ai_engine(request.belief)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === POST /submit_feedback ===
@app.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "belief": request.belief,
            "strategy": request.strategy,
            "result": request.feedback
        }

        feedback_file = os.path.join(os.path.dirname(__file__), "feedback_data.json")

        if os.path.exists(feedback_file):
            with open(feedback_file, "r") as f:
                feedback_list = json.load(f)
        else:
            feedback_list = []

        feedback_list.append(feedback_entry)
        with open(feedback_file, "w") as f:
            json.dump(feedback_list, f, indent=2)

        return {"message": "✅ Feedback saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Optional: Show registered routes if run directly ===
if __name__ == "__main__":
    import uvicorn
    print("\n🔍 ROUTES LOADED:")
    for route in app.routes:
        print(f"{route.path} -> {route.name}")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
