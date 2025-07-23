# backend/ai_engine/ml_strategy_bridge.py

import joblib
import os

# ✅ Load trained ML model and vectorizer
MODEL_PATH = "backend/multi_strategy_model.joblib"
VECTORIZER_PATH = "backend/multi_vectorizer.joblib"

try:
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
except Exception as e:
    print(f"[ERROR] Failed to load ML strategy model: {e}")
    model = None
    vectorizer = None

def predict_strategy_with_ml(belief: str, metadata: dict = {}) -> dict:
    """
    Uses the trained ML model to predict a trading strategy.
    """
    if model is None or vectorizer is None:
        return {"error": "ML model not loaded"}

    try:
        # Combine belief and metadata for input
        full_text = belief
        if metadata:
            meta_parts = [f"{k}: {v}" for k, v in metadata.items()]
            full_text += " | " + " | ".join(meta_parts)

        # Vectorize input
        X = vectorizer.transform([full_text])
        prediction = model.predict(X)[0]

        # Return in expected structure
        return {
            "type": prediction,
            "source": "ml_model"
        }

    except Exception as e:
        print(f"[ERROR] Failed to predict with ML model: {e}")
        return {"error": "prediction failed"}
