# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from ai_engine import run_ai_engine

app = FastAPI()

class BeliefRequest(BaseModel):
    belief: str

@app.post("/analyze")
async def analyze_belief(request: BeliefRequest):
    try:
        belief = request.belief
        result = run_ai_engine(belief)
        print(f"[DEBUG] Received: '{belief}' -> {result}")
        return result
    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        return {"error": str(e)}
