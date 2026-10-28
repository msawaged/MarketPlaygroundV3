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
# The v4 engine uses Claude, so a missing OpenAI key must not stop the app from
# starting. It is only needed when ENGINE_VERSION=legacy.
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# ✅ GPT model to use
GPT_MODEL = "gpt-4"
