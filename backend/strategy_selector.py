# backend/strategy_selector.py

"""
Dynamic Strategy Selector using trained ML model (multi_asset_model.joblib).
This version learns from belief, asset class, direction, goal, and other signals.
Includes manual override logic for known phrases like 'bond ladder'.
"""

import joblib
import os

# Load model and vectorizer (only once)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "multi_asset_model.joblib")
VECTORIZER_PATH = os.path.join(BASE_DIR, "multi_vectorizer.joblib")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

# Metadata for common strategies
STRATEGY_DETAILS = {
    "Bond Ladder": {
        "description": "Build a bond ladder by buying bonds with staggered maturities (e.g. 1Y, 3Y, 5Y)",
        "risk_level": "low",
        "explanation": "Bond ladders offer consistent income and reduce interest rate risk."
    },
    "Iron Condor": {
        "description": "Sell call & put spreads on same expiry",
        "risk_level": "medium",
        "explanation": "Neutral volatility play; good when expecting sideways markets."
    },
    "Bull Call Spread": {
        "description": "Buy call / Sell higher call",
        "risk_level": "high",
        "explanation": "Bullish spread to profit on upward moves with limited risk."
    },
    "Buy Stock": {
        "description": "Buy underlying shares of the company",
        "risk_level": "low",
        "explanation": "Simple long-term position with ownership."
    },
    "Default Strategy": {
        "description": "Fallback plan",
        "risk_level": "unknown",
        "explanation": "Model confidence too low — manual review recommended."
    },
    # Add more strategy metadata as needed
}

def adjust_allocation(base_percent, risk_profile):
    """
    Adjust allocation percentage based on risk profile.
    """
    if risk_profile == "conservative":
        return f"{int(base_percent * 0.6)}%"
    elif risk_profile == "aggressive":
        return f"{int(base_percent * 1.4)}%"
    return f"{base_percent}%"

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
    Predicts or selects a trading strategy based on user belief and ML model.
    Falls back to manual rules when applicable.
    """
    latest_price = round(float(price_info["latest"]), 2) if isinstance(price_info, dict) else round(float(price_info), 2)

    # ✅ MANUAL OVERRIDE for bond ladder
    if "bond ladder" in belief.lower() or "laddered bonds" in belief.lower():
        details = STRATEGY_DETAILS["Bond Ladder"]
        return {
            "type": "Bond Ladder",
            "description": details["description"],
            "risk_level": details["risk_level"],
            "suggested_allocation": adjust_allocation(25, risk_profile),
            "explanation": details["explanation"]
        }

    # ✅ ML Prediction Path
    input_text = f"{belief} | {asset_class} | {direction} | {goal_type} | risk: {risk_profile}"
    X = vectorizer.transform([input_text])
    predicted_type = model.predict(X)[0]

    # Use default if unrecognized
    details = STRATEGY_DETAILS.get(predicted_type, STRATEGY_DETAILS["Default Strategy"])

    # Dynamically format option descriptions
    description = details["description"]
    if "call" in predicted_type.lower():
        description = f"Buy {ticker} {int(latest_price * 1.05)}c / Sell {ticker} {int(latest_price * 1.15)}c"
    elif "put" in predicted_type.lower():
        description = f"Buy {ticker} {int(latest_price * 0.95)}p / Sell {ticker} {int(latest_price * 0.85)}p"

    return {
        "type": predicted_type,
        "description": description,
        "risk_level": details["risk_level"],
        "suggested_allocation": adjust_allocation(20, risk_profile),
        "explanation": details["explanation"]
    }
