# backend/routes/portfolio_router.py

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from backend.portfolio_handler import save_trade, get_portfolio
from backend.analytics import summarize_user_portfolio, generate_portfolio_chart
import tempfile
import json
import csv

router = APIRouter()

# ✅ 1. Save a trade to user's portfolio
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

# ✅ 2. Get full portfolio (list of all trades)
@router.get("/portfolio/{user_id}")
async def get_portfolio_endpoint(user_id: str):
    """
    Get full portfolio (trade history) for a user_id.
    Returns: {
        "user_id": "murad_test",
        "portfolio": [ {trade1}, {trade2}, ... ]
    }
    """
    trades = get_portfolio(user_id)
    return {"user_id": user_id, "portfolio": trades}

# ✅ 3. Get a summary of the portfolio
@router.get("/portfolio_summary/{user_id}")
async def get_portfolio_summary(user_id: str):
    """
    Get a summary breakdown of the user's portfolio:
    - total trades
    - good vs bad feedback
    - unknown feedback
    """
    summary = summarize_user_portfolio(user_id)
    return {"user_id": user_id, "summary": summary}

# ✅ 4. Export portfolio to CSV
@router.get("/export_portfolio/{user_id}")
async def export_portfolio(user_id: str):
    """
    Export user portfolio to a downloadable CSV file.
    Returns: CSV with columns: timestamp, belief, strategy
    """
    trades = get_portfolio(user_id)
    
    if not trades:
        return {"error": "No portfolio data found."}

    # Create temporary CSV file
    tmp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', suffix=".csv")
    writer = csv.DictWriter(tmp_file, fieldnames=["timestamp", "belief", "strategy"])
    writer.writeheader()
    for trade in trades:
        writer.writerow({
            "timestamp": trade.get("timestamp", ""),
            "belief": trade.get("belief", ""),
            "strategy": json.dumps(trade.get("strategy", {}))
        })
    tmp_file.close()

    return FileResponse(path=tmp_file.name, filename=f"{user_id}_portfolio.csv", media_type='text/csv')

# ✅ 5. Generate and return portfolio chart (PNG)
@router.get("/portfolio_chart/{user_id}")
async def get_portfolio_chart(user_id: str):
    """
    Generate a trade volume chart for a user and return it as PNG image.
    """
    file_path = generate_portfolio_chart(user_id)
    return FileResponse(path=file_path, media_type="image/png")
