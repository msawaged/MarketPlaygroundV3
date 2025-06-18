# backend/app.py

from fastapi import FastAPI
from backend.routes.strategy_router import router as strategy_router
from backend.routes.feedback_predictor import router as feedback_router  # ✅ Handles /predict_feedback
from backend.background_tasks import background_retrain_loop  # 🔁 Background model retrainer
import asyncio

# ✅ Initialize FastAPI app
app = FastAPI()

# ✅ Root health check route
@app.get("/")
def root():
    return {"message": "MarketPlayground API is running."}

# ✅ Include all feature routers
app.include_router(strategy_router)       # 🎯 Handles /process_belief
app.include_router(feedback_router)       # 🧠 Predicts feedback from new strategy

# ✅ Run background training loop on startup
@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(background_retrain_loop())
