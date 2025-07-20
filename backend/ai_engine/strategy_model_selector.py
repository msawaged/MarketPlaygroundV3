# backend/ai_engine/strategy_model_selector.py

"""
🧠 Strategy Model Selector
This module decides whether to route belief processing through:
- GPT-4 (LLM)
- Trained ML model
- Hybrid approach

It calls the correct backend engine and returns a consistent strategy output.
"""

from backend.ai_engine.ml_strategy_bridge import generate_strategy_from_ml

# ❌ Removed broken import
# from backend.ai_engine.gpt_strategy_engine import generate_strategy_from_gpt

import json
from backend.openai_config import GPT_MODEL, OPENAI_API_KEY
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_strategy_from_gpt(belief: str, metadata: dict = {}) -> dict:
    """
    Calls GPT-4 to generate a trading strategy from a belief and optional metadata.
    """

    prompt = f"""
You are a financial strategist. Based on the user's belief: "{belief}", generate a trading strategy.

Include:
- type (e.g., long call, bull put spread, buy equity, buy bond ETF)
- trade_legs (e.g., 'buy 1 call 150 strike', 'sell 1 put 140 strike')
- expiration (in 'YYYY-MM-DD' format or 'N/A')
- target_return (expected gain %)
- max_loss (worst-case loss %)
- time_to_target (e.g., 2 weeks, 3 months)
- explanation (why this fits belief)

Context:
- Ticker: {metadata.get('ticker', 'AAPL')}
- Direction: {metadata.get('direction', 'bullish')}
- Asset Class: {metadata.get('asset_class', 'options')}
- Risk Profile: {metadata.get('risk_profile', 'moderate')}
- Confidence: {metadata.get('confidence', 0.5)}
- Goal Type: {metadata.get('goal_type', 'growth')}
- Multiplier: {metadata.get('multiplier', 2)}
- Timeframe: {metadata.get('timeframe', '1 year')}

Respond ONLY with valid JSON. No markdown, no explanation.
"""

    try:
        print("🧠 Calling GPT-4 for strategy generation (via strategy_model_selector)...")
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()

        print("🧾 GPT Response:\n", content)
        strategy = json.loads(content)

        if isinstance(strategy, dict) and "strategy" in strategy:
            return strategy["strategy"]
        return strategy

    except Exception as e:
        print(f"[❌] GPT strategy generation failed: {e}")
        return {
            "type": "error",
            "trade_legs": [],
            "expiration": "N/A",
            "target_return": 0,
            "max_loss": 0,
            "time_to_target": "N/A",
            "explanation": f"GPT strategy generation failed: {e}"
        }

# 🔧 Strategy mode options: "gpt", "ml", or "hybrid"
STRATEGY_MODE = "hybrid"  # Can be toggled via ENV var or API later

def decide_strategy_engine(belief: str, metadata: dict = {}) -> dict:
    """
    🧠 Route the belief through the selected strategy engine.

    Args:
        belief (str): User belief (e.g. "Oil demand will rise")
        metadata (dict): Additional metadata like asset_class, risk_profile, etc.

    Returns:
        dict: Final selected strategy output
    """

    if STRATEGY_MODE == "gpt":
        return generate_strategy_from_gpt(belief, metadata)

    elif STRATEGY_MODE == "ml":
        return generate_strategy_from_ml(belief, metadata)

    elif STRATEGY_MODE == "hybrid":
        # ✅ Try ML first — fallback to GPT if ML fails
        ml_result = generate_strategy_from_ml(belief, metadata)

        if "error" not in ml_result and ml_result.get("confidence", 0) >= 0.6:
            return ml_result
        else:
            print("⚠️ ML result too weak or failed. Using GPT fallback.")
            return generate_strategy_from_gpt(belief, metadata)

    else:
        return {"error": f"Unknown STRATEGY_MODE: {STRATEGY_MODE}"}
