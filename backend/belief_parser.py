# backend/belief_parser.py

"""
This module parses the user's belief into actionable components:
- Extracts ticker (if possible)
- Determines market direction (bullish/bearish/neutral)
- Classifies belief using ML model (tags + confidence)
"""

import re
from backend.utils.ticker_list import ALL_TICKERS
from backend.utils.model_utils import load_model

# Load models
belief_model = load_model("belief_model.joblib")
vectorizer = load_model("belief_vectorizer.joblib")

def clean_belief(text: str) -> str:
    """Clean input by lowering case and removing non-alphanumerics."""
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower().strip())

def detect_ticker(belief: str) -> str:
    """Detect the first matching ticker from a known list."""
    for ticker in ALL_TICKERS:
        if ticker.lower() in belief.lower():
            return ticker.upper()
    return "SPY"  # default if none found

def detect_direction(belief: str) -> str:
    """Simple logic to infer market direction."""
    text = belief.lower()
    if any(word in text for word in ["down", "drop", "fall", "bear", "crash", "tank"]):
        return "bearish"
    elif any(word in text for word in ["up", "rise", "bull", "skyrocket", "jump"]):
        return "bullish"
    return "neutral"

def parse_belief(belief: str) -> dict:
    """
    Parses the user belief into components for downstream use.

    Args:
        belief (str): Natural-language belief, e.g. "TSLA will go up"

    Returns:
        dict: {
            "ticker": "TSLA",
            "direction": "bullish",
            "tags": ["momentum", "growth"],
            "confidence": 0.75
        }
    """
    cleaned = clean_belief(belief)
    vectorized = vectorizer.transform([cleaned])
    predicted = belief_model.predict(vectorized)[0]
    confidence = max(belief_model.predict_proba(vectorized)[0])

    return {
        "ticker": detect_ticker(belief),
        "direction": detect_direction(belief),
        "tags": [predicted],
        "confidence": float(confidence)
    }
