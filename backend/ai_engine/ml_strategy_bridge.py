# backend/ai_engine/ml_strategy_bridge.py

import joblib
import os

# ✅ Load trained ML model and vectorizer from disk
MODEL_PATH = "backend/multi_strategy_model.joblib"
VECTORIZER_PATH = "backend/multi_vectorizer.joblib"

try:
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
except Exception as e:
    print(f"[ERROR] Failed to load ML strategy model or vectorizer: {e}")
    model = None
    vectorizer = None

def predict_strategy_with_ml(belief: str, metadata: dict = {}) -> dict:
    """
    Uses the trained ML model to predict a trading strategy based on belief and metadata.
    Returns a dictionary containing the predicted strategy type and source.
    """
    if model is None or vectorizer is None:
        return {"error": "ML model not loaded"}

    try:
        # Combine belief and metadata for prediction input
        full_text = belief
        if metadata:
            meta_parts = [f"{k}: {v}" for k, v in metadata.items()]
            full_text += " | " + " | ".join(meta_parts)

        # Vectorize and predict
        X = vectorizer.transform([full_text])
        prediction = model.predict(X)[0]

        return {
            "type": prediction,
            "source": "ml_model"
        }

    except Exception as e:
        print(f"[ERROR] Failed to predict with ML model: {e}")
        return {"error": "prediction failed"}

        

def run_ml_strategy_model(belief: str, metadata: dict = {}) -> dict:
    """
    Public interface to run the ML strategy model.
    Mirrors the structure expected by the strategy engine.
    """
    return predict_strategy_with_ml(belief, metadata)

# ✅ Add the missing export used in debug_router.py
def generate_strategy_from_ml(belief: str, metadata: dict = {}) -> dict:
    """
    Entry point expected by debug_router — same as run_ml_strategy_model.
    """
    print(f"🧪 [ML DEBUG] Running generate_strategy_from_ml with belief: {belief}")
    return run_ml_strategy_model(belief, metadata)
