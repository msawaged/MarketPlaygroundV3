# backend/routes/pnl_router.py

from fastapi import APIRouter
from backend.pnl_tracker import get_live_pnl, log_equity_snapshot

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
