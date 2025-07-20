# backend/ai_engine/gpt_strategy_engine.py

"""
🧠 GPT Strategy Engine
Handles strategy generation using OpenAI's GPT-4 based on user beliefs and metadata.
"""

import openai
import os
from backend.logger.log_utils import log_info, log_error

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_strategy_with_gpt(belief, asset_class=None, goal=None, risk_profile=None, **kwargs):
    """
    Generates a trading strategy using GPT-4 based on the user's belief and metadata.

    Args:
        belief (str): The user's natural language belief.
        asset_class (str, optional): Stocks, crypto, bonds, etc.
        goal (str, optional): e.g., "2x my money", "minimize loss"
        risk_profile (str, optional): conservative, moderate, aggressive
        **kwargs: Additional context.

    Returns:
        dict: Strategy details including type, trade legs, explanation, etc.
    """
    try:
        prompt = f"""
You are a trading strategy assistant. Based on the user's belief, generate a realistic, executable strategy.

Belief: "{belief}"
Asset Class: {asset_class or "unspecified"}
Goal: {goal or "unspecified"}
Risk Profile: {risk_profile or "moderate"}

Respond with a JSON object using this format:

{{
    "type": "...",
    "trade_legs": ["buy 1 call 100 strike", "sell 1 call 110 strike"],
    "expiration": "...",
    "target_return": ...,
    "max_loss": ...,
    "time_to_target": "...",
    "explanation": "..."
}}
        """.strip()

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )

        content = response['choices'][0]['message']['content']
        strategy = eval(content) if content.strip().startswith('{') else {}

        log_info(f"[GPT Strategy] Generated strategy for belief: {belief[:60]}")
        return strategy

    except Exception as e:
        log_error(f"[GPT Strategy] Error generating strategy: {str(e)}")
        return {
            "type": "unknown",
            "trade_legs": [],
            "expiration": None,
            "target_return": 0,
            "max_loss": 100,
            "time_to_target": "unknown",
            "explanation": "GPT failed to generate strategy."
        }
