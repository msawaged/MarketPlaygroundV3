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
    asset_model = load_model("asset_class_model.joblib")
except Exception as e:
    print(f"[WARNING] Asset class model not loaded: {e}")
    asset_model = None


# === Fallback keyword-to-ticker maps ===
SYMBOL_LOOKUP_MAP = {
    "tesla": "TSLA", "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA",
    "amazon": "AMZN", "meta": "META", "facebook": "META", "google": "GOOGL", "alphabet": "GOOGL",
    "palantir": "PLTR", "amd": "AMD", "snowflake": "SNOW", "amgen": "AMGN", "stanley black & decker": "SWK",
    "stanley": "SWK", "netflix": "NFLX", "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
    "nasdaq": "QQQ", "s&p": "SPY", "sp500": "SPY", "sp 500": "SPY", "dow": "DIA", "russell": "IWM",
    "bonds": "TLT", "treasury": "TLT", "financials": "XLF", "banks": "XLF", "energy": "XLE", "oil": "XLE",
    "tech": "XLK", "technology": "XLK", "ark": "ARKK", "cathie wood": "ARKK", "gold": "GLD"
}

# === New: AI + Healthcare theme fallback ===
AI_HEALTHCARE_MAP = {
    "ai healthcare": "HART",  # Global X Health & AI ETF
    "healthcare ai": "HART",
    "ai in healthcare": "HART",
    "biotech ai": "ARKG",     # Genomics + AI
    "biotech": "ARKG",
    "healthcare": "XLV",
    "machine learning": "QQQ",
    "artificial intelligence": "QQQ"
}

# === Fallback for broad market themes ===
THEME_TO_TICKER_MAP = {
    "the market": "SPY",
    "stock market": "SPY",
    "markets": "SPY",
    "tech stocks": "QQQ",
    "tech sector": "QQQ",
    "growth stocks": "ARKK",
    "value stocks": "VTV",
    "broad market": "SPY",
    "economy": "SPY",
    "recession": "SPY",
    "inflation": "TIP",
    "interest rates": "TLT",
    "fed": "TLT",
    "federal reserve": "TLT",
    "crash": "SPY",
    "tank": "SPY",
    "boom": "QQQ",
    "bubble": "SPY"
}


# === New: currency-specific logic ===
CURRENCY_LOOKUP_MAP = {
    "usd": "UUP", "dollar": "UUP", "us dollar": "UUP",
    "euro": "FXE", "eur": "FXE",
    "yen": "FXY", "jpy": "FXY",
    "pound": "FXB", "gbp": "FXB",
    "yuan": "CYB", "cny": "CYB"
}

BOND_KEYWORDS = ["bond", "bonds", "bond ladder", "income", "fixed income", "treasury", "muni", "municipal bond"]

def clean_belief(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\s]", "", text.lower().strip())

def detect_ticker(belief: str, asset_class: str = None) -> str:
    cleaned_belief = clean_belief(belief)
    print(f"[DEBUG][TICKER] Cleaned Belief: {cleaned_belief}")

    # ✅ Absolute override for market crash beliefs
    if "the market" in cleaned_belief and any(word in cleaned_belief for word in ["crash", "tank", "drop", "fall", "recession"]):
        print("[DEBUG][TICKER] 🛑 Forced fallback: 'the market' + crash keywords → SPY")
        return "SPY"

    # ✅ Hardcode Nvidia for test
    if "nvidia" in cleaned_belief:
        print("[DEBUG][TICKER] ✅ Nvidia detected in belief — returning NVDA")
        return "NVDA"

    # ✅ Prioritize known mappings
    found_match = False
    for keyword, mapped_ticker in SYMBOL_LOOKUP_MAP.items():
        if keyword in cleaned_belief:
            print(f"[DEBUG][TICKER] ⚠️ Keyword match: '{keyword}' → {mapped_ticker}")
            found_match = True
            return mapped_ticker.upper()

    if not found_match:
        print("[DEBUG][TICKER] No SYMBOL_LOOKUP_MAP match found.")

   # ✅ Match currencies (e.g., USD → UUP)
    for keyword, mapped_ticker in CURRENCY_LOOKUP_MAP.items():
        if keyword in cleaned_belief:
            print(f"[DEBUG][TICKER] Matched currency: {keyword} → {mapped_ticker}")
            return mapped_ticker.upper()

    # ✅ Match broad market themes (e.g., "the market will crash" → SPY)
    for theme, fallback_ticker in THEME_TO_TICKER_MAP.items():
        if theme in cleaned_belief:
            print(f"[DEBUG][TICKER] Matched theme fallback: '{theme}' → {fallback_ticker}")
            return fallback_ticker.upper()

    # ✅ Match AI + healthcare themes
    for theme, fallback_ticker in AI_HEALTHCARE_MAP.items():
        if theme in cleaned_belief:
            print(f"[DEBUG][TICKER] Matched AI/Healthcare fallback: '{theme}' → {fallback_ticker}")
            return fallback_ticker.upper()


    # ❌ No ticker match found
    print("[DEBUG][TICKER] ❌ No ticker detected — returning 'UNKNOWN'")
    # ✅ Fallback: Match if any real ticker symbol is explicitly mentioned in the belief
    for symbol in ALL_TICKERS:
        if symbol.lower() in cleaned_belief.split():
            print(f"[DEBUG][TICKER] 🧠 Matched actual ticker in belief: {symbol}")
            return symbol.upper()

    return "UNKNOWN"



def detect_direction(belief: str) -> str:
    text = belief.lower()
    bearish_words = ["down", "drop", "fall", "bear", "crash", "tank", "recession", "weaken"]
    bullish_words = ["up", "rise", "bull", "skyrocket", "jump", "explode", "rally", "soar", "strengthen"]

    if any(word in text for word in bearish_words):
        return "bearish"
    elif any(word in text for word in bullish_words):
        return "bullish"
    return "neutral"

def detect_asset_class(raw_belief: str) -> str:
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

    # === Tag prediction via ML ===
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

    # === Keyword tag injection (overlay) ===
    tag_list = inject_keyword_tags(belief, tag_list)

    # === Goal Parsing ===
    goal_type = "unspecified"
    multiplier = None
    timeframe = None

    multiplier_match = re.search(r'(\d+(\.\d+)?)\s*x\b', belief.lower())
    if multiplier_match:
        multiplier = float(multiplier_match.group(1))
        goal_type = "multiply_money"

    alt_match = re.search(r'\b(double|triple|quadruple)\b', belief.lower())
    if alt_match:
        word = alt_match.group(1)
        if word == "double":
            multiplier = 2.0
        elif word == "triple":
            multiplier = 3.0
        elif word == "quadruple":
            multiplier = 4.0
        goal_type = "multiply_money"

    # Optional timeframe extraction (e.g. "in 6 months", "by next year")
    time_match = re.search(r'(in|within|by)\s+(the next\s+)?(\d+)\s*(day|week|month|year)s?', belief.lower())
    if time_match:
        timeframe = f"{time_match.group(3)} {time_match.group(4)}"

    # === Asset class override if bond-related ===
    lower_belief = belief.lower()
    if any(kw in lower_belief for kw in BOND_KEYWORDS) or "bond" in tag_list or "income" in tag_list:
        asset_class = "bond"
    else:
        asset_class = detect_asset_class(belief)

    
    # ✅ Debugging output to verify belief parsing
    print("\n[DEBUG] --- Belief Parsing Result ---")
    print(f"[DEBUG] Belief: {belief}")
    print(f"[DEBUG] Cleaned: {cleaned}")
    print(f"[DEBUG] Tags: {tag_list}")
    print(f"[DEBUG] Goal Type: {goal_type}")
    print(f"[DEBUG] Multiplier: {multiplier}")
    print(f"[DEBUG] Timeframe: {timeframe}")
    print(f"[DEBUG] Asset Class: {asset_class}")
    detected_ticker = detect_ticker(belief, asset_class)
    print(f"[DEBUG] Detected Ticker: {detected_ticker}")

    print(f"[DEBUG] Direction: {detect_direction(belief)}")
    print(f"[DEBUG] Confidence: {confidence}")
    print("[DEBUG] -------------------------------\n")
    # === Final structured belief output ===
    return {
        "ticker": detected_ticker,
        "direction": detect_direction(belief),
        "tags": tag_list,
        "confidence": float(confidence),
        "asset_class": asset_class,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe
    }
    cleaned = clean_belief(belief)
    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            return float(max(belief_model.predict_proba(vec)[0]))
        except Exception as e:
            print(f"[CONFIDENCE ERROR] {e}")
    return 0.5
