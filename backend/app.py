from fastapi import FastAPI
from pydantic import BaseModel
from ai_engine.ai_engine import process_belief
from feedback_handler import submit_feedback, predict_feedback

# Initialize the FastAPI application
app = FastAPI()

# === Request Models ===

class BeliefRequest(BaseModel):
    belief: str

class FeedbackRequest(BaseModel):
    belief: str
    feedback: str  # e.g., "good", "bad", "wrong", "accurate"

class FeedbackPredictionRequest(BaseModel):
    belief: str

# === Routes ===

@app.get("/")
def root():
    return {"message": "MarketPlayground AI Backend is running ✅"}

@app.post("/process_belief")
def process_belief_endpoint(request: BeliefRequest):
    """
    Process a market belief and return a strategy.
    Input: {"belief": "TSLA will go up this week"}
    Output: Cleaned belief, detected asset class, strategy suggestion, etc.
    """
    return process_belief(request.belief)

@app.post("/submit_feedback")
def submit_feedback_endpoint(request: FeedbackRequest):
    """
    Save user feedback to the feedback.csv file.
    Input: {"belief": "...", "feedback": "..."}
    """
    return submit_feedback(request.belief, request.feedback)

@app.post("/predict_feedback")
def predict_feedback_endpoint(request: FeedbackPredictionRequest):
    """
    Predict whether a given belief is likely to receive positive or negative feedback.
    Input: {"belief": "..."}
    """
    return predict_feedback(request.belief)
