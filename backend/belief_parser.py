# backend/belief_parser.py

"""
This module parses the user's belief into actionable components:
- Extracts ticker (if possible)
- Determines market direction (bullish/bearish/neutral)
- Classifies belief using ML model (tags + confidence)
- Predicts asset class using ML (fallbacks to 'options' if error)
"""

import re
from backend.utils.ticker_list import ALL_TICKERS
from backend.utils.model_utils import load_model

# === Load Required Models for Tagging ===
try:
    belief_model = load_model("belief_model.joblib")
    vectorizer = load_model("belief_vectorizer.joblib")
except Exception as e:
    print(f"[ERROR] Could not load belief/tag model: {e}")
    belief_model = None
    vectorizer = None

# === Optionally Load Asset Class Model ===
try:
    asset_model = load_model("multi_asset_model.joblib")
    asset_vectorizer = load_model("multi_vectorizer.joblib")
except Exception as e:
    print(f"[WARNING] Asset class model not loaded: {e}")
    asset_model = None
    asset_vectorizer = None

# === Helper: Normalize user input ===
def clean_belief(text: str) -> str:
    """
    Normalize the input belief text by removing punctuation and lowering case.
    Example: "TSLA will explode!" → "tsla will explode"
    """
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower().strip())

# === Helper: Detect ticker ===
def detect_ticker(belief: str) -> str:
    """
    Detect a known stock/ETF ticker mentioned in the belief.
    Defaults to SPY if none found.
    """
    for ticker in ALL_TICKERS:
        if ticker.lower() in belief.lower():
            return ticker.upper()
    return "SPY"  # fallback

# === Helper: Infer direction from belief keywords ===
def detect_direction(belief: str) -> str:
    """
    Infer sentiment direction from keywords in the belief text.
    Returns: 'bullish', 'bearish', or 'neutral'
    """
    text = belief.lower()
    if any(word in text for word in ["down", "drop", "fall", "bear", "crash", "tank", "recession"]):
        return "bearish"
    elif any(word in text for word in ["up", "rise", "bull", "skyrocket", "jump", "explode", "rally"]):
        return "bullish"
    return "neutral"

# === Helper: Predict asset class (ML or fallback) ===
def detect_asset_class(raw_belief: str) -> str:
    """
    Predict the asset class using the trained ML model on the raw (uncleaned) belief.
    Falls back to 'options' if the model is missing or errors.
    """
    if asset_model and asset_vectorizer:
        try:
            vec = asset_vectorizer.transform([raw_belief])
            prediction = asset_model.predict(vec)[0]
            print(f"[ASSET CLASS DETECTED] → {prediction}")
            return prediction
        except Exception as e:
            print(f"[ASSET CLASS ERROR] Failed to predict asset class: {e}")
    print("[ASSET CLASS FALLBACK] Defaulting asset class to 'options'")
    return "options"

# === Main Belief Parsing Function ===
def parse_belief(belief: str) -> dict:
    """
    Converts a user belief string into structured components:
    - Ticker
    - Direction
    - Tags (ML classified and cleaned)
    - Confidence (ML probability)
    - Asset Class (ML or fallback)

    Returns:
        dict: parsed belief components
    """
    cleaned = clean_belief(belief)

    # Default empty tag list and confidence
    tag_list = []
    confidence = 0.0

    # === Predict tag using ML model if loaded
    if belief_model and vectorizer:
        try:
            vectorized = vectorizer.transform([cleaned])
            predicted_tag = belief_model.predict(vectorized)[0]
            confidence = max(belief_model.predict_proba(vectorized)[0])

            # ✅ Split tags on commas/newlines
            raw_tags = re.split(r"[\n,]+", predicted_tag)
            tag_list = [tag.strip() for tag in raw_tags if tag.strip()]

            # ✅ Remove garbage tags: long phrases, belief contamination, etc.
            tag_list = [
                tag for tag in tag_list
                if len(tag) <= 30 and len(tag.split()) <= 4
            ]

        except Exception as e:
            print(f"[TAG MODEL ERROR] Failed to classify belief: {e}")

    return {
        "ticker": detect_ticker(belief),
        "direction": detect_direction(belief),
        "tags": tag_list,
        "confidence": float(confidence),
        "asset_class": detect_asset_class(belief)
    }
