# backend/routes/feedback_predictor.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
import joblib
import os

# ✅ Define input schema
class FeedbackPredictionRequest(BaseModel):
    belief: str
    strategy_description: str

# ✅ Load model on router init
MODEL_PATH = os.path.join("backend", "feedback_model.joblib")
try:
    model = joblib.load(MODEL_PATH)
    print(f"[feedback_predictor] ✅ Loaded model from {MODEL_PATH}")
except Exception as e:
    print(f"[feedback_predictor] ❌ Failed to load model: {e}")
    model = None

# ✅ Create router
router = APIRouter()

@router.post("/predict_feedback")
async def predict_feedback(data: FeedbackPredictionRequest):
    if not model:
        return {"error": "Model not available"}

    # Concatenate belief + strategy for context
    input_text = f"{data.belief} | {data.strategy_description}"
    prediction = model.predict([input_text])[0]

    return {
        "input": input_text,
        "predicted_feedback": prediction
    }
