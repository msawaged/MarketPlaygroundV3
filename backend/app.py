# backend/app.py

from fastapi import FastAPI
from schemas import BeliefRequest  # Import the request body model
from ai_engine.ai_engine import run_ai_engine  # Main strategy generation engine
from feedback_handler import submit_feedback, predict_feedback  # Feedback endpoints

app = FastAPI()

@app.get("/")
def root():
    # Basic health check endpoint
    return {"message": "MarketPlayground API is live."}

@app.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    Takes a user belief (e.g., "TSLA will go up this week")
    and returns the recommended strategy output as JSON.
    """
    result = run_ai_engine(request.belief)
    return result

@app.post("/submit_feedback")
def submit_feedback_endpoint(feedback: dict):
    """
    Accepts feedback from the frontend to log user input on strategies.
    """
    return submit_feedback(feedback)

@app.post("/predict_feedback")
def predict_feedback_endpoint(request: dict):
    """
    Returns predicted label for given feedback-style input.
    """
    return predict_feedback(request)
