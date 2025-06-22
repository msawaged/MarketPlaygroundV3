# backend/app.py
# Main FastAPI app that processes market beliefs and handles feedback.

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from backend.ai_engine.ai_engine import run_ai_engine
import json
import os
from datetime import datetime

# Initialize the FastAPI app
app = FastAPI()

# Load feedback model once at startup (not currently used in this file, but ready for prediction features)
print("✅ Loading feedback model...")

# Define request body schema for /process_belief endpoint
class BeliefRequest(BaseModel):
    belief: str

# Define request body schema for /submit_feedback endpoint
class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str

# === POST /process_belief ===
# Input: natural language belief string
# Output: strategy dict based on interpreted AI processing
@app.post("/process_belief")
def process_belief(request: BeliefRequest) -> Dict[str, Any]:
    try:
        result = run_ai_engine(request.belief)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === POST /submit_feedback ===
# Input: user feedback on AI's selected strategy
# Appends structured record to feedback_data.json for ML learning
@app.post("/submit_feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "belief": request.belief,
            "strategy": request.strategy,
            "result": request.feedback
        }

        # Path to the feedback file
        feedback_file = os.path.join(os.path.dirname(__file__), "feedback_data.json")

        # Load existing feedback
        if os.path.exists(feedback_file):
            with open(feedback_file, "r") as f:
                feedback_list = json.load(f)
        else:
            feedback_list = []

        # Append and save updated list
        feedback_list.append(feedback_entry)
        with open(feedback_file, "w") as f:
            json.dump(feedback_list, f, indent=2)

        return {"message": "✅ Feedback saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
