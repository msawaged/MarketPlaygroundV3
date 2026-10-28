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
_model = {"loaded": False, "value": None}


def _get_model():
    """Load the legacy model on first use, not at startup."""
    if not _model["loaded"]:
        try:
            _model["value"] = joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"[feedback_predictor] model unavailable: {e}")
        _model["loaded"] = True
    return _model["value"]

# ✅ Create router
router = APIRouter()

@router.post("/predict_feedback")
async def predict_feedback(data: FeedbackPredictionRequest):
    model = _get_model()
    if not model:
        return {"error": "Model not available"}

    # Concatenate belief + strategy for context
    input_text = f"{data.belief} | {data.strategy_description}"
    prediction = model.predict([input_text])[0]

    return {
        "input": input_text,
        "predicted_feedback": prediction
    }
