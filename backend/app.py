# backend/app.py

from fastapi import FastAPI, Request
from backend.ai_engine.ai_engine import run_ai_engine  # ✅ ABSOLUTE IMPORT FROM ROOT

app = FastAPI()

@app.get("/")
def root():
    return {"message": "MarketPlayground API is running."}

@app.post("/process")
async def process_belief(request: Request):
    data = await request.json()
    belief = data.get("belief", "")
    result = run_ai_engine(belief)
    return result
