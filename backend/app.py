# backend/app.py
# ✅ Final version: combines route-based logic and direct endpoints like /process_belief

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from backend.routes import router  # includes strategy, feedback predictor, auth
from backend.user_models import init_db
from backend.ai_engine.ai_engine import run_ai_engine
import json
import os
from datetime import datetime

# === Initialize FastAPI app ===
app = FastAPI(title="MarketPlayground AI Backend")

# === Create user DB tables ===
init_db()

# === Include route-based APIs ===
app.include_router(router)

# === Define request schemas ===
class BeliefRequest(BaseModel):
    belief: str

class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

# === POST /process_belief ===
# Input: belief string → Output: AI-generated strategy
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    try:
        result = run_ai_engine(request.belief)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === POST /submit_feedback ===
# Appends structured feedback to feedback_data.json
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
