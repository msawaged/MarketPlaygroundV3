# backend/routes/execution_router.py

"""
Handles intelligent execution of trading strategies.
Supports both preview and execution modes with Alpaca integration.
Future-proofed for multi-broker support.
"""

from fastapi import APIRouter, Request
from backend.portfolio_handler import save_trade
from backend.engine_switch import run_belief as _run_belief


def run_ai_engine(belief, risk_profile="moderate", user_id="system", **_):
    """Kept for older call sites: now routed through the active engine (v4 by default)."""
    return _run_belief(belief, user_id=user_id, risk_profile=risk_profile, source="system")
from backend.alpaca_client import submit_market_buy, get_account_info
from typing import Optional

router = APIRouter()

@router.post("/execute_trade")
async def execute_trade(request: Request):
    """
    Executes a user-submitted belief via AI and places trade if eligible.
    """
    data = await request.json()
    user_id = data.get("user_id", "anonymous")
    belief = data.get("belief", "")

    # Run AI engine on belief
    result = run_ai_engine(belief)
    strategy = result.get("strategy", {})
    confidence = strategy.get("confidence", 0)

    # Decide if this strategy qualifies for real execution
    if confidence >= 0.7:
        save_trade(user_id, belief, strategy)
        return {
            "status": "✅ Executed via Alpaca",
            "details": result
        }
    else:
        return {
            "status": "⚠️ Confidence too low for execution",
            "confidence": confidence,
            "details": result
        }


@router.post("/preview_trade")
async def preview_trade(request: Request):
    """
    Returns the strategy without executing it.
    """
    data = await request.json()
    belief = data.get("belief", "")
    result = run_ai_engine(belief)
    return {
        "status": "🧠 Preview only — no trade executed",
        "strategy": result
    }


@router.get("/alpaca/account")
def get_alpaca_account():
    """
    Returns Alpaca account info (paper trading).
    """
    return get_account_info()
