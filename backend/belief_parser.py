# backend/belief_parser.py

"""
This module parses the user's belief into structured components:
- Detects company names and tickers
- Infers market direction from keywords
- Predicts asset class using ML model
- Extracts tags via belief tag classifier
"""

import re
from backend.utils.ticker_list import ALL_TICKERS
from backend.utils.model_utils import load_model

# === Load Belief Tag Classifier ===
try:
    belief_model = load_model("belief_model.joblib")
    vectorizer = load_model("belief_vectorizer.joblib")
except Exception as e:
    print(f"[ERROR] Could not load belief/tag model: {e}")
    belief_model, vectorizer = None, None

# === Load Asset Class Classifier ===
try:
    asset_model = load_model("asset_class_model.joblib")
    asset_vectorizer = load_model("asset_vectorizer.joblib")
except Exception as e:
    print(f"[WARNING] Asset class model not loaded: {e}")
    asset_model, asset_vectorizer = None, None

# === Fallback map for company/sector keywords to tickers ===
SYMBOL_LOOKUP_MAP = {
    "tesla": "TSLA", "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA",
    "amazon": "AMZN", "meta": "META", "facebook": "META", "google": "GOOGL", "alphabet": "GOOGL",
    "palantir": "PLTR", "amd": "AMD", "snowflake": "SNOW", "amgen": "AMGN", "stanley black & decker": "SWK",
    "stanley": "SWK", "netflix": "NFLX", "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
    "nasdaq": "QQQ", "s&p": "SPY", "sp500": "SPY", "sp 500": "SPY", "dow": "DIA", "russell": "IWM",
    "bonds": "TLT", "treasury": "TLT", "financials": "XLF", "banks": "XLF", "energy": "XLE", "oil": "XLE",
    "tech": "XLK", "technology": "XLK", "ark": "ARKK", "cathie wood": "ARKK", "gold": "GLD"
}

def clean_belief(text: str) -> str:
    """
    Lowercases and strips special characters from the belief string.
    """
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower().strip())

def detect_ticker(belief: str) -> str:
    """
    Detect the most likely ticker symbol from belief using:
    1. Direct ticker match from ALL_TICKERS list.
    2. Fallback to known company/sector keyword map.
    """
    cleaned_belief = clean_belief(belief)

    # First pass: direct ticker mention
    for ticker in ALL_TICKERS:
        if ticker.lower() in cleaned_belief:
            return ticker.upper()

    # Second pass: keyword/company name match
    for keyword, mapped_ticker in SYMBOL_LOOKUP_MAP.items():
        if keyword in cleaned_belief:
            return mapped_ticker.upper()

    # No match found
    print("[TICKER DETECTION] No match — returning None")
    return None

def detect_direction(belief: str) -> str:
    """
    Infers market direction from belief text:
    Returns 'bullish', 'bearish', or 'neutral'.
    """
    text = belief.lower()

    bearish_words = ["down", "drop", "fall", "bear", "crash", "tank", "recession"]
    bullish_words = ["up", "rise", "bull", "skyrocket", "jump", "explode", "rally", "soar"]

    if any(word in text for word in bearish_words):
        return "bearish"
    elif any(word in text for word in bullish_words):
        return "bullish"
    else:
        return "neutral"

def detect_asset_class(raw_belief: str) -> str:
    """
    Uses ML model to predict asset class (stock, options, bond, crypto, etc).
    Falls back to 'options' if model is unavailable or errors occur.
    """
    if asset_model and asset_vectorizer:
        try:
            vec = asset_vectorizer.transform([raw_belief])
            prediction = asset_model.predict(vec)[0]
            print(f"[ASSET CLASS DETECTED] → {prediction}")
            return prediction
        except Exception as e:
            print(f"[ASSET CLASS ERROR] Failed to predict: {e}")
    
    # Default fallback
    print("[ASSET CLASS FALLBACK] Defaulting to 'options'")
    return "options"

def inject_keyword_tags(belief: str, tags: list) -> list:
    """
    Supplements ML tags with keyword-based tags from common phrases in belief.
    """
    belief_lower = belief.lower()

    keyword_map = {
        "bond": ["bond", "bonds", "treasury", "fixed income", "government bond"],
        "income": ["income", "yield", "dividend"],
        "crypto": ["bitcoin", "btc", "eth", "ethereum", "solana"],
        "etf": ["spy", "qqq", "index fund", "etf"],
        "safe": ["low risk", "safe", "stable", "preserve"],
    }

    for key, phrases in keyword_map.items():
        if any(phrase in belief_lower for phrase in phrases) and key not in tags:
            tags.append(key)

    return tags

def parse_belief(belief: str) -> dict:
    """
    Parses the user belief and returns structured data including:
    - ticker symbol
    - direction (bullish, bearish, neutral)
    - tags (from ML and keyword injection)
    - confidence score from tag ML model
    - predicted asset class (stock, options, bond, crypto, etc)
    """
    cleaned = clean_belief(belief)
    tag_list = []
    confidence = 0.0

    # ML-based tag prediction
    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            prediction = belief_model.predict(vec)[0]
            confidence = max(belief_model.predict_proba(vec)[0])

            # Split predicted tags into list
            raw_tags = re.split(r"[\n,]+", prediction)
            tag_list = [tag.strip() for tag in raw_tags if tag.strip()]
            # Sanitize tags to limit length and word count
            tag_list = [tag for tag in tag_list if len(tag) <= 30 and len(tag.split()) <= 4]
        except Exception as e:
            print(f"[TAG MODEL ERROR] Failed to classify belief: {e}")

    # Inject keyword-based fallback tags
    tag_list = inject_keyword_tags(belief, tag_list)

    # Predict asset class using ML or fallback
    predicted_asset_class = detect_asset_class(belief)

    # Final override logic for bonds
    lower_belief = belief.lower()
    if any(kw in lower_belief for kw in ["government bond", "treasury", "fixed income", "bond fund", "low-risk income"]):
        asset_class = "bond"
    elif "bond" in tag_list or "income" in tag_list:
        asset_class = "bond"
    else:
        asset_class = predicted_asset_class

    return {
        "ticker": detect_ticker(belief),
        "direction": detect_direction(belief),
        "tags": tag_list,
        "confidence": float(confidence),
        "asset_class": asset_class
    }

def detect_confidence(belief: str) -> float:
    """
    Separate method to get confidence score of tag classification.
    """
    cleaned = clean_belief(belief)
    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            return float(max(belief_model.predict_proba(vec)[0]))
        except Exception as e:
            print(f"[CONFIDENCE ERROR] {e}")
    return 0.5  # fallback default confidence
