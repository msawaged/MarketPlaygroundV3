# backend/feedback_handler.py

import os
import json
import joblib
from datetime import datetime
import csv


# === File Paths ===
# Base directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# JSON file where all user feedback entries are stored
FEEDBACK_FILE = os.path.join(BASE_DIR, "feedback_data.json")

# Serialized ML model file for feedback prediction
MODEL_FILE = os.path.join(BASE_DIR, "feedback_model.joblib")

# Path to append feedback into strategy training CSV
CSV_FILE = os.path.join(BASE_DIR, "../strategy_outcomes.csv")


def load_feedback_model():
    """
    Loads the trained feedback ML model if it exists.
    Returns None if model file not found.
    """
    if os.path.exists(MODEL_FILE):
        print("✅ Loading feedback model...")
        return joblib.load(MODEL_FILE)
    else:
        print("⚠️ No trained feedback model found.")
        return None

# Load model once at import time to reuse
# === 🩹 TEMP PATCH: Prevent crash if feedback model is corrupted or missing ===
try:
    model = load_feedback_model()
except Exception as e:
    print(f"[⚠️ Feedback model disabled] {e}")
    model = None


def predict_feedback_label(belief: str, strategy: str) -> str:
    """
    Predicts feedback label ('good' or 'bad') based on
    combined belief and strategy text using the loaded ML model.

    Returns 'unknown' if no model is loaded.
    """
    if not model:
        return "unknown"
    
    # Combine belief and strategy for prediction input
    text = f"{belief} => {strategy}"
    
    # Extract vectorizer and classifier from the loaded model
    vectorizer = model["vectorizer"]
    clf = model["classifier"]
    
    # Transform text input and predict
    X = vectorizer.transform([text])
    prediction = clf.predict(X)[0]
    
    return "good" if prediction == 1 else "bad"

def save_feedback(belief: str, strategy: str, feedback: str = None, user_id: str = "anonymous"):
    """
    Saves user feedback to the feedback JSON file.
    If feedback is not provided, predicts it using the ML model.

    The feedback entry includes timestamp, user_id, belief, strategy, and result.
    """
    data = []

    # Load existing feedback entries if the file exists
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ JSON decode error — starting fresh.")
                data = []

    # If feedback not explicitly provided, infer it via prediction
    if not feedback:
        feedback = predict_feedback_label(belief, strategy)

    # Construct feedback entry
    feedback_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "strategy": strategy,
        "result": feedback
    }

    # Append new entry and save back to JSON file
    data.append(feedback_entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Feedback saved to file for user: {user_id}")

def save_feedback(belief: str, strategy: str, feedback: str = None, user_id: str = "anonymous", **kwargs):
    """
    ✅ Saves user feedback and any extra metadata to JSON.
    Accepts optional args like:
    - feedback (explicit or predicted)
    - user_id
    - confidence
    - source
    """
    data = []

    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ JSON decode error — starting fresh.")
                data = []

    if not feedback:
        feedback = predict_feedback_label(belief, strategy)

    feedback_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "belief": belief,
        "strategy": strategy,
        "result": feedback
    }

    # ✅ Merge any additional metadata into entry (like confidence, source)
    feedback_entry.update(kwargs)

    data.append(feedback_entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # ✅ Append to strategy_outcomes.csv if possible
    try:
        with open(CSV_FILE, mode="a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                datetime.utcnow().isoformat(),
                user_id,
                belief,
                strategy,
                kwargs.get("ticker", "N/A"),
                kwargs.get("pnl_percent", "N/A"),
                feedback,
                kwargs.get("risk", "moderate"),
                kwargs.get("holding_period_days", "N/A"),
                kwargs.get("notes", ""),
                ",".join(kwargs.get("tags", [])) if isinstance(kwargs.get("tags"), list) else kwargs.get("tags", "")
            ])
            print("🟩 Feedback also appended to strategy_outcomes.csv")
    except Exception as e:
        print(f"⚠️ Could not write to strategy_outcomes.csv: {e}")

    print(f"✅ Feedback saved to file for user: {user_id}")

def save_feedback_entry(belief: str, strategy: str, result: str = None, user_id: str = "anonymous", **kwargs):
    """
    ✅ Adaptive alias to support legacy and upgraded feedback entry logic.
    Accepts flexible metadata such as confidence, source, etc.
    Avoids double-passing 'feedback' via both args and kwargs.
    """
    # Remove 'feedback' key from kwargs if present to avoid conflict
    kwargs.pop("feedback", None)

    # Explicitly pass result as feedback
    save_feedback(belief, strategy, feedback=result, user_id=user_id, **kwargs)
                                                                                   
