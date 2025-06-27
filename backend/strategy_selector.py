# backend/strategy_selector.py

import joblib
import os

# 🔁 Load trained ML model and vectorizer for strategy classification
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "multi_asset_model.joblib")
VECTORIZER_PATH = os.path.join(BASE_DIR, "multi_vectorizer.joblib")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

# 📚 Human-readable metadata for each supported strategy
STRATEGY_DETAILS = {
    "bond ladder": {
        "description": "Build a bond ladder by buying bonds with staggered maturities (e.g. 1Y, 3Y, 5Y)",
        "risk_level": "low",
        "explanation": "Bond ladders offer consistent income and reduce interest rate risk."
    },
    "iron condor": {
        "description": "Sell call & put spreads on same expiry",
        "risk_level": "medium",
        "explanation": "Neutral volatility play; good when expecting sideways markets."
    },
    "bull call spread": {
        "description": "Buy call / Sell higher call",
        "risk_level": "high",
        "explanation": "Bullish spread to profit on upward moves with limited risk."
    },
    "long put": {
        "description": "Buy a put option to profit from a downward move",
        "risk_level": "high",
        "explanation": "Profit directly from sharp price declines; limited risk, high reward."
    },
    "buy stock": {
        "description": "Buy underlying shares of the company",
        "risk_level": "low",
        "explanation": "Simple long-term position with ownership."
    },
    "buy stock for income": {
        "description": "Buy dividend-paying shares of the company",
        "risk_level": "low",
        "explanation": "Generates income through quarterly dividends while holding the stock."
    },
    "default strategy": {
        "description": "Fallback plan",
        "risk_level": "unknown",
        "explanation": "Model confidence too low — manual review recommended."
    }
}

# 🎯 Adjust suggested capital allocation based on user's risk profile
def adjust_allocation(base_percent: int, risk_profile: str) -> str:
    if risk_profile == "conservative":
        return f"{int(base_percent * 0.6)}%"
    elif risk_profile == "aggressive":
        return f"{int(base_percent * 1.4)}%"
    return f"{base_percent}%"

# 🧠 Core AI strategy selection logic
def select_strategy(
    belief: str,
    direction: str,
    ticker: str,
    asset_class: str,
    price_info: dict,
    confidence: float = 0.5,
    goal_type: str = None,
    multiplier: float = None,
    timeframe: str = None,
    expiry_date: str = None,
    risk_profile: str = "moderate"
) -> dict:
    """
    Uses ML model to generate a strategy recommendation from user belief and parsed metadata.
    Returns a structured dict describing the suggested strategy.
    """

    # ✅ Extract and round latest price
    latest_price = round(float(price_info["latest"]), 2) if isinstance(price_info, dict) else round(float(price_info), 2)

    # 🧪 Construct formatted input string for vectorizer
    model_input = f"{belief} | {asset_class} | {direction} | {goal_type or 'none'} | risk: {risk_profile}"

    # 🔍 Predict strategy using ML model
    X = vectorizer.transform([model_input])
    predicted_type = model.predict(X)[0]
    normalized = predicted_type.strip().lower()

    print(f"[ML MODEL PREDICTION] → {normalized}")

    # 🔁 Handle known prediction aliases (map to STRATEGY_DETAILS keys)
    alias_map = {
        "stock": "buy stock",
        "equity": "buy stock",
        "dividend stock": "buy stock for income"
    }
    if normalized in alias_map:
        normalized = alias_map[normalized]

    # 🛑 Fallback if prediction not recognized
    if normalized not in STRATEGY_DETAILS:
        print(f"[WARN] Unknown prediction: {normalized} → using default strategy.")
        normalized = "default strategy"

    # 📚 Get metadata for the strategy
    details = STRATEGY_DETAILS[normalized]

    # 🧱 Dynamically build strategy description
    if "call" in normalized:
        description = f"Buy {ticker} {int(latest_price * 1.05)}c / Sell {ticker} {int(latest_price * 1.15)}c"
    elif "put" in normalized:
        description = f"Buy {ticker} {int(latest_price * 0.95)}p / Sell {ticker} {int(latest_price * 0.85)}p"
    elif "income" in normalized:
        description = f"Buy {ticker} shares for dividend income"
    elif "stock" in normalized:
        description = f"Buy {ticker} shares"
    else:
        description = details["description"]

    # 📤 Return final strategy dict
    return {
        "type": normalized,
        "description": description,
        "risk_level": details["risk_level"],
        "suggested_allocation": adjust_allocation(20, risk_profile),
        "explanation": details["explanation"]
    }

# 🔧 Local test block to verify functionality when run directly
if __name__ == "__main__":
    print("🧪 Running strategy_selector test...")

    test_belief = "I think AAPL will go up sharply after earnings"
    strategy = select_strategy(
        belief=test_belief,
        direction="bullish",
        ticker="AAPL",
        asset_class="stock",
        price_info={"latest": 195.60},
        confidence=0.8,
        goal_type="multiply",
        multiplier=2.0,
        timeframe="short",
        risk_profile="moderate"
    )

    print("\n🎯 [TEST STRATEGY OUTPUT]")
    for k, v in strategy.items():
        print(f"{k.capitalize()}: {v}")
