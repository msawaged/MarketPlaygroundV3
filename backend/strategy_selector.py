# backend/strategy_selector.py

import joblib
import os

# ✅ Load smart ML pipeline (pretrained model + preprocessing)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "smart_strategy_pipeline.joblib")
pipeline = joblib.load(MODEL_PATH)

# 📚 Expanded strategy metadata — real-advisor grade coverage
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

# 🎯 Adjust allocation based on risk profile
def adjust_allocation(base_percent: int, risk_profile: str) -> str:
    if risk_profile == "conservative":
        return f"{int(base_percent * 0.6)}%"
    elif risk_profile == "aggressive":
        return f"{int(base_percent * 1.4)}%"
    return f"{base_percent}%"

# 🧠 Strategy selection core
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

    # 🛠️ Prepare input
    input_row = [{
        "belief": belief,
        "ticker": ticker,
        "direction": direction,
        "confidence": confidence,
        "asset_class": asset_class
    }]

    try:
        raw_prediction = pipeline.predict(input_row)[0]
        # 🔍 Handle if model accidentally returns a dict or malformed object
        normalized = raw_prediction if isinstance(raw_prediction, str) else str(raw_prediction.get("type", "default strategy"))
        normalized = normalized.strip().lower()
        print(f"[SMART MODEL PREDICTION] → {normalized}")
    except Exception as e:
        print(f"[ERROR] Strategy prediction failed: {e}")
        normalized = "default strategy"

    # 🧽 Clean up aliases
    alias_map = {
        "stock": "buy stock",
        "equity": "buy stock",
        "dividend stock": "buy stock for income"
    }
    if normalized in alias_map:
        normalized = alias_map[normalized]

    if normalized not in STRATEGY_DETAILS:
        print(f"[WARN] Unknown strategy '{normalized}', using fallback.")
        normalized = "default strategy"

    details = STRATEGY_DETAILS[normalized]

    # ✨ Dynamic description logic
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

# 🧪 Test block (manual run)
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
