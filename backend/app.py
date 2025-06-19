from fastapi import FastAPI
from pydantic import BaseModel
from ai_engine.ai_engine import run_ai_engine
from feedback_handler import submit_feedback, predict_feedback

app = FastAPI()

# ✅ Define the request model for processing a belief
class BeliefRequest(BaseModel):
    belief: str

# ✅ Define the request model for feedback submission
class FeedbackRequest(BaseModel):
    belief: str
    feedback: str

# ✅ Define the request model for feedback prediction
class FeedbackPredictionRequest(BaseModel):
    belief: str

# ✅ Root endpoint
@app.get("/")
def read_root():
    return {"message": "MarketPlayground AI Backend is live!"}

# ✅ Process belief and return strategy
@app.post("/process_belief")
def process_belief(data: BeliefRequest):
    result = run_ai_engine(data.belief)
    return result

# ✅ Submit feedback from the user
@app.post("/submit_feedback")
def submit_user_feedback(data: FeedbackRequest):
    return submit_feedback(data.belief, data.feedback)

# ✅ Predict feedback based on belief
@app.post("/predict_feedback")
def predict_user_feedback(data: FeedbackPredictionRequest):
    return predict_feedback(data.belief)
