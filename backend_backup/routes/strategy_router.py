# backend/routes/strategy_router.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.ai_engine.ai_engine import run_ai_engine  # 🧠 Belief → strategy engine
from backend.feedback_handler import save_feedback_entry  # 💾 Feedback logger

router = APIRouter()

# === Request Schemas ===
class BeliefRequest(BaseModel):
    belief: str
    user_id: Optional[str] = "anonymous"

class FeedbackRequest(BaseModel):
    belief: str
    strategy: Dict[str, Any]
    feedback: str
    user_id: Optional[str] = "anonymous"

# === POST /strategy/process_belief ===
@router.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    Input JSON: {
        "belief": "TSLA will go up this week",
        "user_id": "optional_user_id"
    }
    """
    result = run_ai_engine(request.belief)
    result["user_id"] = request.user_id

    # Optionally save to history or logs here
    save_feedback_entry(request.belief, result, "auto_generated", request.user_id)

    return result

# === POST /strategy/submit_feedback ===
@router.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Input JSON: {
        "belief": "TSLA will go up this week",
        "strategy": { ... },
        "feedback": "good",
        "user_id": "optional_user_id"
    }
    """
    save_feedback_entry(request.belief, request.strategy, request.feedback, request.user_id)
    return {"status": "✅ Feedback saved"}
