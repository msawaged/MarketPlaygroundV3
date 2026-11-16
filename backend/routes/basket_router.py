# backend/routes/basket_router.py

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.engine_switch import generate_basket, engine_version

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
        if engine_version() == "legacy":
            from backend.ai_engine.ai_engine import generate_asset_basket
            result = generate_asset_basket(input_text=request.input_text, goal=request.goal, user_id=request.user_id)
        else:
            result = generate_basket(request.input_text, user_id=request.user_id)

        basket_items = [BasketItem(**item) for item in result.get("basket", [])]

        return BasketResponse(
            basket=basket_items,
            goal=result.get("goal", request.goal),
            estimated_return=result.get("estimated_return", "unknown"),
            risk_profile=result.get("risk_profile", "moderate")
        )

    except Exception as e:
        # No canned basket here: a fixed 60/40 with a promised "5-7% a year" ignored the goal (e.g. a 3-year house
        # down payment got 60% stocks) and never said it was a stand-in. Say we couldn't build one instead.
        print("⚠️ AI Engine Basket Generation Failed:", e)
        raise HTTPException(
            status_code=500,
            detail="We couldn't build a basket for that goal just now. Nothing was made up: please try again in a minute.",
        )
