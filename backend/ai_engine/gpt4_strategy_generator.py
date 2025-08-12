# FILE: backend/ai_engine/gpt4_strategy_generator.py
"""
GPT-4 Strategy Generator — Isolated GPT wrapper that turns beliefs into trading strategies.
ENHANCED VERSION: Professional-grade prompts for institutional-level analysis
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
    """
    Lazy-initialize the OpenAI client once, if needed.
    Prevents import-time failures and allows for better error handling.
    """
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
    Send the user belief to GPT-4 with ENHANCED institutional-grade prompts.
    
    Args:
        belief (str): User's market belief/thesis
        
    Returns:
        Optional[dict]: Detailed strategy dict with professional analysis,
                       or None if GPT fails or response is invalid
                       
    Enhanced Features:
        - Professional system prompt positioning GPT as elite strategist
        - Detailed example with 100+ word explanations
        - Higher token limit (800) for comprehensive analysis
        - Increased temperature (0.6) for more creative insights
        - Specific requirements for technical analysis and risk management
    """
    openai_client = initialize_openai_client()
    if not openai_client:
        print("⚠️ OpenAI client unavailable. Aborting GPT-4 strategy generation.")
        return None

    # 🎯 ENHANCED SYSTEM PROMPT: Positions GPT as institutional-grade strategist
    # This dramatically improves the quality and depth of analysis
    system_prompt = (
        "You are an elite institutional trading strategist with 20+ years of experience. "
        "Provide sophisticated, detailed trading strategies with deep market insights. "
        "Your analysis should include technical, fundamental, and risk considerations. "
        "Always format output as valid JSON with comprehensive explanations."
    )

    # 📝 ENHANCED USER PROMPT: Provides detailed example and specific requirements
    # The example explanation is now 100+ words with professional analysis
    user_prompt = (
        f"Belief: {belief}\n\n"
        "Provide a detailed trading strategy in this JSON format:\n"
        "{\n"
        '  "type": "Call Option",\n'
        '  "trade_legs": [\n'
        '    {"action": "Buy to Open", "ticker": "AAPL", "option_type": "Call", "strike_price": "150"}\n'
        "  ],\n"
        '  "expiration": "2025-09-20",\n'
        '  "target_return": "20%",\n'
        '  "max_loss": "Premium Paid",\n'
        '  "time_to_target": "2 weeks",\n'
        '  "explanation": "Given the current market environment and technical indicators, this call option strategy capitalizes on anticipated earnings momentum in AAPL. The strike price at $150 provides optimal risk-reward positioning above current resistance levels. Key catalysts include strong iPhone sales guidance and AI integration announcements. Risk management involves limiting loss to premium ($2.50/share) while targeting 20% returns within the 2-week window. This strategy benefits from positive gamma and delta exposure while maintaining defined risk parameters. Exit criteria: 50% profit target or 2 days before expiration to avoid theta decay."\n'
        "}\n\n"
        "Requirements:\n"
        "- Explanation must be 100+ words with specific market reasoning\n"
        "- Include technical analysis, catalysts, and risk management\n"
        "- Mention specific price targets and exit criteria\n"
        "- Only output valid JSON, no markdown or extra text"
    )

    try:
        print("🚀 Sending belief to GPT-4...")
        
        # 🔧 ENHANCED API CALL: Higher limits for better analysis
        response = openai_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,  # 📈 INCREASED: More creative and varied analysis
            max_tokens=800,   # 📈 INCREASED: Allow for longer, detailed explanations
        )

        gpt_output = response.choices[0].message.content.strip()
        print(f"📥 GPT raw output:\n{gpt_output}\n")

        # 🔍 JSON PARSING: Attempt to parse GPT response as valid JSON
        strategy = json.loads(gpt_output)
        print("✅ Successfully parsed GPT-4 output into strategy.")
        return strategy

    except json.JSONDecodeError as je:
        # 🚨 JSON ERROR: GPT returned invalid JSON format
        print(f"❌ Failed to parse GPT-4 output as JSON: {je}")
        print("🔍 GPT raw response for manual review:\n", gpt_output)
        return None

    except Exception as e:
        # 🚨 GENERAL ERROR: API call failed or other issue
        print(f"❌ GPT-4 strategy generation failed: {e}")
        return None