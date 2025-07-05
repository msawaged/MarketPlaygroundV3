# backend/routes/feedback_router.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Literal
import json
import os
import csv
from datetime import datetime

from backend.belief_parser import parse_belief
from backend.ai_engine.goal_evaluator import evaluate_goal_from_belief

router = APIRouter()

# ✅ Expected input format
class FeedbackPayload(BaseModel):
    belief: str
    strategy: str
    feedback: Literal["good", "bad"]
    user_id: str = "anonymous"
    risk_profile: str = "moderate"

# ✅ Paths for all feedback logs
FEEDBACK_PATH = os.path.join("backend", "feedback_data.json")             # Raw JSON log
TRAINING_PATH = os.path.join("backend", "Training_Strategies.csv")       # Good samples for retraining
LOG_PATH = os.path.join("backend", "feedback_log.csv")                   # All feedback (flat log)
RETRAIN_PATH = os.path.join("backend", "feedback.csv")                   # ⬅️ Used by retrain_worker

# ✅ Store raw feedback entries as JSON
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

# ✅ Store good samples for model training
def append_training_example(belief, strategy, risk_profile):
    parsed = parse_belief(belief)
    goal = evaluate_goal_from_belief(belief)

    row = {
        "belief": belief,
        "strategy": strategy,
        "asset_class": parsed.get("asset_class", "unknown"),
        "direction": parsed.get("direction", "neutral"),
        "goal_type": goal.get("goal_type", "unspecified"),
        "risk_profile": risk_profile
    }

    file_exists = os.path.isfile(TRAINING_PATH)
    with open(TRAINING_PATH, "a", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

# ✅ Store all feedback in both log.csv and retrain.csv
def log_feedback_csv(entry: dict):
    row = {
        "timestamp": entry["timestamp"],
        "user_id": entry["user_id"],
        "ip": entry["ip"],
        "belief": entry["belief"],
        "strategy": entry["strategy"],
        "feedback": entry["feedback"],
        "risk_profile": entry["risk_profile"]
    }

    # Write to feedback_log.csv (for general auditing)
    log_exists = os.path.isfile(LOG_PATH)
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not log_exists:
            writer.writeheader()
        writer.writerow(row)

    # ✅ Also write to feedback.csv (for retrain_worker)
    retrain_exists = os.path.isfile(RETRAIN_PATH)
    with open(RETRAIN_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not retrain_exists:
            writer.writeheader()
        writer.writerow(row)

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
        "risk_profile": payload.risk_profile
    }

    # Save to all feedback systems
    save_feedback_entry(entry)
    log_feedback_csv(entry)
    if payload.feedback == "good":
        append_training_example(payload.belief, payload.strategy, payload.risk_profile)

    return {"message": "✅ Feedback received. Thank you!"}

# 🧪 GET /feedback_test
@router.get("/feedback_test")
def test_feedback():
    return {"message": "✅ Feedback router connected."}
