# backend/app.py
# ✅ Master entry point for FastAPI app — includes routers and direct endpoints

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from backend.routes import router  # 🔗 Main router: includes all submodules
from backend.user_models import init_db  # 🛠️ User model setup
from backend.ai_engine.ai_engine import run_ai_engine  # 🧠 Core AI strategy engine
import os
import json
from datetime import datetime

# === Initialize FastAPI app ===
app = FastAPI(title="MarketPlayground AI Backend")

# === One-time database initialization for user tables ===
init_db()

# === Mount all modular route groups (strategy, feedback, auth, portfolio) ===
app.include_router(router)

# === Request body schemas for endpoints ===
class BeliefRequest(BaseModel):
    belief: str

class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

# === POST /process_belief ===
# → Input: user belief
# → Output: parsed belief, strategy, price data, goal, etc.
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    try:
        result = run_ai_engine(request.belief)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === POST /submit_feedback ===
# → Logs user feedback into feedback_data.json
@app.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "belief": request.belief,
            "strategy": request.strategy,
            "result": request.feedback
        }

        # ✅ Save path (same directory as app.py)
        feedback_file = os.path.join(os.path.dirname(__file__), "feedback_data.json")

        # 📥 Load existing feedback
        if os.path.exists(feedback_file):
            with open(feedback_file, "r") as f:
                feedback_list = json.load(f)
        else:
            feedback_list = []

        # 📤 Append and save updated list
        feedback_list.append(feedback_entry)
        with open(feedback_file, "w") as f:
            json.dump(feedback_list, f, indent=2)

        return {"message": "✅ Feedback saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
