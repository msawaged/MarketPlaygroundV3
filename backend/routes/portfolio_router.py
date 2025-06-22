# backend/routes/portfolio_router.py

from fastapi import APIRouter, Request
from backend.portfolio_handler import save_trade, get_portfolio

router = APIRouter()

@router.post("/save_trade")
async def save_trade_endpoint(request: Request):
    """
    Save a trade to the user's portfolio.
    Input: {
        "user_id": "murad_test",
        "belief": "TSLA will go up",
        "strategy": { ... }
    }
    """
    data = await request.json()
    user_id = data.get("user_id", "anonymous")
    belief = data.get("belief", "")
    strategy = data.get("strategy", {})

    save_trade(user_id, belief, strategy)
    return {"status": f"✅ Trade saved for user {user_id}"}

@router.get("/portfolio/{user_id}")
async def get_portfolio_endpoint(user_id: str):
    """
    Get full portfolio (trade history) for a user_id
    """
    trades = get_portfolio(user_id)
    return {"user_id": user_id, "portfolio": trades}
