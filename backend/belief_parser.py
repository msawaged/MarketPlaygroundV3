# belief_parser.py
# Parses the belief into clean text, direction, and asset class.

import re
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

# Load the vectorizer and classifier
belief_vectorizer = joblib.load("belief_vectorizer.joblib")
belief_classifier = joblib.load("belief_classifier.joblib")

def clean_belief(belief: str) -> str:
    """
    Clean and normalize belief text.
    """
    belief = belief.lower().strip()
    belief = re.sub(r"[^a-zA-Z0-9\s]", "", belief)
    return belief

def detect_asset_and_direction(belief: str) -> dict:
    """
    Predict the asset class and directional sentiment from a belief.
    """
    cleaned = clean_belief(belief)
    vector = belief_vectorizer.transform([cleaned])
    prediction = belief_classifier.predict(vector)[0]

    # Determine direction heuristically
    direction = "up"
    if any(word in cleaned for word in ["fall", "drop", "crash", "bear", "tank", "down"]):
        direction = "down"
    elif any(word in cleaned for word in ["flat", "sideways", "nothing", "neutral"]):
        direction = "neutral"

    return {
        "asset_class": prediction,
        "direction": direction
    }
