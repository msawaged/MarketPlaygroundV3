# backend/routes/pnl_router.py

"""
Handles endpoints related to portfolio performance:
- /live_pnl          → returns current PnL and equity
- /log_equity        → logs current equity to pnl.json
- /risk_metrics      → analyzes performance and returns risk metrics
"""

from fastapi import APIRouter
from backend.pnl_tracker import get_live_pnl, log_equity_snapshot
from backend.analytics.risk_engine import calculate_risk_metrics  # ✅ New import

router = APIRouter()

@router.get("/live_pnl")
def live_pnl():
    """
    Returns open unrealized PnL and current equity.
    """
    return get_live_pnl()

@router.post("/log_equity")
def log_equity():
    """
    Logs current equity snapshot for historical tracking.
    """
    return log_equity_snapshot()

@router.get("/risk_metrics")
def risk_metrics():
    """
    Calculates volatility, max drawdown, and risk label based on pnl.json history.
    """
    return calculate_risk_metrics()
