# app.py

# Import FastAPI and HTTPException for API behavior and error handling
from fastapi import FastAPI, HTTPException

# Pydantic BaseModel for request body validation
from pydantic import BaseModel

# ✅ Correct import: 'ai_engine.py' is a module inside the same 'backend' directory
from ai_engine.ai_engine import run_ai_engine

# Create FastAPI app instance
app = FastAPI()

# Define the expected format of incoming JSON request
class BeliefRequest(BaseModel):
    belief: str  # Expecting a string belief from user (e.g., "TSLA will go up")

# Define the POST endpoint to analyze beliefs
@app.post("/analyze/")
async def analyze_belief(request: BeliefRequest):
    try:
        # Pass the belief to the AI engine
        result = run_ai_engine(request.belief)
        # Return the result with success status
        return {"status": "success", "result": result}
    except Exception as e:
        # Catch and raise errors with proper API response
        raise HTTPException(status_code=500, detail=str(e))

# Define a GET endpoint to check if the API is running
@app.get("/")
def read_root():
    return {"message": "MarketPlayground API is up and running"}
