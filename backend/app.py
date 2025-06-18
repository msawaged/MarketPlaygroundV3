# backend/app.py

from fastapi import FastAPI
from backend.routes.strategy_router import router as strategy_router  # router with /process_belief

app = FastAPI()

@app.get("/")
def root():
    return {"message": "MarketPlayground API is running."}

# Mount all /process_belief and future strategy-related endpoints
app.include_router(strategy_router)
