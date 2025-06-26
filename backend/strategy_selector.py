# backend/strategy_selector.py

import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "multi_asset_model.joblib")
VECTORIZER_PATH = os.path.join(BASE_DIR, "multi_vectorizer.joblib")

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

# ✅ Strategy Definitions
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
    "Long Put": {
        "description": "Buy a put option to profit from a downward move",
        "risk_level": "high",
        "explanation": "Profit directly from sharp price declines; limited risk, high reward."
    },
    "Buy Stock": {
        "description": "Buy underlying shares of the company",
        "risk_level": "low",
        "explanation": "Simple long-term position with ownership."
    },
    "Buy Stock for Income": {
        "description": "Buy dividend-paying shares of the company",
        "risk_level": "low",
        "explanation": "Generates income through quarterly dividends while holding the stock."
    },
    "Default Strategy": {
        "description": "Fallback plan",
        "risk_level": "unknown",
        "explanation": "Model confidence too low — manual review recommended."
    },
}

def adjust_allocation(base_percent, risk_profile):
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
    latest_price = round(float(price_info["latest"]), 2) if isinstance(price_info, dict) else round(float(price_info), 2)
    belief_lower = belief.lower()

    # ✅ Manual override: Bond Ladder
    if "bond ladder" in belief_lower or "laddered bonds" in belief_lower:
        details = STRATEGY_DETAILS["Bond Ladder"]
        return {
            "type": "Bond Ladder",
            "description": details["description"],
            "risk_level": details["risk_level"],
            "suggested_allocation": adjust_allocation(25, risk_profile),
            "explanation": details["explanation"]
        }

    # ✅ Override: Long Put for Bearish Low Confidence
    if direction == "bearish" and ticker and confidence < 0.01:
        details = STRATEGY_DETAILS["Long Put"]
        strike = int(latest_price * 0.9)
        return {
            "type": "Long Put",
            "description": f"Buy {ticker} {strike}p",
            "risk_level": details["risk_level"],
            "suggested_allocation": adjust_allocation(20, risk_profile),
            "explanation": details["explanation"]
        }

    # ✅ New: Income tag or belief mentions income, and asset is equity
    if asset_class == "equity" and ("income" in belief_lower or "dividend" in belief_lower):
        details = STRATEGY_DETAILS["Buy Stock for Income"]
        return {
            "type": "Buy Stock for Income",
            "description": f"Buy {ticker} shares for dividend income",
            "risk_level": details["risk_level"],
            "suggested_allocation": adjust_allocation(20, risk_profile),
            "explanation": details["explanation"]
        }

    # ✅ Run ML Strategy Classifier
    input_text = f"{belief} | {asset_class} | {direction} | {goal_type} | risk: {risk_profile}"
    X = vectorizer.transform([input_text])
    predicted_type = model.predict(X)[0]

    # 🔧 Prevent ETF fallback if asset class is actually equity
    if predicted_type.lower() == "etf" and asset_class == "equity":
        predicted_type = "Buy Stock"

    # ✅ Format Strategy Output
    details = STRATEGY_DETAILS.get(predicted_type, STRATEGY_DETAILS["Default Strategy"])
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
