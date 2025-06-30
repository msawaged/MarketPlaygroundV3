# backend/asset_selector.py

print("🔥 asset_selector.py is running...")

"""
Selects the appropriate asset class using a trained ML model.
Falls back to tag-based logic if model files are missing.
"""

import os
import joblib

# Set model paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "asset_class_model.joblib")
VECTORIZER_PATH = os.path.join(BASE_DIR, "asset_vectorizer.joblib")

# Load ML model and vectorizer (once at import)
try:
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    print("✅ Loaded ML asset class model.")
except Exception as e:
    print(f"⚠️ Could not load asset class model or vectorizer: {e}")
    model = None
    vectorizer = None

def select_asset_class(tags: list, ticker: str = "") -> str:
    """
    Predicts the most relevant asset class using ML model or tag-based fallback.

    Args:
        tags (list): Extracted belief tags (e.g. ['bond', 'income'])
        ticker (str): Optional ticker symbol for future override logic

    Returns:
        str: Predicted asset class (e.g. 'stocks', 'options', 'bonds', etc.)
    """
    try:
        input_text = " ".join(tags).lower()
    except Exception as e:
        print(f"[ASSET SELECTOR ERROR] Failed to combine tags: {e}")
        input_text = ""

    # ✅ Attempt ML prediction
    if model and vectorizer:
        try:
            X_vec = vectorizer.transform([input_text])
            prediction = model.predict(X_vec)[0]
            print(f"🧠 [ASSET SELECTOR] ML predicted: {prediction}")
            return prediction
        except Exception as e:
            print(f"[ASSET CLASS ERROR] Failed to predict: {e}")

    # 🛠️ Fallback: Rule-based logic
    try:
        if any(x in input_text for x in ["bond", "treasury", "yield", "interest", "fixed income"]):
            fallback = "bonds"
        elif any(x in input_text for x in ["stock", "equity", "share"]):
            fallback = "stocks"
        elif any(x in input_text for x in ["etf", "fund", "index", "spy", "qqq"]):
            fallback = "etf"
        elif any(x in input_text for x in ["crypto", "bitcoin", "btc", "eth", "ethereum", "solana"]):
            fallback = "crypto"
        else:
            fallback = "options"

        print(f"[ASSET CLASS FALLBACK] Using fallback logic → {fallback}")
        return fallback

    except Exception as e:
        print(f"[ASSET MODEL ERROR] Fallback to default logic failed: {e}")
        return "options"
