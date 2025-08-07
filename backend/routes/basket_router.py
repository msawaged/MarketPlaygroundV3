# backend/routes/basket_router.py

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.ai_engine.ai_engine import generate_asset_basket  # ✅ Use AI engine, not direct OpenAI call

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

# === 🎯 Basket Endpoint via AI Engine ===
@router.post("/generate_basket", response_model=BasketResponse)
def route_generate_asset_basket(request: BasketRequest):
    """
    Delegates asset basket generation to the AI Engine.
    """
    try:
        result = generate_asset_basket(
            input_text=request.input_text,
            goal=request.goal,
            user_id=request.user_id
        )

        basket_items = [BasketItem(**item) for item in result.get("basket", [])]

        return BasketResponse(
            basket=basket_items,
            goal=result.get("goal", request.goal),
            estimated_return=result.get("estimated_return", "unknown"),
            risk_profile=result.get("risk_profile", "moderate")
        )

    except Exception as e:
        print("⚠️ AI Engine Basket Generation Failed:", e)

        # === 🔁 Fallback: conservative 60/40 allocation
        fallback_basket = [
            BasketItem(
                ticker="VTI",
                type="stock",
                allocation="60%",
                rationale="Broad U.S. equity exposure for long-term growth"
            ),
            BasketItem(
                ticker="BND",
                type="bond",
                allocation="40%",
                rationale="Diversified bond ETF for income and stability"
            )
        ]

        return BasketResponse(
            basket=fallback_basket,
            goal=request.goal or "growth",
            estimated_return="5-7% annually",
            risk_profile="moderate"
        )
