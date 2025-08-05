"""
GPT-4 Strategy Generator — Isolated GPT wrapper that turns beliefs into trading strategies.
"""

import os
import json
from typing import Optional

from backend.openai_config import OPENAI_API_KEY, GPT_MODEL
import openai

# ⛔️ DO NOT initialize client immediately due to compatibility issues with 'proxies'
# ✅ Use lazy loading — only create the client once, when needed
client = None

def initialize_openai_client():
    """Lazy-initialize the OpenAI client once, if needed."""
    global client
    if client is None:
        try:
            print("🔑 Initializing OpenAI client...")
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            print("✅ OpenAI client initialized successfully.")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI client: {e}")
            client = None
    return client


def generate_strategy_with_gpt4(belief: str) -> Optional[dict]:
    """
    Send the user belief to GPT-4 with a structured prompt and return a strategy as a Python dict.
    Returns None if GPT fails or response is invalid.
    """
    openai_client = initialize_openai_client()
    if not openai_client:
        print("⚠️ OpenAI client unavailable. Aborting GPT-4 strategy generation.")
        return None

    # Prompt given to GPT-4 — keep this tightly controlled
    system_prompt = (
        "You are a financial trading assistant. Your job is to return a valid JSON strategy "
        "object in response to user beliefs. Always format output strictly as a JSON object. "
        "Do not include commentary, explanations, or notes outside the JSON."
    )

    user_prompt = (
        f"My belief is: {belief}\n\n"
        "Return a trading strategy in this JSON format:\n"
        "{\n"
        '  "type": "Call Option",\n'
        '  "trade_legs": [\n'
        '    {"action": "Buy to Open", "ticker": "AAPL", "option_type": "Call", "strike_price": "150"}\n'
        "  ],\n"
        '  "expiration": "2025-09-20",\n'
        '  "target_return": "20%",\n'
        '  "max_loss": "Premium Paid",\n'
        '  "time_to_target": "2 weeks",\n'
        '  "explanation": "This strategy profits if AAPL rises post-earnings and limits loss to premium paid."\n'
        "}\n\n"
        "Only output the JSON object. Do not include markdown, commentary, or anything outside the braces."
    )

    try:
        print("🚀 Sending belief to GPT-4...")
        response = openai_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=500,
        )

        gpt_output = response.choices[0].message.content.strip()
        print(f"📥 GPT raw output:\n{gpt_output}\n")

        # Try parsing the GPT output as JSON
        strategy = json.loads(gpt_output)
        print("✅ Successfully parsed GPT-4 output into strategy.")
        return strategy

    except json.JSONDecodeError as je:
        print(f"❌ Failed to parse GPT-4 output as JSON: {je}")
        print("🔍 GPT raw response for manual review:\n", gpt_output)
        return None

    except Exception as e:
        print(f"❌ GPT-4 strategy generation failed: {e}")
        return None
