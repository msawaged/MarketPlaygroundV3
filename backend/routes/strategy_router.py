# backend/routes/strategy_router.py

from fastapi import APIRouter, Request
from backend.ai_engine.ai_engine import run_ai_engine  # Runs the belief → strategy pipeline
from backend.feedback_handler import save_feedback_entry  # Saves feedback to local JSON file

router = APIRouter()

@router.post("/process_belief")
async def process_belief(request: Request):
    """
    POST endpoint to process a natural-language belief and return a strategy.
    Input JSON: {"belief": "TSLA will go up this week"}
    Output JSON includes cleaned belief, parsed asset info, and selected strategy.
    """
    data = await request.json()
    belief = data.get("belief", "")
    result = run_ai_engine(belief)
    return result

@router.post("/submit_feedback")
async def submit_feedback(request: Request):
    """
    POST endpoint to accept feedback for a generated strategy.
    Input JSON:
    {
        "belief": "TSLA will go up this week",
        "strategy": { ... },  # same structure as returned from /process_belief
        "feedback": "good"  # or "bad", or custom string
    }
    Saves feedback to backend/feedback_data.json for future model retraining.
    """
    data = await request.json()
    belief = data.get("belief", "")
    strategy = data.get("strategy", {})
    feedback = data.get("feedback", "")

    save_feedback_entry(belief, strategy, feedback)
    return {"status": "saved"}
