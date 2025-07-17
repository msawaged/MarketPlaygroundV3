# backend/routes/basket_router.py

import os  # ✅ Must come before using os.getenv
from dotenv import load_dotenv
load_dotenv()
print("🔑 Loaded OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))  # ✅ Debug print


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import openai

router = APIRouter()

# === 🧠 Input schema for asset basket generation ===
class BasketRequest(BaseModel):
    user_id: Optional[str] = None
    goal: Optional[str] = None
    input_text: str  # Example: "I want 60% stocks and 40% bonds for growth"

# === 📦 Output schema for each basket asset ===
class BasketItem(BaseModel):
    ticker: str
    type: str  # e.g. stock, bond, crypto
    allocation: str
    rationale: str

class BasketResponse(BaseModel):
    basket: List[BasketItem]
    goal: Optional[str]
    estimated_return: Optional[str]
    risk_profile: Optional[str]

# === ✅ GPT-4 Powered Basket Generator (openai>=1.0.0 compatible) ===
@router.post("/generate_basket", response_model=BasketResponse)
def generate_asset_basket(request: BasketRequest):
    """
    Uses GPT-4 to generate a custom asset allocation basket based on user input.
    Falls back to a sample basket if OpenAI fails.
    """
    try:
        # ✅ Create OpenAI client (new style)
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # ✅ Smart prompt for asset basket generation
        prompt = f"""
You are a financial AI tasked with building a diversified asset basket.

User goal: {request.goal or 'unspecified'}
User input: {request.input_text}

Return a JSON object with:
- basket: a list of 2–5 assets (ticker, type, allocation %, rationale)
- goal: repeat the parsed goal
- estimated_return: string like "5-7% annually"
- risk_profile: string like "conservative", "moderate", or "aggressive"

Format example:
{{
  "basket": [
    {{
      "ticker": "VTI",
      "type": "stock",
      "allocation": "60%",
      "rationale": "Broad U.S. equity exposure"
    }},
    {{
      "ticker": "BND",
      "type": "bond",
      "allocation": "40%",
      "rationale": "Diversified bond holdings"
    }}
  ],
  "goal": "growth",
  "estimated_return": "6-8% annually",
  "risk_profile": "moderate"
}}
Only return valid JSON.
"""

        # ✅ Use the new OpenAI client for GPT-4 chat completion
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500
        )

        # ✅ Parse and format the returned JSON content
        content = response.choices[0].message.content.strip()
        import json
        parsed = json.loads(content)

        basket_items = [BasketItem(**item) for item in parsed.get("basket", [])]

        return BasketResponse(
            basket=basket_items,
            goal=parsed.get("goal", request.goal),
            estimated_return=parsed.get("estimated_return", "unknown"),
            risk_profile=parsed.get("risk_profile", "moderate")
        )

    except Exception as e:
        print("⚠️ GPT-4 Basket Generation Failed:", e)

        # === 🧱 Fallback: hardcoded conservative 60/40 basket ===
        fallback_basket = [
            BasketItem(
                ticker="VTI",
                type="stock",
                allocation="60%",
                rationale="Broad U.S. stock exposure for long-term growth"
            ),
            BasketItem(
                ticker="BND",
                type="bond",
                allocation="40%",
                rationale="Diversified bond ETF for stability and income"
            )
        ]
        return BasketResponse(
            basket=fallback_basket,
            goal=request.goal or "growth",
            estimated_return="5-7% annually",
            risk_profile="moderate"
        )
