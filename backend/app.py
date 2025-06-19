# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from ai_engine import run_ai_engine
from feedback_handler import submit_feedback, predict_feedback

app = FastAPI()

# Request model for /process_belief
class BeliefRequest(BaseModel):
    belief: str

# Request model for /submit_feedback
class FeedbackRequest(BaseModel):
    belief: str
    feedback: str

# Request model for /predict_feedback
class FeedbackPredictionRequest(BaseModel):
    belief: str

@app.get("/")
def root():
    return {"message": "MarketPlayground AI Backend is live!"}

@app.post("/process_belief")
def process_belief(data: BeliefRequest):
    """
    Process a user belief and return parsed strategy, asset, etc.
    """
    result = run_ai_engine(data.belief)
    return result

@app.post("/submit_feedback")
def submit_user_feedback(data: FeedbackRequest):
    """
    Store user feedback to improve model accuracy.
    """
    return submit_feedback(data.belief, data.feedback)

@app.post("/predict_feedback")
def predict_feedback_label(data: FeedbackPredictionRequest):
    """
    Predict feedback label for a belief using the feedback model.
    """
    return predict_feedback(data.belief)
