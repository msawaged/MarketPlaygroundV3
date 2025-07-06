# backend/openai_config.py

"""
Holds your GPT-4 API key and model config.

🔒 IMPORTANT:
- Do NOT hardcode your API key here in production.
- Instead, load it securely from environment variables.
"""

import os

# Load API key from environment variable securely
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = "gpt-4"
