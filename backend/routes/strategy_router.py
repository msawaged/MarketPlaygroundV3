# backend/routes/strategy_router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_engine.main_engine import process_belief

router = APIRouter()

class BeliefRequest(BaseModel):
    belief: str

@router.post("/process_belief")
async def process_user_belief(request: BeliefRequest):
    try:
        result = process_belief(request.belief)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
