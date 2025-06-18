# backend/belief_parser.py

"""
This module parses user beliefs into:
1. Cleaned belief text.
2. Detected asset class & directional sentiment (e.g., bullish/bearish).
3. Vectorized representation for model prediction (via TF-IDF).
"""

import os
import re
import joblib

# ✅ Load the vectorizer from the same directory (safe for local + Render)
belief_vectorizer = joblib.load(
    os.path.join(os.path.dirname(__file__), "belief_vectorizer.joblib")
)

def clean_belief(text: str) -> str:
    """
    Cleans user belief text by lowercasing, removing special characters, etc.

    Args:
        text (str): Raw belief input like "TSLA will tank Monday"

    Returns:
        str: Cleaned and normalized belief string
    """
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text.strip()


def detect_asset_and_direction(text: str) -> dict:
    """
    Very simple hardcoded logic to classify direction and asset class.
    (To be replaced later with ML classifier)

    Args:
        text (str): Cleaned belief string

    Returns:
        dict: {
            "direction": "bullish" | "bearish" | "neutral",
            "asset_class": "stocks" | "etfs" | "bonds" | "crypto" | "currencies"
        }
    """
    text = text.lower()

    direction = "neutral"
    if any(word in text for word in ["rise", "up", "bull", "moon", "go higher"]):
        direction = "bullish"
    elif any(word in text for word in ["drop", "down", "tank", "bear", "crash"]):
        direction = "bearish"

    asset_class = "stocks"
    if any(word in text for word in ["etf", "index", "spy", "qqq"]):
        asset_class = "etfs"
    elif any(word in text for word in ["bond", "treasury", "yield"]):
        asset_class = "bonds"
    elif any(word in text for word in ["bitcoin", "crypto", "eth", "ethereum"]):
        asset_class = "crypto"
    elif any(word in text for word in ["currency", "usd", "euro", "yen", "forex"]):
        asset_class = "currencies"

    return {
        "direction": direction,
        "asset_class": asset_class,
    }


def vectorize_belief(text: str):
    """
    Converts belief string into numerical vector using pre-trained TF-IDF vectorizer.

    Args:
        text (str): Cleaned belief string

    Returns:
        sparse matrix: Vectorized belief input
    """
    return belief_vectorizer.transform([text])
