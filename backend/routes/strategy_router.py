from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.ai_engine.ai_engine import run_ai_engine  # 🧠 Belief → strategy engine
from backend.feedback_handler import save_feedback_entry  # 💾 Feedback logger
from backend.logger.strategy_logger import log_strategy  # 📝 Strategy history logger
from backend.alpaca_orders import AlpacaExecutor  # 🧾 Unified Alpaca execution

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
    Input JSON:
    {
        "belief": "TSLA will go up this week",
        "user_id": "optional_user_id",
        "place_order": true
    }
    """

    result = run_ai_engine(request.belief)
    result["user_id"] = request.user_id

    # ✅ Save to feedback log
    save_feedback_entry(request.belief, result, "auto_generated", request.user_id)

    # ✅ Save to strategy history log
    log_strategy(request.belief, result["strategy"]["type"], request.user_id)

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
    Input JSON:
    {
        "belief": "TSLA will go up this week",
        "strategy": { ... },
        "feedback": "good",
        "user_id": "optional_user_id"
    }
    """
    save_feedback_entry(request.belief, request.strategy, request.feedback, request.user_id)
    return {"status": "✅ Feedback saved"}
