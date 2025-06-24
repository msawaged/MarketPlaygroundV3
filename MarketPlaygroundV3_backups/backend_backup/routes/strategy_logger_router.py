# backend/routes/strategy_logger_router.py

from fastapi import APIRouter, HTTPException, Query
from backend.logger.strategy_logger import get_user_strategy_history

router = APIRouter()

@router.get("/strategy_history")
def strategy_history(user_id: str = Query(default="anonymous")):
    try:
        history = get_user_strategy_history(user_id)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
