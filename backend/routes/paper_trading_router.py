# backend/routes/paper_trading_router.py
from fastapi import APIRouter
from backend.paper_trading import paper_engine

router = APIRouter()

@router.post("/execute")
def execute_paper_trade(user_id: str, strategy_data: dict, belief: str):
    return paper_engine.execute_paper_trade(user_id, strategy_data, belief)

@router.get("/portfolio/{user_id}")
def get_portfolio(user_id: str):
    return paper_engine.get_portfolio(user_id)

@router.get("/leaderboard")
def get_leaderboard():
    return paper_engine.get_leaderboard()