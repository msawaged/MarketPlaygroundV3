# backend/ai_engine/gpt4_strategy_generator.py

"""
Sends a user belief to GPT-4 and receives a strategy breakdown.
"""

from openai import OpenAI
from backend.openai_config import OPENAI_API_KEY, GPT_MODEL

# ✅ Initialize the OpenAI client (SDK v1.0+)
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_strategy_with_gpt4(belief: str, metadata: dict = None) -> str:
    """
    Calls OpenAI's ChatCompletion API with the user's belief and optional metadata.

    Parameters:
    - belief (str): The user's belief about the market.
    - metadata (dict): Optional dictionary with fields like risk_profile, asset_class, goal_type, etc.

    Returns:
    - strategy (str): A natural language explanation of a tradable strategy.
    """

    # 🎯 Construct the user prompt dynamically
    user_prompt = f"User Belief: {belief.strip()}"

    # Append metadata context if provided
    if metadata:
        if "risk_profile" in metadata:
            user_prompt += f"\nRisk Profile: {metadata['risk_profile']}"
        if "goal_type" in metadata:
            user_prompt += f"\nGoal: {metadata['goal_type']}"
        if "asset_class" in metadata:
            user_prompt += f"\nAsset Class: {metadata['asset_class']}"
        if "timeframe" in metadata:
            user_prompt += f"\nTimeframe: {metadata['timeframe']}"
        if "multiplier" in metadata:
            user_prompt += f"\nDesired Return Multiplier: {metadata['multiplier']}"

    try:
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional options strategist. "
                        "Given a user's belief about a market or asset, suggest the best trading strategy "
                        "using real instruments like options, ETFs, or stocks. Output only the strategy "
                        "in plain English with price levels, entry, and expected profit/risk logic."
                    ),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            max_tokens=500,
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[ERROR] GPT-4 strategy generation failed: {e}")
        return "⚠️ GPT-4 strategy generation failed."
