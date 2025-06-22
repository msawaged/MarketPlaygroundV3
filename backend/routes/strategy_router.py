# backend/routes/strategy_router.py

from fastapi import APIRouter, Request
from backend.ai_engine.ai_engine import run_ai_engine  # Runs the belief → strategy pipeline
from backend.feedback_handler import save_feedback_entry  # Saves feedback to local JSON file

router = APIRouter()

@router.post("/process_belief")
async def process_belief(request: Request):
    """
    POST endpoint to process a natural-language belief and return a strategy.
    Input JSON: {
        "belief": "TSLA will go up this week",
        "user_id": "optional_user_id"
    }
    """
    data = await request.json()
    belief = data.get("belief", "")
    user_id = data.get("user_id", "anonymous")

    result = run_ai_engine(belief)
    result["user_id"] = user_id  # attach to response

    # Log the strategy with user_id
    save_feedback_entry(belief, result, "auto_generated", user_id)

    return result


@router.post("/submit_feedback")
async def submit_feedback(request: Request):
    """
    POST endpoint to accept feedback for a generated strategy.
    Input JSON: {
        "belief": "TSLA will go up this week",
        "strategy": { ... },  # same structure as returned from /process_belief
        "feedback": "good",
        "user_id": "optional_user_id"
    }
    """
    data = await request.json()
    belief = data.get("belief", "")
    strategy = data.get("strategy", {})
    feedback = data.get("feedback", "")
    user_id = data.get("user_id", "anonymous")

    # Save feedback with user_id
    save_feedback_entry(belief, strategy, feedback, user_id)
    return {"status": "✅ Feedback saved"}
