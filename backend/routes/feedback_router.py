# backend/routes/feedback_router.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Literal
import json
import os
from datetime import datetime

router = APIRouter()

# ✅ Define expected feedback payload
class FeedbackPayload(BaseModel):
    belief: str
    strategy: str
    feedback: Literal["good", "bad"]
    user_id: str = "anonymous"

# ✅ Feedback storage path
FEEDBACK_PATH = os.path.join("backend", "feedback_data.json")

# ✅ Append feedback to file
def save_feedback_entry(data: dict):
    if os.path.exists(FEEDBACK_PATH):
        with open(FEEDBACK_PATH, "r") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    existing.append(data)

    with open(FEEDBACK_PATH, "w") as f:
        json.dump(existing, f, indent=2)

# ✅ POST /submit_feedback
@router.post("/submit_feedback")
def submit_feedback(payload: FeedbackPayload, request: Request):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": payload.user_id,
        "ip": request.client.host,
        "belief": payload.belief,
        "strategy": payload.strategy,
        "feedback": payload.feedback,
    }

    save_feedback_entry(entry)

    return {"message": "✅ Feedback received. Thank you!"}

# 🧪 Test route (optional)
@router.get("/feedback_test")
def test_feedback():
    return {"message": "✅ Feedback router connected."}
