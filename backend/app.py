# backend/app.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import run_ai_engine  # ✅ FIXED: correct import if ai_engine.py is in backend/

app = FastAPI()

# Allow all origins for now (can restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "MarketPlayground AI backend is live!"}

@app.post("/run_ai_engine/")
async def run_engine(request: Request):
    data = await request.json()
    belief = data.get("belief", "")
    result = run_ai_engine(belief)
    return {"result": result}
