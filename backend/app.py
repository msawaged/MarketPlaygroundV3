# ✅ FastAPI app main entry point
from fastapi import FastAPI
from pydantic import BaseModel

# ✅ Import the AI processing engine
from backend.ai_engine.ai_engine import run_ai_engine

# ✅ Create FastAPI instance
app = FastAPI()

# ✅ Define input schema using Pydantic so Swagger UI displays an input box
class BeliefRequest(BaseModel):
    belief: str

# ✅ Endpoint to process natural-language belief and return AI-generated strategy
@app.post("/process_belief")
def process_belief(request: BeliefRequest):
    """
    Accepts a JSON object like {"belief": "TSLA will go up this week"}
    and returns a trading strategy recommendation.
    """
    result = run_ai_engine(request.belief)
    return result
