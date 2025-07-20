# backend/ai_engine/gpt4_strategy_generator.py

"""
Sends a user belief to GPT-4 and receives a strategy breakdown.
"""

import openai
from backend.openai_config import OPENAI_API_KEY, GPT_MODEL

# 🔑 Set the key
openai.api_key = OPENAI_API_KEY

def generate_strategy_with_gpt4(belief: str) -> str:
    """
    Calls OpenAI's ChatCompletion API with the user's belief.

    Parameters:
    - belief (str): The user's belief about the market.

    Returns:
    - strategy (str): A natural language explanation of a tradable strategy.
    """
    response = openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a professional options strategist. Given a user's belief about a market or asset, suggest the best trading strategy using real instruments like options, ETFs, or stocks. Output only the strategy in plain English with price levels, entry, and expected profit/risk logic."
            },
            {
                "role": "user",
                "content": belief
            }
        ],
        max_tokens=500,
        temperature=0.7,
    )

    return response["choices"][0]["message"]["content"].strip()
