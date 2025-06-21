# backend/app.py

from fastapi import FastAPI
from pydantic import BaseModel
from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_handler import log_feedback
from backend.feedback_trainer import train_from_feedback
from backend.utils.model_utils import load_model
import subprocess

app = FastAPI(title="MarketPlayground AI API 🚀")


# ==== REQUEST SCHEMAS ====

class BeliefRequest(BaseModel):
    belief: str


class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str  # e.g., "positive" or "negative"


# ==== MAIN ENDPOINT ====

@app.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    🔍 Interpret a belief and return a strategy.
    """
    result = run_ai_engine(request.belief)
    return result


# ==== FEEDBACK ENDPOINT ====

@app.post("/feedback")
def feedback_endpoint(request: FeedbackRequest):
    """
    💬 Log user feedback for model learning.
    """
    log_feedback(request.belief, request.strategy, request.feedback)
    return {"message": "✅ Feedback recorded successfully."}


# ==== TRAINING ENDPOINT ====

@app.post("/train_from_feedback")
def train_endpoint():
    """
    🧠 Retrain model from collected feedback.
    """
    train_from_feedback()
    return {"message": "🔁 Model retrained from feedback."}


# ==== TEMPORARY BELIEF MODEL RETRAIN ENDPOINT ====

@app.post("/retrain-belief-model")
def retrain_belief_model():
    """
    🔧 TEMP: Manually retrain the belief model (runs train_belief_model.py).
    """
    try:
        result = subprocess.run(
            ["python", "train_belief_model.py"],
            check=True,
            capture_output=True,
            text=True
        )
        return {
            "message": "✅ Belief model retrained.",
            "output": result.stdout
        }
    except subprocess.CalledProcessError as e:
        return {
            "error": "❌ Training failed.",
            "details": e.stderr
        }
