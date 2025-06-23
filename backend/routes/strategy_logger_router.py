# backend/routes/strategy_logger_router.py
# ✅ Defines the /strategy/history route for fetching user-specific strategy logs

from fastapi import APIRouter, HTTPException, Query
from backend.logger.strategy_logger import get_user_strategy_history

# Create router
router = APIRouter()

@router.get("/strategy/history")
def strategy_history(user_id: str = Query(default="anonymous")):
    """
    ✅ Fetch strategy history for a given user.
    
    Example:
    GET /strategy/history?user_id=test_user

    Returns:
    - JSON list of past strategies for the user
    """
    try:
        history = get_user_strategy_history(user_id)
        return {"user_id": user_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
