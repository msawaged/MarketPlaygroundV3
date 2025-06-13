# belief_parser.py
# Parses raw user beliefs into structured tags using your trained ML model

import joblib
import re

# Load the trained ML model and vectorizer
model = joblib.load("belief_model.joblib")
vectorizer = joblib.load("belief_vectorizer.joblib")

# Basic fallback tickers list (can be upgraded with ML later)
COMMON_TICKERS = {
    "oil": "OIL",
    "gold": "GOLD",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "apple": "AAPL",
    "aapl": "AAPL",
    "spy": "SPY",
    "qqq": "QQQ",
    "nvda": "NVDA",
    "nvidia": "NVDA",
    "amazon": "AMZN",
    "amzn": "AMZN"
}

def detect_ticker(belief_text):
    """
    Tries to detect a known ticker/symbol from the belief text.
    """
    belief_text = belief_text.lower()
    for keyword, ticker in COMMON_TICKERS.items():
        if keyword in belief_text:
            return ticker
    return "SPY"  # Default fallback

def predict_tags(belief_text):
    """
    Uses the ML model to predict direction, duration, and volatility from a belief.
    """
    X = vectorizer.transform([belief_text])
    preds = model.predict(X)

    direction, duration, volatility = preds[0]
    return {
        "direction": direction,
        "duration": duration,
        "volatility": volatility
    }

def parse_belief(belief_text):
    """
    Main entry point to convert raw user belief into structured data.
    """
    return {
        "input": belief_text,
        "ticker": detect_ticker(belief_text),
        "tags": predict_tags(belief_text)
    }
