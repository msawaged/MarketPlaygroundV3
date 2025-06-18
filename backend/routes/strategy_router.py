# backend/routes/strategy_router.py

from fastapi import APIRouter, Request
from backend.ai_engine.ai_engine import run_ai_engine

router = APIRouter()

@router.post("/process_belief")
async def process_belief(request: Request):
    data = await request.json()
    belief = data.get("belief", "")
    result = run_ai_engine(belief)
    return result
