# backend/routes/portfolio_router.py

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from backend.portfolio_handler import save_trade, get_portfolio
from backend.analytics import summarize_user_portfolio, generate_portfolio_chart
from backend.ai_engine.ai_engine import run_ai_engine  # ✅ New: import AI engine
import tempfile
import json
import csv
from datetime import datetime
import os

router = APIRouter()

# ✅ 1. Save a belief as a trade using AI-generated strategy
@router.post("/save_trade")
async def save_trade_endpoint(request: Request):
    """
    Accepts a user belief and user_id, generates a strategy using the AI engine,
    and logs the resulting strategy to the user's portfolio.

    Input Example:
    {
        "user_id": "murad_test",
        "belief": "I want to 2x my money on AAPL this month"
    }

    Output:
    {
        "status": "✅ Trade saved for user murad_test"
    }
    """
    data = await request.json()
    user_id = data.get("user_id", "anonymous")
    belief = data.get("belief", "")

    # ✅ Run belief through AI engine
    result = run_ai_engine(belief)
    strategy = result.get("strategy", {})

    # === 🔍 Debug print: See what the AI actually returned
    print("\n🚨 [SAVE_TRADE DEBUG OUTPUT]")
    print(json.dumps(result, indent=2))

    # ✅ Save the trade
    save_trade(user_id, belief, strategy)

    return {"status": f"✅ Trade saved for user {user_id}"}
