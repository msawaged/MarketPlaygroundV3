# backend/app.py

from fastapi import FastAPI
from backend.schemas import BeliefRequest  # ✅ FIXED for Render context
from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_handler import submit_feedback, predict_feedback

app = FastAPI()

@app.get("/")
def root():
    return {"message": "MarketPlayground API is live."}

@app.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    Accepts a natural language belief and returns an AI-generated strategy.

    Input Example:
    {
        "belief": "TSLA will go up this week"
    }
    """
    return run_ai_engine(request.belief)

@app.post("/submit_feedback")
def submit_feedback_endpoint(feedback: dict):
    """
    Submits user feedback on a strategy to the learning engine.
    """
    return submit_feedback(feedback)

@app.post("/predict_feedback")
def predict_feedback_endpoint(request: dict):
    """
    Predicts the category of user feedback.
    """
    return predict_feedback(request)
