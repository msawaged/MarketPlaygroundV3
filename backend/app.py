from fastapi import FastAPI
from .ai_engine import run_ai_engine  # ✅ FIX: Use relative import

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "MarketPlayground AI is live 🎉"}

@app.post("/run_ai_engine/")
def run_engine(prompt: str):
    """
    Run the AI engine on a user-submitted belief prompt.
    """
    return run_ai_engine(prompt)
