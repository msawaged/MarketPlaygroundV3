# backend/belief_parser.py

"""
This module parses the user's belief into structured components:
- Detects company names and tickers
- Infers market direction from keywords
- Predicts asset class using ML model pipeline
- Extracts tags via ML classifier and keyword injection
"""

import re
from backend.utils.ticker_list import ALL_TICKERS
from backend.utils.model_utils import load_model

# === Load Belief Tag Classifier + Vectorizer ===
try:
    belief_model = load_model("belief_model.joblib")
    vectorizer = load_model("belief_vectorizer.joblib")
except Exception as e:
    print(f"[ERROR] Could not load belief/tag model: {e}")
    belief_model, vectorizer = None, None

# === Load Asset Class Model (full pipeline) ===
try:
    asset_model = load_model("asset_class_model.joblib")  # pipeline includes vectorizer
except Exception as e:
    print(f"[WARNING] Asset class model not loaded: {e}")
    asset_model = None

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

BOND_KEYWORDS = ["bond", "bonds", "bond ladder", "income", "fixed income", "treasury", "muni", "municipal bond"]

def clean_belief(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower().strip())

def detect_ticker(belief: str, asset_class: str = None) -> str:
    """
    Returns a detected ticker from the belief. If asset_class is 'bond' and no ticker is detected,
    returns a bond ETF fallback (AGG or BND).
    """
    cleaned_belief = clean_belief(belief)

    for ticker in ALL_TICKERS:
        if ticker.lower() in cleaned_belief:
            return ticker.upper()

    for keyword, mapped_ticker in SYMBOL_LOOKUP_MAP.items():
        if keyword in cleaned_belief:
            return mapped_ticker.upper()

    # ✅ If this is a bond-related belief and no ticker was found, assign bond ETF fallback
    if asset_class == "bond":
        print("[TICKER DETECTION] No match — assigning fallback bond ETF (AGG)")
        return "AGG"

    print("[TICKER DETECTION] No match — returning None")
    return None

def detect_direction(belief: str) -> str:
    text = belief.lower()
    bearish_words = ["down", "drop", "fall", "bear", "crash", "tank", "recession"]
    bullish_words = ["up", "rise", "bull", "skyrocket", "jump", "explode", "rally", "soar"]

    if any(word in text for word in bearish_words):
        return "bearish"
    elif any(word in text for word in bullish_words):
        return "bullish"
    return "neutral"

def detect_asset_class(raw_belief: str) -> str:
    """
    Uses full ML pipeline to predict asset class.
    """
    if asset_model:
        try:
            prediction = asset_model.predict([raw_belief])[0]
            print(f"[ASSET CLASS DETECTED] → {prediction}")
            return prediction
        except Exception as e:
            print(f"[ASSET CLASS ERROR] Failed to predict: {e}")
    
    print("[ASSET CLASS FALLBACK] Defaulting to 'options'")
    return "options"

def inject_keyword_tags(belief: str, tags: list) -> list:
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
    cleaned = clean_belief(belief)
    tag_list = []
    confidence = 0.0

    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            prediction = belief_model.predict(vec)[0]
            confidence = max(belief_model.predict_proba(vec)[0])
            raw_tags = re.split(r"[\n,]+", prediction)
            tag_list = [tag.strip() for tag in raw_tags if tag.strip()]
            tag_list = [tag for tag in tag_list if len(tag) <= 30 and len(tag.split()) <= 4]
        except Exception as e:
            print(f"[TAG MODEL ERROR] Failed to classify belief: {e}")

    tag_list = inject_keyword_tags(belief, tag_list)

    # 🔍 Asset class logic override if bond keywords are found
    lower_belief = belief.lower()
    if any(kw in lower_belief for kw in BOND_KEYWORDS) or "bond" in tag_list or "income" in tag_list:
        asset_class = "bond"
    else:
        asset_class = detect_asset_class(belief)

    return {
        "ticker": detect_ticker(belief, asset_class),
        "direction": detect_direction(belief),
        "tags": tag_list,
        "confidence": float(confidence),
        "asset_class": asset_class
    }

def detect_confidence(belief: str) -> float:
    cleaned = clean_belief(belief)
    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            return float(max(belief_model.predict_proba(vec)[0]))
        except Exception as e:
            print(f"[CONFIDENCE ERROR] {e}")
    return 0.5
