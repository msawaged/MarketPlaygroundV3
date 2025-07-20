# backend/ai_engine/ml_strategy_bridge.py

"""
🔗 ML Strategy Bridge
This module handles routing beliefs and metadata into trained ML models
for predicting optimal trading strategies. This is part of the new GPT-to-ML
upgrade that modularizes strategy generation into GPT, ML, or hybrid modes.
"""

import os
import joblib

# ✅ Load ML models (you can swap or update these paths as needed)
ML_MODEL_PATH = os.path.join("backend", "multi_strategy_model.joblib")
VEC_PATH = os.path.join("backend", "multi_vectorizer.joblib")

try:
    ml_model = joblib.load(ML_MODEL_PATH)
    ml_vectorizer = joblib.load(VEC_PATH)
    print("✅ ML strategy model and vectorizer loaded successfully.")
except Exception as e:
    print(f"❌ Failed to load ML components: {e}")
    ml_model = None
    ml_vectorizer = None


def generate_strategy_from_ml(belief: str, metadata: dict = {}) -> dict:
    """
    🧠 Run the belief + metadata through the trained ML model.

    Args:
        belief (str): User belief or market hypothesis
        metadata (dict): Optional — can include parsed info like asset class, risk, etc.

    Returns:
        dict: A strategy dictionary with type, explanation, and tags
    """
    if not ml_model or not ml_vectorizer:
        return {"error": "ML model not loaded"}

    # ✅ Combine belief and metadata into a single text input
    meta_string = " ".join([f"{k}:{v}" for k, v in metadata.items()])
    input_text = f"{belief} {meta_string}".strip()

    try:
        # ✅ Vectorize and predict
        vectorized = ml_vectorizer.transform([input_text])
        prediction = ml_model.predict(vectorized)[0]

        # Optional: Add probability or confidence score
        if hasattr(ml_model, "predict_proba"):
            probas = ml_model.predict_proba(vectorized)[0]
            confidence = round(max(probas), 3)
        else:
            confidence = 0.5  # fallback

        return {
            "type": prediction,
            "confidence": confidence,
            "source": "ml_model",
            "tags": ["auto-ml", "trained"],
            "explanation": f"This strategy was selected using a trained ML model based on your belief: '{belief}'"
        }

    except Exception as e:
        return {"error": f"ML strategy generation failed: {e}"}
