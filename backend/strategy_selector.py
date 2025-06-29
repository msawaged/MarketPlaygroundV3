# backend/strategy_selector.py

import os
import pandas as pd
import joblib  # ✅ Correct loader for joblib-saved pipeline

# ✅ Import custom feature combiner used in the model
from backend.utils.feature_utils import combine_features

# ✅ Define path to trained ML pipeline and encoder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "smart_strategy_pipeline.joblib")
ENCODER_PATH = os.path.join(BASE_DIR, "strategy_label_encoder.joblib")

# ✅ Load pipeline and label encoder using joblib
pipeline = joblib.load(MODEL_PATH)
encoder = joblib.load(ENCODER_PATH)

# 📚 Strategy metadata — advisor-grade strategy explanations
STRATEGY_DETAILS = {
    "buy stock": {
        "description": "Buy shares of the underlying company",
        "risk_level": "low",
        "explanation": "Long-term bullish strategy with ownership and growth exposure."
    },
    "buy stock for income": {
        "description": "Buy dividend-paying shares",
        "risk_level": "low",
        "explanation": "Ideal for income-focused investors seeking stability and passive cash flow."
    },
    "bond ladder": {
        "description": "Build a ladder of bonds with staggered maturities",
        "risk_level": "low",
        "explanation": "Generates predictable income while minimizing interest rate risk."
    },
    "index fund": {
        "description": "Buy a diversified ETF tracking a market index (e.g. SPY)",
        "risk_level": "low",
        "explanation": "Diversified exposure with lower volatility and management cost."
    },
    "covered call": {
        "description": "Buy stock + sell a call",
        "risk_level": "low",
        "explanation": "Generates extra income in sideways or mildly bullish markets."
    },
    "cash-secured put": {
        "description": "Sell a put backed by cash",
        "risk_level": "moderate",
        "explanation": "Earn premium while potentially entering a stock at a lower price."
    },
    "protective put": {
        "description": "Buy stock + buy a put",
        "risk_level": "moderate",
        "explanation": "Limits downside while maintaining upside — insurance for your position."
    },
    "collar": {
        "description": "Buy stock + protective put + covered call",
        "risk_level": "moderate",
        "explanation": "Neutral-to-bullish strategy with downside protection and income generation."
    },
    "bull call spread": {
        "description": "Buy a call and sell a higher strike call",
        "risk_level": "high",
        "explanation": "Limited-risk bullish strategy with a defined reward range."
    },
    "bear put spread": {
        "description": "Buy a put and sell a lower strike put",
        "risk_level": "high",
        "explanation": "Limited-risk bearish strategy to profit from modest declines."
    },
    "iron condor": {
        "description": "Sell call + put spreads (same expiry)",
        "risk_level": "medium",
        "explanation": "Best for neutral outlook — profit if price stays in a defined range."
    },
    "straddle": {
        "description": "Buy call and put at same strike/expiry",
        "risk_level": "high",
        "explanation": "Profit from volatility in either direction — useful before earnings or news."
    },
    "strangle": {
        "description": "Buy out-of-the-money call and put",
        "risk_level": "high",
        "explanation": "Cheaper alternative to straddle — bet on volatility outside a range."
    },
    "long call": {
        "description": "Buy a call option",
        "risk_level": "high",
        "explanation": "Speculative bullish trade with high upside but potential full premium loss."
    },
    "long put": {
        "description": "Buy a put option",
        "risk_level": "high",
        "explanation": "Speculative bearish trade with large profit potential on sharp drops."
    },
    "sector rotation": {
        "description": "Shift exposure into leading sectors (e.g. tech, healthcare)",
        "risk_level": "moderate",
        "explanation": "Tactically reallocate capital based on economic cycles and themes."
    },
    "thematic ETF": {
        "description": "Invest in trend-based ETFs (AI, EVs, green energy, etc.)",
        "risk_level": "moderate",
        "explanation": "Gain diversified exposure to high-growth themes with managed risk."
    },
    "buy gold": {
        "description": "Purchase gold ETF or physical gold",
        "risk_level": "low",
        "explanation": "Hedge against inflation and geopolitical instability."
    },
    "defensive stocks": {
        "description": "Invest in consumer staples, healthcare, and utilities",
        "risk_level": "low",
        "explanation": "Reduce volatility and drawdown during uncertain markets."
    },
    "real estate REIT": {
        "description": "Buy shares in real estate investment trusts",
        "risk_level": "moderate",
        "explanation": "Generates income and offers diversification outside equities."
    },
    "target-date fund": {
        "description": "Buy a fund that adjusts over time toward retirement",
        "risk_level": "low",
        "explanation": "Simplifies retirement planning with gradual de-risking."
    },
    "default strategy": {
        "description": "Fallback plan",
        "risk_level": "unknown",
        "explanation": "Model confidence too low — requires manual advisor review."
    }
}

def adjust_allocation(base_percent: int, risk_profile: str) -> str:
    """
    Adjust strategy allocation based on user risk profile.
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
    Selects and returns the most appropriate trading strategy given the user's belief and metadata.
    """
    latest_price = round(float(price_info["latest"]), 2) if isinstance(price_info, dict) else round(float(price_info), 2)

    # 🧠 Create input features for the ML pipeline
    input_row = pd.DataFrame([{
        "belief": belief,
        "ticker": ticker,
        "direction": direction,
        "confidence": confidence,
        "asset_class": asset_class
    }])

    try:
        # 🔮 Predict strategy using trained pipeline
        prediction = pipeline.predict(input_row)

        # ✅ Decode the strategy label from integer to string
        normalized = encoder.inverse_transform([prediction[0]])[0].strip().lower()

        print(f"[SMART MODEL PREDICTION] → {normalized}")
    except Exception as e:
        print(f"[ERROR] Strategy prediction failed: {e}")
        normalized = "default strategy"

    # 🔁 Map known aliases to canonical names
    alias_map = {
        "stock": "buy stock",
        "equity": "buy stock",
        "dividend stock": "buy stock for income"
    }
    normalized = alias_map.get(normalized, normalized)

    if normalized not in STRATEGY_DETAILS:
        print(f"[WARN] Unknown strategy '{normalized}', using fallback.")
        normalized = "default strategy"

    details = STRATEGY_DETAILS[normalized]

    # 📈 Strategy description generation logic
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

    return {
        "type": normalized,
        "description": description,
        "risk_level": details["risk_level"],
        "suggested_allocation": adjust_allocation(20, risk_profile),
        "explanation": details["explanation"]
    }

# ✅ CLI test block
if __name__ == "__main__":
    print("🧪 Running strategy_selector test...")

    strategy = select_strategy(
        belief="I think AAPL will go up sharply after earnings",
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
