# backend/openai_config.py

"""
Central OpenAI config for GPT-4 usage in MarketPlayground.

🔐 Loads API key from environment variables.
🧠 Sets up global key for OpenAI SDK usage.
"""

import os
import openai
from dotenv import load_dotenv

# ✅ Step 1: Load .env file
# Always load from backend/.env explicitly to avoid ambiguity
load_dotenv()

# ✅ Step 2: Load API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY not found in environment variables.")
else:
    print(f"🔑 OpenAI API key loaded: ...{OPENAI_API_KEY[-4:]}")

# ✅ Step 3: Set API key globally for OpenAI SDK
openai.api_key = OPENAI_API_KEY

# ✅ GPT model to use
GPT_MODEL = "gpt-4"
