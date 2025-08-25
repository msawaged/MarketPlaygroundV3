# backend/belief_parser.py
print("🔍 belief_parser.py: Top of file reached")

"""
This module parses the user's belief into structured components:
- Detects company names and tickers
- Infers market direction from keywords
- Predicts asset class using ML model pipeline
# - Extracts tags via ML classifier and keyword injection
"""

import re
from backend.utils.ticker_sanitizer import finalize_detected_ticker
from backend.utils.symbol_universe import is_tradable_symbol, normalize_ticker  # ✅ Step C guards

# from backend.utils.ticker_list import ALL_TICKERS
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
    "ai healthcare": "HART",
    "healthcare ai": "HART",
    "ai in healthcare": "HART",
    "biotech ai": "ARKG",
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
    """Enhanced ticker detection with Step C tradability guards."""
    belief_lower = belief.lower()

    # 🎯 STEP 1: Direct ticker pattern matching (TSLA, AAPL, etc.)
    ticker_pattern = r'\b([A-Z]{1,5})\b'
    ticker_matches = re.findall(ticker_pattern, belief.upper())

    # Filter out common false positives
    false_positives = {
        "THE","AND","OR","BUT","FOR","IN","ON","AT","TO","UP","GO","BUY","SELL",
        "THINK","WILL","I","HIT","MOON","DROP","FALL","RISE","JUMP","RUN","TANK",
        "SOAR","AFTER","BEFORE","WHEN","WHERE","WHY","HOW","WHAT","WHO","CAN",
        "COULD","WOULD","SHOULD","MIGHT","MAY","MUST","SHALL","HAVE","HAS","HAD",
        "IS","ARE","WAS","WERE","BE","BEEN","BEING","DO","DOES","DID","DONE",
        "GET","GOT","GIVE","GAVE","TAKE","TOOK","MAKE","MADE","COME","CAME",
        "LOOK","SEEMS","FEEL","FEELS","LIKE","LOVE","WANT","NEED","KNOW","SAY",
        "SAID","TELL","TOLD","ASK","ASKED","SHOW","SEEN","SEE","FIND","FOUND",
        "CALL","CALLS","WORK","WORKS","TRY","TRIES","HELP","HELPS","MOVE","MOVES",
        "TURN","TURNS","KEEP","KEEPS","START","STARTS","STOP","STOPS","PLAY","PLAYS",
        "RUN","RUNS","WALK","WALKS","TALK","TALKS","READ","READS","WRITE","WRITES",
        "HEAR","HEARS","LISTEN","FOLLOW","OPEN","OPENS","CLOSE","CLOSES","LEAVE",
        "LEAVES","STAY","STAYS","LIVE","LIVES","DIE","DIES","KILL","KILLS","EAT",
        "EATS","DRINK","DRINKS","SLEEP","SLEEPS","WAKE","WAKES","SIT","SITS","STAND",
        "STANDS","LIE","LIES","WIN","WINS","LOSE","LOSES","FIGHT","FIGHTS","PEACE",
        "WAR","WARS","HOPE","HOPES","FEAR","FEARS","HAPPY","SAD","GOOD","BAD",
        "BIG","SMALL","LONG","SHORT","HIGH","LOW","FAST","SLOW","HOT","COLD",
        "OLD","NEW","YOUNG","EASY","HARD","RIGHT","WRONG","TRUE","FALSE","REAL",
        "FAKE","SAME","DIFFERENT","FULL","EMPTY","RICH","POOR","FREE","BUSY",
        "EARLY","LATE","SOON","NEVER","ALWAYS","OFTEN","SOMETIMES","RARELY","MAYBE",
        "PROBABLY","DEFINITELY","CERTAINLY","POSSIBLY","LIKELY","UNLIKELY","SURE",
        "UNSURE","CLEAR","UNCLEAR","OBVIOUS","HIDDEN","SIMPLE","COMPLEX","EASY",
        "DIFFICULT","POSSIBLE","IMPOSSIBLE","LEGAL","ILLEGAL","SAFE","DANGEROUS",
        "HEALTHY","SICK","STRONG","WEAK","SMART","STUPID","FUNNY","SERIOUS",
        "NICE","MEAN","KIND","CRUEL","FAIR","UNFAIR","JUST","UNJUST","HONEST",
        "DISHONEST","LOYAL","DISLOYAL","PATIENT","IMPATIENT","CALM","ANGRY",
        "EXCITED","BORED","INTERESTED","UNINTERESTED","SURPRISED","SHOCKED",
        "CONFUSED","UNDERSTANDING","WORRIED","RELAXED","STRESSED","PEACEFUL",
        "TESLA","APPLE","MICROSOFT","NVIDIA","AMAZON","GOOGLE","FACEBOOK","NETFLIX","BITCOIN","ETHEREUM"
    }
    # Enforce min length 2 here; remaining validity handled by is_tradable_symbol
    candidate_tickers = [t for t in ticker_matches if t not in false_positives and len(t) >= 2]

    for t in candidate_tickers:
        tt = normalize_ticker(t)
        if is_tradable_symbol(tt):
            print(f"🎯 Direct ticker match found: {tt}")
            return tt
        else:
            print(f"[PARSER] Rejected direct match (not tradable): {tt}")

    # 🎯 STEP 2: Company name to ticker mapping
    for company, ticker in SYMBOL_LOOKUP_MAP.items():
        if company in belief_lower:
            tt = normalize_ticker(ticker)
            if is_tradable_symbol(tt):
                print(f"🎯 Company name match: {company} → {tt}")
                return tt
            else:
                print(f"[PARSER] Rejected company map (not tradable): {company}→{tt}")

    # 🎯 STEP 3: AI/Healthcare theme mapping
    for theme, ticker in AI_HEALTHCARE_MAP.items():
        if theme in belief_lower:
            tt = normalize_ticker(ticker)
            if is_tradable_symbol(tt):
                print(f"🎯 AI/Healthcare theme match: {theme} → {tt}")
                return tt
            else:
                print(f"[PARSER] Rejected AI/Healthcare map (not tradable): {theme}→{tt}")

    # 🎯 STEP 4: Market theme mapping
    for theme, ticker in THEME_TO_TICKER_MAP.items():
        if theme in belief_lower:
            tt = normalize_ticker(ticker)
            if is_tradable_symbol(tt):
                print(f"🎯 Market theme match: {theme} → {tt}")
                return tt
            else:
                print(f"[PARSER] Rejected market theme map (not tradable): {theme}→{tt}")

    # 🎯 STEP 5: Currency mapping
    for currency, ticker in CURRENCY_LOOKUP_MAP.items():
        if currency in belief_lower:
            tt = normalize_ticker(ticker)
            if is_tradable_symbol(tt):
                print(f"🎯 Currency match: {currency} → {tt}")
                return tt
            else:
                print(f"[PARSER] Rejected currency map (not tradable): {currency}→{tt}")

    # 🎯 STEP 6: Asset class specific defaults (validate each default)
    if asset_class == "bond":
        tt = "TLT"
        if is_tradable_symbol(tt):
            print("🎯 Bond asset class → TLT")
            return tt
    elif asset_class == "crypto":
        # NOTE: 'BTC' won't be tradable in Alpaca equities universe; leave to final guard
        tt = "BTC"
        print("🎯 Crypto asset class → BTC (will be validated later)")
        return tt
    elif asset_class == "equity":
        tt = "SPY"
        if is_tradable_symbol(tt):
            print("🎯 Equity asset class → SPY")
            return tt

    # 🎯 STEP 7: Final fallback (still validated later)
    print("❌ No ticker detected, using SPY fallback (will be validated)")
    return "SPY"

def detect_direction(belief: str) -> str:
    """
    Enhanced direction detection with expanded keywords and price target logic
    """
    text = belief.lower()

    bearish_words = [
        "down","drop","fall","bear","crash","tank","recession","weaken",
        "decline","plummet","tumble","sink","collapse","crater","dump",
        "short","puts","bearish","sell","negative","bad","terrible",
        "overvalued","bubble","correction","pullback","dip"
    ]
    bullish_words = [
        "up","rise","bull","skyrocket","jump","explode","rally","soar","strengthen",
        "moon","hit","reach","target","climb","pump","breakout","surge",
        "long","calls","bullish","buy","positive","good","strong",
        "undervalued","growth","momentum","rocket","blast","spike"
    ]

    if any(word in text for word in bearish_words):
        return "bearish"
    if any(word in text for word in bullish_words):
        return "bullish"

    # Price target logic
    price_patterns = [
        r'(?:hit|reach|target|to|at)\s+\$?(\d+(?:,\d+)*(?:\.\d+)?)[k]?',
        r'\$(\d+(?:,\d+)*(?:\.\d+)?)[k]?\s+(?:target|goal)',
        r'(\d+(?:,\d+)*(?:\.\d+)?)[k]?\s+(?:by|within)'
    ]
    for pattern in price_patterns:
        matches = re.findall(pattern, text)
        if matches:
            target_str = matches[0].replace(',', '')
            try:
                target_price = float(target_str)
                if 'k' in text and target_price < 1000:
                    target_price *= 1000
                if target_price > 0:
                    print(f"[DIRECTION] Price target detected: {target_price} - assuming bullish")
                    return "bullish"
            except ValueError:
                pass

    pct_patterns = [
        r'(\d+)%?\s+(?:gain|increase|up)',
        r'(?:gain|increase|up)\s+(\d+)%?',
        r'(\d+)%?\s+(?:loss|decrease|down)',
        r'(?:loss|decrease|down)\s+(\d+)%?'
    ]
    for i, pattern in enumerate(pct_patterns):
        matches = re.findall(pattern, text)
        if matches:
            return "bullish" if i < 2 else "bearish"

    positive_context = [
        "good","great","excellent","strong","solid","promising",
        "optimistic","confident","bright","positive","favorable"
    ]
    negative_context = [
        "bad","terrible","weak","poor","concerning","worried",
        "pessimistic","negative","unfavorable","risky","dangerous"
    ]
    if any(word in text for word in positive_context):
        return "bullish"
    if any(word in text for word in negative_context):
        return "bearish"

    print(f"[DIRECTION] No clear direction detected in: '{belief}' - defaulting to neutral")
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
        "bond": ["bond","bonds","treasury","fixed income","government bond"],
        "income": ["income","yield","dividend"],
        "crypto": ["bitcoin","btc","eth","ethereum","solana"],
        "etf": ["spy","qqq","index fund","etf"],
        "safe": ["low risk","safe","stable","preserve"],
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

    time_match = re.search(r'(in|within|by)\s+(the next\s+)?(\d+)\s*(day|week|month|year)s?', belief.lower())
    if time_match:
        timeframe = f"{time_match.group(3)} {time_match.group(4)}"

    # === Asset class override if bond- or crypto-related ===
    lower_belief = belief.lower()
    crypto_terms = ("bitcoin", "btc", "eth", "ethereum", "crypto")
    if any(kw in lower_belief for kw in BOND_KEYWORDS) or "bond" in tag_list or "income" in tag_list:
        asset_class = "bond"
    elif any(term in lower_belief for term in crypto_terms):
        asset_class = "crypto"
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

    raw_detected_ticker = detect_ticker(belief, asset_class)
    detected_ticker = finalize_detected_ticker(cleaned, raw_detected_ticker, asset_class)

    # 🚧 Final Step C guard — ensure final ticker is actually tradable
    final_t = normalize_ticker(detected_ticker or "")

    if asset_class == "crypto":
        # Skip the Alpaca tradability check for crypto tickers (e.g. BTC, ETH)
        print(f"[PARSER] Crypto asset class — skipping Alpaca tradability check for {final_t}")
    else:
        if not is_tradable_symbol(final_t):
            print(f"[PARSER] ❌ Final ticker not tradable: {detected_ticker!r} (asset_class={asset_class}) → defaulting to SPY")
            final_t = "SPY"


    print(f"[DEBUG] Detected Ticker (raw): {raw_detected_ticker}")
    print(f"[DEBUG] Detected Ticker (final): {final_t}")

    direction = detect_direction(belief)
    print(f"[DEBUG] Direction: {direction}")
    print(f"[DEBUG] Confidence: {confidence}")
    print("[DEBUG] -------------------------------\n")

    # === Final structured belief output ===
    return {
        "ticker": final_t,
        "direction": direction,
        "tags": tag_list,
        "confidence": float(confidence),
        "asset_class": asset_class,
        "goal_type": goal_type,
        "multiplier": multiplier,
        "timeframe": timeframe,
    }

    # (Unreachable legacy code retained intentionally during cleanup)
    cleaned = clean_belief(belief)
    if belief_model and vectorizer:
        try:
            vec = vectorizer.transform([cleaned])
            return float(max(belief_model.predict_proba(vec)[0]))
        except Exception as e:
            print(f"[CONFIDENCE ERROR] {e}")
    return 0.5
