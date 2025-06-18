import re
import os
import joblib

# ✅ Load the vectorizer using a path relative to this file's directory
# This ensures compatibility with both local and cloud environments (e.g., Render)
belief_vectorizer = joblib.load(os.path.join(os.path.dirname(__file__), "belief_vectorizer.joblib"))

# ✅ Clean up the user's belief string (remove special characters, lowercase, etc.)
def clean_belief(belief: str) -> str:
    belief = belief.lower()
    belief = re.sub(r'[^a-zA-Z0-9\s]', '', belief)  # Remove punctuation/symbols
    belief = re.sub(r'\s+', ' ', belief).strip()    # Normalize whitespace
    return belief

# ✅ Dummy asset/direction detection for now (upgradeable)
# Extracts rough direction from user's text belief
def detect_asset_and_direction(belief: str) -> tuple:
    cleaned = clean_belief(belief)

    direction = "neutral"
    if any(word in cleaned for word in ["up", "rise", "bull", "increase", "moon"]):
        direction = "bullish"
    elif any(word in cleaned for word in ["down", "fall", "bear", "drop", "crash"]):
        direction = "bearish"

    # Default to SPY if no specific asset mentioned
    asset = "SPY"
    for symbol in ["AAPL", "TSLA", "NVDA", "QQQ", "SPY", "AMZN", "MSFT", "META"]:
        if symbol.lower() in cleaned:
            asset = symbol
            break

    return asset, direction
