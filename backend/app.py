# backend/app.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from backend.ai_engine.ai_engine import run_ai_engine
from backend.feedback_handler import save_feedback, predict_feedback

app = FastAPI()


# ✅ Request body models
class BeliefInput(BaseModel):
    belief: str

class FeedbackInput(BaseModel):
    belief: str
    category: str
    feedback: str

class PredictFeedbackInput(BaseModel):
    belief: str
    strategy: str


@app.get("/")
def read_root():
    return {"message": "MarketPlayground AI backend is live."}


# ✅ Properly defined POST route with input model
@app.post("/process_belief")
def process_belief(input_data: BeliefInput):
    return run_ai_engine(input_data.belief)


@app.post("/submit_feedback")
def submit_feedback(feedback: FeedbackInput):
    return save_feedback(feedback.dict())


@app.post("/predict_feedback")
def predict_feedback_endpoint(data: PredictFeedbackInput):
    return predict_feedback(data.dict())
