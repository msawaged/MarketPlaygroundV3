# backend/routes/paper_trading_router.py
from fastapi import APIRouter
from pydantic import BaseModel
from backend.paper_trading import paper_engine

router = APIRouter()

class TradeRequest(BaseModel):
    user_id: str
    strategy_data: dict
    belief: str

@router.post("/execute")
def execute_paper_trade(request: TradeRequest):
    return paper_engine.execute_paper_trade(
        request.user_id, 
        request.strategy_data, 
        request.belief
    )

@router.get("/portfolio/{user_id}")
def get_portfolio(user_id: str):
    return paper_engine.get_portfolio(user_id)

@router.post("/close_position")
def close_position(user_id: str, position_id: str):
    return paper_engine.close_position(user_id, position_id)

@router.get("/leaderboard")
def get_leaderboard():
    return paper_engine.get_leaderboard()

@router.post("/process_automatic_feedback")
def process_automatic_feedback(evaluation_days: int = 7):
    """Generate automatic feedback from paper trading performance"""
    return paper_engine.process_automatic_feedback(evaluation_days)