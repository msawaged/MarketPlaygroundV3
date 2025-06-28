# backend/belief_parser.py

"""
This module parses the user's belief into structured components:
- Extracts ticker from known list
- Infers market direction from keywords
- Classifies tags via ML (with confidence score)
- Predicts asset class via ML (fallbacks gracefully)
"""

import re
from backend.utils.ticker_list import ALL_TICKERS
from backend.utils.model_utils import load_model

# === Load ML Models ===
try:
    belief_model = load_model("belief_model.joblib")
    vectorizer = load_model("belief_vectorizer.joblib")
except Exception as e:
    print(f"[ERROR] Could not load belief/tag model: {e}")
    belief_model, vectorizer = None, None

try:
    asset_model = load_model("multi_asset_model.joblib")
    asset_vectorizer = load_model("multi_vectorizer.joblib")
except Exception as e:
    print(f"[WARNING] Asset class model not loaded: {e}")
    asset_model, asset_vectorizer = None, None

# === Clean and Normalize Belief Text ===
def clean_belief(text: str) -> str:
    """
    Lowercase and strip punctuation from input.
    Example: "TSLA will explode!" → "tsla will explode"
    """
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower().strip())

# === Ticker Detection ===
def detect_ticker(belief: str) -> str:
    """
    Scans belief for any known tickers from master list.
    Returns uppercase ticker or defaults to 'SPY'
    """
    for ticker in ALL_TICKERS:
        if ticker.lower() in belief.lower():
            return ticker.upper()
    return "SPY"

# === Market Sentiment Detection ===
def detect_direction(belief: str) -> str:
    """
    Heuristically classify belief as bullish, bearish, or neutral.
    """
    text = belief.lower()
    if any(w in text for w in ["down", "drop", "fall", "bear", "crash", "tank", "recession"]):
        return "bearish"
    elif any(w in text for w in ["up", "rise", "bull", "skyrocket", "jump", "explode", "rally"]):
        return "bullish"
    return "neutral"

# === Asset Class Prediction ===
def detect_asset_class(raw_belief: str) -> str:
    """
    Use ML model to classify asset class (e.g., stock, options, bond).
    Fallback to 'options' on failure.
    """
    if asset_model and asset_vectorizer:
        try:
            vec = asset_vectorizer.transform([raw_belief])
            prediction = asset_model.predict(vec)[0]
            print(f"[ASSET CLASS DETECTED] → {prediction}")
            return prediction
        except Exception as e:
            print(f"[ASSET CLASS ERROR] Failed to predict: {e}")
    print("[ASSET CLASS FALLBACK] Defaulting to 'options'")
    return "options"

# === Main Parser Function ===
def parse_belief(belief: str) -> dict:
    """
    Full belief parser that extracts:
    - ticker
    - direction
    - tags (via ML)
    - confidence (via ML)
    - asset_class (via ML or fallback)
    """
    cleaned = clean_belief(belief)
    tag_list = []
    confidence = 0.0

    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            prediction = belief_model.predict(vec)[0]
            confidence = max(belief_model.predict_proba(vec)[0])

            # Split tag predictions into list
            raw_tags = re.split(r"[\n,]+", prediction)
            tag_list = [tag.strip() for tag in raw_tags if tag.strip()]

            # Filter out overly long or malformed tags
            tag_list = [tag for tag in tag_list if len(tag) <= 30 and len(tag.split()) <= 4]
        except Exception as e:
            print(f"[TAG MODEL ERROR] Failed to classify belief: {e}")

    return {
        "ticker": detect_ticker(belief),
        "direction": detect_direction(belief),
        "tags": tag_list,
        "confidence": float(confidence),
        "asset_class": detect_asset_class(belief)
    }

# === Standalone Confidence Function ===
def detect_confidence(belief: str) -> float:
    """
    Returns ML-predicted confidence score (0 to 1) from belief model.
    Falls back to 0.5 if model unavailable.
    """
    cleaned = clean_belief(belief)
    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            return float(max(belief_model.predict_proba(vec)[0]))
        except Exception as e:
            print(f"[CONFIDENCE ERROR] {e}")
    return 0.5  # fallback
