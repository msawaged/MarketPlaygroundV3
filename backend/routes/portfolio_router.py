# backend/routes/portfolio_router.py

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from backend.portfolio_handler import save_trade, get_portfolio
from backend.analytics.portfolio_summary import summarize_user_portfolio, generate_portfolio_chart
from backend.engine_switch import run_belief as _run_belief


def run_ai_engine(belief, risk_profile="moderate", user_id="system", **_):
    """Kept for older call sites: now routed through the active engine (v4 by default)."""
    return _run_belief(belief, user_id=user_id, risk_profile=risk_profile, source="system")
import json
import csv
import os
from datetime import datetime

router = APIRouter()

# ✅ 1. Save a belief as a trade using AI-generated strategy
@router.post("/save_trade")
async def save_trade_endpoint(request: Request):
    """
    Accepts a user belief and user_id, generates a strategy using the AI engine,
    and logs the resulting strategy to the user's portfolio.
    """
    data = await request.json()
    user_id = data.get("user_id", "anonymous")
    belief = data.get("belief", "")
    result = run_ai_engine(belief)
    strategy = result.get("strategy", {})

    print("\n🚨 [SAVE_TRADE DEBUG OUTPUT]")
    print(json.dumps(result, indent=2))

    save_trade(user_id, belief, strategy)
    return {"status": f"✅ Trade saved for user {user_id}"}


# ✅ 2. Get a user's saved portfolio/trade history
@router.post("/get_portfolio")
async def fetch_user_portfolio(request: Request):
    """
    Fetches the full portfolio/trade history for a user.
    """
    data = await request.json()
    user_id = data.get("user_id", "anonymous")
    portfolio = get_portfolio(user_id)
    return {"user_id": user_id, "portfolio": portfolio}


# ✅ 3. Return portfolio summary as stats
@router.get("/portfolio_summary")
def portfolio_summary(user_id: str):
    """
    Returns summary statistics for the user's portfolio.
    """
    return summarize_user_portfolio(user_id)


# ✅ 4. Export portfolio to CSV (macOS-safe)
@router.get("/export_portfolio")
def export_portfolio(user_id: str):
    """
    Exports the user's portfolio to a downloadable CSV file.
    Safer version for macOS curl -OJ.
    """
    portfolio = get_portfolio(user_id)
    filename = f"{user_id}_portfolio.csv"
    filepath = os.path.join(os.getcwd(), filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Belief", "Strategy JSON"])
        for entry in portfolio:
            writer.writerow([
                entry.get("timestamp", ""),
                entry.get("belief", ""),
                json.dumps(entry.get("strategy", {}))
            ])

    return FileResponse(path=filepath, filename=filename, media_type="text/csv")


# ✅ 5. Generate and return PNG portfolio chart
@router.get("/portfolio_chart")
def portfolio_chart(user_id: str):
    """
    Returns a PNG chart image of the user's portfolio history.
    """
    return generate_portfolio_chart(user_id)
